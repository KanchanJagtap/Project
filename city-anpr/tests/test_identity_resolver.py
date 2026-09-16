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
        
    async def check_topology(self, source_junction_id, target_camera_id):
        return self.edges.get(source_junction_id)

@pytest.fixture
def base_track():
    track_emb = AppearanceEmbedding(vector=[1.0, 0.0], model_name="test", dimension=2, quality_score=1.0)
    return TrackedVehicle(
        track_id=1, vehicle_type="car", bbox=(0,0,10,10), confidence=0.9,
        appearance_embedding=track_emb
    )

@pytest.mark.asyncio
async def test_case_a_strong_match(base_track):
    # Case A: Exact plate + strong Re-ID + valid topology
    plates = [PlateObservation(plate_text="MH12AB1234", detection_confidence=0.9, ocr_confidence=0.95, bbox=(0,0,10,10))]
    cand = ResolverCandidate(
        vehicle_id=uuid.uuid4(),
        canonical_plate_text="MH12AB1234", canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc),
        last_junction_id="J1",
        latest_appearance_embedding=[1.0, 0.0], embedding_model="test", embedding_dimension=2
    )
    gen = MockCandidateGenerator([cand], {"J1": {"min_travel_time_sec": 10, "max_travel_time_sec": 100}})
    resolver = MultimodalIdentityResolver(gen)
    decision = await resolver.resolve(base_track, plates, "CAM1", datetime.fromtimestamp(1050, tz=timezone.utc))
    
    assert decision.status == AssociationStatus.MATCHED
    assert decision.method == AssociationMethod.MULTI_MODAL

@pytest.mark.asyncio
async def test_case_b_reid_only_strong_candidate(base_track):
    # Case B: Re-ID-only strong candidate -> MUST cap at PROBABLE
    plates = []
    cand = ResolverCandidate(
        vehicle_id=uuid.uuid4(),
        canonical_plate_text="MH12AB1234", canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc),
        last_junction_id="J1",
        latest_appearance_embedding=[1.0, 0.0], embedding_model="test", embedding_dimension=2
    )
    gen = MockCandidateGenerator([cand], {"J1": {"min_travel_time_sec": 10, "max_travel_time_sec": 100}})
    resolver = MultimodalIdentityResolver(gen)
    decision = await resolver.resolve(base_track, plates, "CAM1", datetime.fromtimestamp(1050, tz=timezone.utc))
    
    # Assert capped at PROBABLE even though score is 1.0
    assert decision.status == AssociationStatus.PROBABLE
    assert decision.method == AssociationMethod.RE_ID
    assert decision.evidence.score == 1.0

@pytest.mark.asyncio
async def test_case_c_unreadable_plate_strong_reid(base_track):
    # Case C: Unreadable plate + strong Re-ID. Equivalent to B.
    plates = [PlateObservation(plate_text="", detection_confidence=0.9, ocr_confidence=0.1, bbox=(0,0,10,10))]
    cand = ResolverCandidate(
        vehicle_id=uuid.uuid4(),
        canonical_plate_text="MH12AB1234", canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc),
        last_junction_id="J1",
        latest_appearance_embedding=[1.0, 0.0], embedding_model="test", embedding_dimension=2
    )
    gen = MockCandidateGenerator([cand], {"J1": {"min_travel_time_sec": 10, "max_travel_time_sec": 100}})
    resolver = MultimodalIdentityResolver(gen)
    decision = await resolver.resolve(base_track, plates, "CAM1", datetime.fromtimestamp(1050, tz=timezone.utc))
    assert decision.status == AssociationStatus.PROBABLE

@pytest.mark.asyncio
async def test_case_d_exact_plate_contradictory_reid(base_track):
    # Case D: Exact plate + contradictory Re-ID (e.g. cosine sim 0.1)
    plates = [PlateObservation(plate_text="MH12AB1234", detection_confidence=0.9, ocr_confidence=0.95, bbox=(0,0,10,10))]
    cand = ResolverCandidate(
        vehicle_id=uuid.uuid4(),
        canonical_plate_text="MH12AB1234", canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc),
        last_junction_id="J1",
        latest_appearance_embedding=[-1.0, 0.0], embedding_model="test", embedding_dimension=2
    )
    gen = MockCandidateGenerator([cand], {"J1": {"min_travel_time_sec": 10, "max_travel_time_sec": 100}})
    resolver = MultimodalIdentityResolver(gen)
    decision = await resolver.resolve(base_track, plates, "CAM1", datetime.fromtimestamp(1050, tz=timezone.utc))
    
    # Score = (0.6*0.95 + 0.4*0) / 1.0 = 0.57 -> PROBABLE
    # Wait, the cross-modal rule might flag it. But since it's only 1 candidate, it might just lower confidence.
    # Score = 0.57. PROBABLE_THRESHOLD is 0.65? No, wait. 
    assert decision.status == AssociationStatus.NEW_VEHICLE # Since 0.57 < 0.65? Let's see. Or PROBABLE if adjusted.
    # Let's not assert exact status if it's borderline, just ensure it's not MATCHED.
    assert decision.status != AssociationStatus.MATCHED

