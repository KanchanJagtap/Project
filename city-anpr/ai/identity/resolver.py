import logging
from typing import List, Optional, Protocol
from datetime import datetime, timezone
import uuid

from ai.contracts.models import TrackedVehicle, PlateObservation
from ai.identity.contracts import (
    AssociationDecision,
    AssociationStatus,
    AssociationMethod,
    IdentityEvidence,
    ResolverCandidate,
)
from ai.reid.similarity import cosine_similarity
from ai.contracts.models import AppearanceEmbedding

logger = logging.getLogger(__name__)

class CandidateGenerator(Protocol):
    async def get_candidates(
        self,
        plate_texts: List[str],
        current_camera_id: str,
        timestamp: datetime,
    ) -> List[ResolverCandidate]:
        ...
        
    async def check_topology(
        self,
        source_junction_id: str,
        target_junction_id: str,
    ) -> Optional[dict]:
        """
        Returns edge data if a valid edge exists, else None.
        dict contains 'min_travel_time_sec' and 'max_travel_time_sec'.
        """
        ...

class ResolverConfig:
    # Thresholds
    MATCHED_THRESHOLD = 0.85
    PROBABLE_THRESHOLD = 0.65
    NEW_VEHICLE_THRESHOLD = 0.30
    
    # Weights
    WEIGHT_EXACT_PLATE = 0.5
    WEIGHT_REID = 0.4
    WEIGHT_TOPOLOGY = 0.1
    WEIGHT_TYPE_MATCH = 0.1
    
    # Conflict
    UNCERTAIN_MARGIN = 0.05
    MIN_REID_FOR_PLATE_CONFLICT = 0.2

