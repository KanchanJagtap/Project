import pytest
from datetime import datetime, timezone
import uuid
import numpy as np

from ai.contracts.models import TrackedVehicle, PlateObservation, AppearanceEmbedding
from ai.identity.contracts import (
    AssociationStatus,
    AssociationMethod,
    ResolverCandidate,
)
from ai.identity.resolver import MultimodalIdentityResolver, ResolverConfig

class MockCandidateGenerator:
    def __init__(self, candidates, edges):
        self.candidates = candidates
        self.edges = edges
        
    async def get_candidates(self, plate_texts, current_camera_id, timestamp):
        return self.candidates
        
    async def check_topology(self, source_junction_id, target_junction_id):
        return self.edges.get((source_junction_id, target_junction_id))

@pytest.mark.asyncio
async def test_case_a_strong_match():
    # Case A: Exact Plate + Valid Topology + Strong ReID -> MATCHED
    track_emb = AppearanceEmbedding(vector=[1.0, 0.0], model_name="test", dimension=2, quality_score=1.0)
    track = TrackedVehicle(
        track_id=1, vehicle_type="car", bbox=(0,0,10,10), confidence=0.9,
        appearance_embedding=track_emb
    )
    plates = [
        PlateObservation(plate_text="MH12AB1234", detection_confidence=0.9, ocr_confidence=0.95, bbox=(0,0,10,10))
    ]
    
    cand = ResolverCandidate(
        vehicle_id=uuid.uuid4(),
        canonical_plate_text="MH12AB1234",
        canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc),
        last_junction_id="J1",
        latest_appearance_embedding=[1.0, 0.0],
        embedding_model="test",
        embedding_dimension=2
    )
    
    gen = MockCandidateGenerator(
        candidates=[cand],
        edges={("J1", "current_junction"): {"min_travel_time_sec": 10, "max_travel_time_sec": 100}}
    )
    
    resolver = MultimodalIdentityResolver(gen)
    decision = await resolver.resolve(
        track=track, plates=plates, camera_id="CAM1", timestamp=datetime.fromtimestamp(1050, tz=timezone.utc)
    )
    
    assert decision.status == AssociationStatus.MATCHED
    assert decision.method == AssociationMethod.EXACT_PLATE
    assert decision.vehicle_id == cand.vehicle_id
    assert decision.evidence.plate_evidence['has_match'] is True
    assert decision.evidence.topology_evidence['is_possible'] is True

@pytest.mark.asyncio
async def test_case_b_reid_only():
    # Case B: No Plate + Valid Topology + Strong ReID -> PROBABLE (or MATCHED depending on threshold)
    track_emb = AppearanceEmbedding(vector=[1.0, 0.0], model_name="test", dimension=2, quality_score=1.0)
    track = TrackedVehicle(
        track_id=1, vehicle_type="car", bbox=(0,0,10,10), confidence=0.9,
        appearance_embedding=track_emb
    )
    plates = []
    
    cand = ResolverCandidate(
        vehicle_id=uuid.uuid4(),
        canonical_plate_text="MH12AB1234",
        canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc),
        last_junction_id="J1",
        latest_appearance_embedding=[1.0, 0.0],
        embedding_model="test",
        embedding_dimension=2
    )
    
    gen = MockCandidateGenerator(
        candidates=[cand],
        edges={("J1", "current_junction"): {"min_travel_time_sec": 10, "max_travel_time_sec": 100}}
    )
    
    # Adjust thresholds to make it PROBABLE (base 0.0 + reid 0.4 + topo 0.1 + type 0.1 = 0.60)
    config = ResolverConfig()
    config.PROBABLE_THRESHOLD = 0.50
    config.MATCHED_THRESHOLD = 0.85
    
    resolver = MultimodalIdentityResolver(gen, config)
    decision = await resolver.resolve(
        track=track, plates=plates, camera_id="CAM1", timestamp=datetime.fromtimestamp(1050, tz=timezone.utc)
    )
    
    assert decision.status == AssociationStatus.PROBABLE
    assert decision.evidence.plate_evidence['has_match'] is False
    assert decision.evidence.reid_evidence['cosine_similarity'] == 1.0

@pytest.mark.asyncio
async def test_case_f_impossible_time():
    # Case F: Impossible travel time -> hard reject
    track_emb = AppearanceEmbedding(vector=[1.0, 0.0], model_name="test", dimension=2, quality_score=1.0)
    track = TrackedVehicle(
        track_id=1, vehicle_type="car", bbox=(0,0,10,10), confidence=0.9,
        appearance_embedding=track_emb
    )
    plates = [
        PlateObservation(plate_text="MH12AB1234", detection_confidence=0.9, ocr_confidence=0.95, bbox=(0,0,10,10))
    ]
    
    cand = ResolverCandidate(
        vehicle_id=uuid.uuid4(),
        canonical_plate_text="MH12AB1234",
        canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc),
        last_junction_id="J1",
        latest_appearance_embedding=[1.0, 0.0],
        embedding_model="test",
        embedding_dimension=2
    )
    
    gen = MockCandidateGenerator(
        candidates=[cand],
        edges={("J1", "current_junction"): {"min_travel_time_sec": 10, "max_travel_time_sec": 100}}
    )
    
    resolver = MultimodalIdentityResolver(gen)
    
    # timestamp is only 2 seconds later -> impossible travel time (min is 10)
    decision = await resolver.resolve(
        track=track, plates=plates, camera_id="CAM1", timestamp=datetime.fromtimestamp(1002, tz=timezone.utc)
    )
    
    assert decision.status == AssociationStatus.NEW_VEHICLE
    

@pytest.mark.asyncio
async def test_case_e_close_competitors():
    # Candidate A and B very close -> UNCERTAIN
    track = TrackedVehicle(
        track_id=1, vehicle_type="car", bbox=(0,0,10,10), confidence=0.9,
    )
    plates = []
    
    candA = ResolverCandidate(
        vehicle_id=uuid.uuid4(),
        canonical_plate_text="AAA",
        canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc),
    )
    candB = ResolverCandidate(
        vehicle_id=uuid.uuid4(),
        canonical_plate_text="BBB",
        canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc),
    )
    
    gen = MockCandidateGenerator(
        candidates=[candA, candB],
        edges={}
    )
    
    # Force high scores (they both just match vehicle type, so score = 0.1). 
    # Let's adjust thresholds to make 0.1 probable.
    config = ResolverConfig()
    config.PROBABLE_THRESHOLD = 0.05
    config.MATCHED_THRESHOLD = 0.85
    config.UNCERTAIN_MARGIN = 0.05
    
    resolver = MultimodalIdentityResolver(gen, config)
    decision = await resolver.resolve(
        track=track, plates=[], camera_id="CAM1", timestamp=datetime.fromtimestamp(1050, tz=timezone.utc)
    )
    
    assert decision.status == AssociationStatus.UNCERTAIN
    assert decision.evidence is not None