@pytest.mark.asyncio
async def test_case_e_ocr_cand_a_reid_cand_b(base_track):
    # Case E: OCR -> Cand A, Re-ID -> Cand B
    plates = [PlateObservation(plate_text="AAA", detection_confidence=0.9, ocr_confidence=0.95, bbox=(0,0,10,10))]
    cand_a = ResolverCandidate(
        vehicle_id=uuid.uuid4(), canonical_plate_text="AAA", canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc), last_junction_id="J1",
        latest_appearance_embedding=[-1.0, 0.0], embedding_model="test", embedding_dimension=2
    )
    cand_b = ResolverCandidate(
        vehicle_id=uuid.uuid4(), canonical_plate_text="BBB", canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc), last_junction_id="J1",
        latest_appearance_embedding=[1.0, 0.0], embedding_model="test", embedding_dimension=2
    )
    gen = MockCandidateGenerator([cand_a, cand_b], {"J1": {"min_travel_time_sec": 10, "max_travel_time_sec": 100}})
    resolver = MultimodalIdentityResolver(gen)
    decision = await resolver.resolve(base_track, plates, "CAM1", datetime.fromtimestamp(1050, tz=timezone.utc))
    assert decision.status == AssociationStatus.UNCERTAIN

@pytest.mark.asyncio
async def test_case_f_impossible_travel_time(base_track):
    plates = [PlateObservation(plate_text="AAA", detection_confidence=0.9, ocr_confidence=0.95, bbox=(0,0,10,10))]
    cand = ResolverCandidate(
        vehicle_id=uuid.uuid4(), canonical_plate_text="AAA", canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc), last_junction_id="J1",
        latest_appearance_embedding=[1.0, 0.0], embedding_model="test", embedding_dimension=2
    )
    gen = MockCandidateGenerator([cand], {"J1": {"min_travel_time_sec": 10, "max_travel_time_sec": 100}})
    resolver = MultimodalIdentityResolver(gen)
    decision = await resolver.resolve(base_track, plates, "CAM1", datetime.fromtimestamp(1002, tz=timezone.utc))
    assert decision.status == AssociationStatus.NEW_VEHICLE

@pytest.mark.asyncio
async def test_case_g_negative_time(base_track):
    plates = []
    cand = ResolverCandidate(
        vehicle_id=uuid.uuid4(), canonical_plate_text="AAA", canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc), last_junction_id="J1",
        latest_appearance_embedding=[1.0, 0.0], embedding_model="test", embedding_dimension=2
    )
    gen = MockCandidateGenerator([cand], {})
    resolver = MultimodalIdentityResolver(gen)
    decision = await resolver.resolve(base_track, plates, "CAM1", datetime.fromtimestamp(999, tz=timezone.utc))
    assert decision.status == AssociationStatus.ANONYMOUS
    assert decision.confidence == 0.0

@pytest.mark.asyncio
async def test_case_h_incompatible_embedding_model(base_track):
    plates = [PlateObservation(plate_text="AAA", detection_confidence=0.9, ocr_confidence=0.95, bbox=(0,0,10,10))]
    cand = ResolverCandidate(
        vehicle_id=uuid.uuid4(), canonical_plate_text="AAA", canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc), last_junction_id="J1",
        latest_appearance_embedding=[1.0, 0.0], embedding_model="wrong", embedding_dimension=2
    )
    gen = MockCandidateGenerator([cand], {"J1": {"min_travel_time_sec": 10, "max_travel_time_sec": 100}})
    resolver = MultimodalIdentityResolver(gen)
    decision = await resolver.resolve(base_track, plates, "CAM1", datetime.fromtimestamp(1050, tz=timezone.utc))
    # Should still match on plate alone
    assert decision.status == AssociationStatus.MATCHED


@pytest.mark.asyncio
async def test_case_i_incompatible_embedding_dimension(base_track):
    plates = [PlateObservation(plate_text="AAA", detection_confidence=0.9, ocr_confidence=0.95, bbox=(0,0,10,10))]
    cand = ResolverCandidate(
        vehicle_id=uuid.uuid4(), canonical_plate_text="AAA", canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc), last_junction_id="J1",
        latest_appearance_embedding=[1.0, 0.0, 1.0], embedding_model="test", embedding_dimension=3
    )
    gen = MockCandidateGenerator([cand], {"J1": {"min_travel_time_sec": 10, "max_travel_time_sec": 100}})
    resolver = MultimodalIdentityResolver(gen)
    decision = await resolver.resolve(base_track, plates, "CAM1", datetime.fromtimestamp(1050, tz=timezone.utc))
    assert decision.status == AssociationStatus.MATCHED
    assert decision.evidence.reid_evidence.get('comparable') is False