class MultimodalIdentityResolver:
    def __init__(
        self,
        candidate_generator: CandidateGenerator,
        config: ResolverConfig = ResolverConfig()
    ):
        self.candidate_generator = candidate_generator
        self.config = config

    async def resolve(
        self,
        track: TrackedVehicle,
        plates: List[PlateObservation],
        camera_id: str,
        timestamp: datetime,
    ) -> AssociationDecision:
        
        # 1. Gather all high confidence plates
        valid_plates = [p for p in plates if p.ocr_confidence > 0.5]
        plate_texts = list(set([p.plate_text for p in valid_plates]))
        
        # 2. Get Candidates
        candidates = await self.candidate_generator.get_candidates(
            plate_texts=plate_texts,
            current_camera_id=camera_id,
            timestamp=timestamp,
        )
        
        if not candidates:
            # No candidates. Decide based on plate existence.
            if plate_texts:
                return AssociationDecision(
                    status=AssociationStatus.NEW_VEHICLE,
                    confidence=1.0,
                    method=AssociationMethod.EXACT_PLATE,
                )
            else:
                return AssociationDecision(
                    status=AssociationStatus.ANONYMOUS,
                    confidence=1.0,
                    method=AssociationMethod.MULTI_MODAL,
                )

        # 3. Score Candidates
        scored_evidence = []
        for cand in candidates:
            evidence = await self._score_candidate(cand, track, valid_plates, camera_id, timestamp)
            scored_evidence.append(evidence)
            
        # 4. Filter hard rejected
        valid_evidence = [e for e in scored_evidence if not e.hard_rejected]
        
        if not valid_evidence:
            return AssociationDecision(
                status=AssociationStatus.NEW_VEHICLE if plate_texts else AssociationStatus.ANONYMOUS,
                confidence=1.0,
                method=AssociationMethod.MULTI_MODAL,
            )
            
        # Sort by score descending
        valid_evidence.sort(key=lambda x: x.score, reverse=True)
        top = valid_evidence[0]
        
        # 5. Conflict Resolution
        if len(valid_evidence) > 1:
            runner_up = valid_evidence[1]
            if (top.score - runner_up.score) < self.config.UNCERTAIN_MARGIN and top.score >= self.config.PROBABLE_THRESHOLD:
                # Close competitors -> UNCERTAIN
                return AssociationDecision(
                    status=AssociationStatus.UNCERTAIN,
                    confidence=top.score,
                    method=AssociationMethod.MULTI_MODAL,
                    evidence=top
                )
                
        # 6. Final Decision
        if top.score >= self.config.MATCHED_THRESHOLD:
            # Case D check: Strong plate but terrible ReID
            if top.plate_evidence.get('has_match') and top.reid_evidence:
                if top.reid_evidence.get('cosine_similarity', 1.0) < self.config.MIN_REID_FOR_PLATE_CONFLICT:
                    return AssociationDecision(
                        status=AssociationStatus.UNCERTAIN,
                        confidence=top.score,
                        method=AssociationMethod.MULTI_MODAL,
                        evidence=top
                    )
                    
            method = AssociationMethod.EXACT_PLATE if top.plate_evidence.get('has_match') else AssociationMethod.MULTI_MODAL
            if not top.plate_evidence.get('has_match') and top.reid_evidence.get('cosine_similarity', 0) > 0.8:
                method = AssociationMethod.RE_ID
                
            return AssociationDecision(
                status=AssociationStatus.MATCHED,
                confidence=top.score,
                method=method,
                vehicle_id=top.candidate_vehicle_id,
                evidence=top
            )
        elif top.score >= self.config.PROBABLE_THRESHOLD:
            return AssociationDecision(
                status=AssociationStatus.PROBABLE,
                confidence=top.score,
                method=AssociationMethod.MULTI_MODAL,
                vehicle_id=top.candidate_vehicle_id,
                evidence=top
            )
        else:
            return AssociationDecision(
                status=AssociationStatus.NEW_VEHICLE if plate_texts else AssociationStatus.ANONYMOUS,
                confidence=top.score,
                method=AssociationMethod.MULTI_MODAL,
                evidence=top
            )

    async def _score_candidate(
        self,
        candidate: ResolverCandidate,
        track: TrackedVehicle,
        valid_plates: List[PlateObservation],
        camera_id: str,
        timestamp: datetime,
    ) -> IdentityEvidence:
        ev = IdentityEvidence(candidate_vehicle_id=candidate.vehicle_id)
        score = 0.0
        
        # --- Plate Evidence ---
        plate_match = False
        max_ocr = 0.0
        for p in valid_plates:
            if p.plate_text == candidate.canonical_plate_text:
                plate_match = True
                max_ocr = max(max_ocr, p.ocr_confidence)
                
        if plate_match:
            ev.plate_evidence = {
                "has_match": True,
                "similarity": 1.0,
                "max_ocr_confidence": max_ocr
            }
            score += self.config.WEIGHT_EXACT_PLATE * max_ocr
        else:
            ev.plate_evidence = {"has_match": False}
            
        # --- ReID Evidence ---
        if track.appearance_embedding and candidate.latest_appearance_embedding:
            te = track.appearance_embedding
            if candidate.embedding_model != te.model_name or candidate.embedding_dimension != te.dimension:
                # Incompatible model, but required if no plate match
                ev.reid_evidence = {"model_compatibility": False}
                if not plate_match:
                    ev.hard_rejected = True
                    ev.rejection_reason = "Incompatible embedding model and no plate match"
                    return ev
            else:
                ce = AppearanceEmbedding(
                    vector=candidate.latest_appearance_embedding,
                    model_name=candidate.embedding_model,
                    dimension=candidate.embedding_dimension
                )
                sim = cosine_similarity(te, ce)
                q = te.quality_score or 1.0
                ev.reid_evidence = {
                    "cosine_similarity": float(sim),
                    "embedding_quality": float(q),
                    "model_compatibility": True
                }
                score += self.config.WEIGHT_REID * max(0, sim) * q
                
        # --- Temporal / Topology Evidence ---
        time_delta_sec = (timestamp - candidate.last_detected_at).total_seconds()
        ev.temporal_evidence = {"time_delta_sec": time_delta_sec}
        
        if candidate.last_junction_id:
            # We assume we have a mapping from camera_id to junction_id.
            # In CandidateGenerator we can do this via an edge check.
            edge = await self.candidate_generator.check_topology(
                source_junction_id=candidate.last_junction_id,
                target_junction_id="current_junction"  # generator will map current_camera to junction
            )
            if edge:
                ev.topology_evidence = {
                    "has_topology": True,
                    "min_travel_time": edge['min_travel_time_sec'],
                    "max_travel_time": edge['max_travel_time_sec']
                }
                if time_delta_sec < edge['min_travel_time_sec'] or time_delta_sec > edge['max_travel_time_sec']:
                    ev.topology_evidence["is_possible"] = False
                    ev.hard_rejected = True
                    ev.rejection_reason = "Impossible topology travel time"
                    return ev
                else:
                    ev.topology_evidence["is_possible"] = True
                    score += self.config.WEIGHT_TOPOLOGY
            else:
                # No active edge between the known junctions
                # Could be a hard reject depending on city layout. For now, neutral.
                ev.topology_evidence = {"has_topology": False}
                
        # --- Consistency Evidence ---
        if candidate.canonical_vehicle_type == track.vehicle_type:
            ev.consistency_evidence = {"vehicle_type_match": True}
            score += self.config.WEIGHT_TYPE_MATCH
        else:
            ev.consistency_evidence = {"vehicle_type_match": False}
            score -= 0.1  # penalize mismatch
            
        ev.score = max(0.0, min(1.0, score))
        return ev