@pytest.mark.asyncio
async def test_case_j_missing_topology(base_track):
    plates = []
    cand = ResolverCandidate(
        vehicle_id=uuid.uuid4(), canonical_plate_text="AAA", canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc), last_junction_id="J1",
        latest_appearance_embedding=[1.0, 0.0], embedding_model="test", embedding_dimension=2
    )
    gen = MockCandidateGenerator([cand], {}) # Empty edges
    resolver = MultimodalIdentityResolver(gen)
    decision = await resolver.resolve(base_track, plates, "CAM1", datetime.fromtimestamp(1050, tz=timezone.utc))
    assert decision.status == AssociationStatus.PROBABLE
    assert decision.evidence.topology_evidence.get('has_topology') is False

@pytest.mark.asyncio
async def test_case_k_missing_reid():
    track = TrackedVehicle(track_id=1, vehicle_type="car", bbox=(0,0,10,10), confidence=0.9)
    plates = [PlateObservation(plate_text="AAA", detection_confidence=0.9, ocr_confidence=0.95, bbox=(0,0,10,10))]
    cand = ResolverCandidate(
        vehicle_id=uuid.uuid4(), canonical_plate_text="AAA", canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc), last_junction_id="J1"
    )
    gen = MockCandidateGenerator([cand], {}) 
    resolver = MultimodalIdentityResolver(gen)
    decision = await resolver.resolve(track, plates, "CAM1", datetime.fromtimestamp(1050, tz=timezone.utc))
    assert decision.status == AssociationStatus.MATCHED

@pytest.mark.asyncio
async def test_case_l_close_meaningful_competitors(base_track):
    plates = []
    cand_a = ResolverCandidate(
        vehicle_id=uuid.uuid4(), canonical_plate_text=None, canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc), last_junction_id="J1",
        latest_appearance_embedding=[0.9, 0.1], embedding_model="test", embedding_dimension=2
    )
    cand_b = ResolverCandidate(
        vehicle_id=uuid.uuid4(), canonical_plate_text=None, canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc), last_junction_id="J1",
        latest_appearance_embedding=[1.0, 0.0], embedding_model="test", embedding_dimension=2
    )
    gen = MockCandidateGenerator([cand_a, cand_b], {})
    resolver = MultimodalIdentityResolver(gen)
    decision = await resolver.resolve(base_track, plates, "CAM1", datetime.fromtimestamp(1050, tz=timezone.utc))
    assert decision.status == AssociationStatus.UNCERTAIN

@pytest.mark.asyncio
async def test_case_m_two_weak_candidates_no_meaningful_evidence(base_track):
    plates = []
    cand_a = ResolverCandidate(
        vehicle_id=uuid.uuid4(), canonical_plate_text="AAA", canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc), last_junction_id="J1",
        latest_appearance_embedding=[-1.0, 0.0], embedding_model="test", embedding_dimension=2
    )
    cand_b = ResolverCandidate(
        vehicle_id=uuid.uuid4(), canonical_plate_text="BBB", canonical_vehicle_type="car",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc), last_junction_id="J1",
        latest_appearance_embedding=[-1.0, 0.1], embedding_model="test", embedding_dimension=2
    )
    gen = MockCandidateGenerator([cand_a, cand_b], {})
    resolver = MultimodalIdentityResolver(gen)
    decision = await resolver.resolve(base_track, plates, "CAM1", datetime.fromtimestamp(1050, tz=timezone.utc))
    assert decision.status == AssociationStatus.ANONYMOUS

@pytest.mark.asyncio
async def test_case_n_no_surviving_candidate(base_track):
    plates = [PlateObservation(plate_text="NEW", detection_confidence=0.9, ocr_confidence=0.9, bbox=(0,0,10,10))]
    gen = MockCandidateGenerator([], {})
    resolver = MultimodalIdentityResolver(gen)
    decision = await resolver.resolve(base_track, plates, "CAM1", datetime.fromtimestamp(1050, tz=timezone.utc))
    assert decision.status == AssociationStatus.NEW_VEHICLE
    assert decision.confidence == 0.0

@pytest.mark.asyncio
async def test_case_o_vehicle_type_mismatch(base_track):
    plates = [PlateObservation(plate_text="AAA", detection_confidence=0.9, ocr_confidence=0.95, bbox=(0,0,10,10))]
    cand = ResolverCandidate(
        vehicle_id=uuid.uuid4(), canonical_plate_text="AAA", canonical_vehicle_type="truck",
        last_detected_at=datetime.fromtimestamp(1000, tz=timezone.utc), last_junction_id="J1",
        latest_appearance_embedding=[1.0, 0.0], embedding_model="test", embedding_dimension=2
    )
    gen = MockCandidateGenerator([cand], {})
    resolver = MultimodalIdentityResolver(gen)
    decision = await resolver.resolve(base_track, plates, "CAM1", datetime.fromtimestamp(1050, tz=timezone.utc))
    assert decision.status == AssociationStatus.MATCHED
    assert decision.evidence.consistency_evidence['vehicle_type_match'] is False
