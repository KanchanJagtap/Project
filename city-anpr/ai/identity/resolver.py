import logging
from typing import List, Optional, Protocol, Dict
from datetime import datetime
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
        target_camera_id: str,
    ) -> Optional[dict]:
        ...

class ResolverConfig:
    # Production defaults
    MATCHED_THRESHOLD = 0.85
    PROBABLE_THRESHOLD = 0.65
    NEW_VEHICLE_THRESHOLD = 0.30
    
    # Weights for dynamic normalization
    WEIGHT_EXACT_PLATE = 0.6
    WEIGHT_REID = 0.4
    
    # Penalties
    PENALTY_TYPE_MISMATCH = 0.05
    
    # Conflict
    UNCERTAIN_MARGIN = 0.05

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
        
        valid_plates = [p for p in plates if p.ocr_confidence > 0.5]
        plate_texts = list(set([p.plate_text for p in valid_plates]))
        
        candidates = await self.candidate_generator.get_candidates(
            plate_texts=plate_texts,
            current_camera_id=camera_id,
            timestamp=timestamp,
        )
        
        if not candidates:
            return AssociationDecision(
                status=AssociationStatus.NEW_VEHICLE if plate_texts else AssociationStatus.ANONYMOUS,
                confidence=0.0,
                method=AssociationMethod.MULTI_MODAL,
            )

        scored_evidence = []
        for cand in candidates:
            evidence = await self._score_candidate(cand, track, valid_plates, camera_id, timestamp)
            scored_evidence.append(evidence)
            
        valid_evidence = [e for e in scored_evidence if not e.hard_rejected]
        
        if not valid_evidence:
            return AssociationDecision(
                status=AssociationStatus.NEW_VEHICLE if plate_texts else AssociationStatus.ANONYMOUS,
                confidence=0.0,
                method=AssociationMethod.MULTI_MODAL,
            )
            
        valid_evidence.sort(key=lambda x: x.score, reverse=True)
        top = valid_evidence[0]
        
        # Cross-modal conflict check
        # e.g., OCR prefers A, Re-ID prefers B
        if len(valid_evidence) > 1:
            runner_up = valid_evidence[1]
            
            top_plate_match = top.plate_evidence.get('has_match', False)
            runner_plate_match = runner_up.plate_evidence.get('has_match', False)
            top_reid = top.reid_evidence.get('cosine_similarity', 0.0)
            runner_reid = runner_up.reid_evidence.get('cosine_similarity', 0.0)
            
            # If top has plate but runner_up has significantly better Re-ID (> 0.2 diff) and both are decent candidates
            if top_plate_match and not runner_plate_match and (runner_reid - top_reid > 0.5) and runner_reid > 0.8:
                return AssociationDecision(
                    status=AssociationStatus.UNCERTAIN,
                    confidence=top.score,
                    method=AssociationMethod.MULTI_MODAL,
                    evidence=top
                )
                
            # Close competitors check
            if (top.score - runner_up.score) <= self.config.UNCERTAIN_MARGIN and top.score >= self.config.PROBABLE_THRESHOLD:
                return AssociationDecision(
                    status=AssociationStatus.UNCERTAIN,
                    confidence=top.score,
                    method=AssociationMethod.MULTI_MODAL,
                    evidence=top
                )
                
        # Final Decision
        if top.score >= self.config.MATCHED_THRESHOLD:
            method = AssociationMethod.EXACT_PLATE if top.plate_evidence.get('has_match') else AssociationMethod.RE_ID
            if top.plate_evidence.get('has_match') and top.reid_evidence.get('cosine_similarity', 0) > 0.8:
                method = AssociationMethod.MULTI_MODAL
                
            # Block 1: Cap Re-ID Authority
            if not top.plate_evidence.get('has_match') and method == AssociationMethod.RE_ID:
                return AssociationDecision(
                    status=AssociationStatus.PROBABLE,
                    confidence=top.score,
                    method=method,
                    vehicle_id=top.candidate_vehicle_id,
                    evidence=top
                )
                
            return AssociationDecision(
                status=AssociationStatus.MATCHED,
                confidence=top.score,
                method=method,
                vehicle_id=top.candidate_vehicle_id,
                evidence=top
            )
        elif top.score >= self.config.PROBABLE_THRESHOLD:
            method = AssociationMethod.EXACT_PLATE if top.plate_evidence.get('has_match') else AssociationMethod.RE_ID
            return AssociationDecision(
                status=AssociationStatus.PROBABLE,
                confidence=top.score,
                method=method,
                vehicle_id=top.candidate_vehicle_id,
                evidence=top
            )
        else:
            return AssociationDecision(
                status=AssociationStatus.NEW_VEHICLE if plate_texts else AssociationStatus.ANONYMOUS,
                confidence=0.0,
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
        
        # 1. Temporal / Topology Hard Filters
        time_delta_sec = (timestamp - candidate.last_detected_at).total_seconds()
        ev.temporal_evidence = {"time_delta_sec": time_delta_sec}
        
        if time_delta_sec < 0:
            ev.hard_rejected = True
            ev.rejection_reason = "Negative travel time"
            return ev
            
        if candidate.last_junction_id:
            edge = await self.candidate_generator.check_topology(
                source_junction_id=candidate.last_junction_id,
                target_camera_id=camera_id  # Abstracted inside generator
            )
            if edge:
                ev.topology_evidence = {
                    "has_topology": True,
                    "is_possible": True,
                    "min_travel_time": edge['min_travel_time_sec'],
                    "max_travel_time": edge['max_travel_time_sec']
                }
                if time_delta_sec < edge['min_travel_time_sec'] or time_delta_sec > edge['max_travel_time_sec']:
                    ev.topology_evidence["is_possible"] = False
                    ev.hard_rejected = True
                    ev.rejection_reason = "Impossible topology travel time"
                    return ev
            else:
                ev.topology_evidence = {"has_topology": False}
        else:
            ev.topology_evidence = {"has_topology": False}
            
        # 2. Dynamic Evidence Scoring
        raw_score = 0.0
        max_possible_weight = 0.0
        
        # --- Plate Evidence ---
        plate_match = False
        max_ocr = 0.0
        if valid_plates and candidate.canonical_plate_text:
            max_possible_weight += self.config.WEIGHT_EXACT_PLATE
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
                raw_score += self.config.WEIGHT_EXACT_PLATE * max_ocr
            else:
                ev.plate_evidence = {"has_match": False}
        else:
            ev.plate_evidence = {"has_match": False}
            
        # --- ReID Evidence ---
        if track.appearance_embedding and candidate.latest_appearance_embedding:
            te = track.appearance_embedding
            if candidate.embedding_model != te.model_name or candidate.embedding_dimension != te.dimension:
                ev.reid_evidence = {"comparable": False, "model_compatibility": False}
                # Missing evidence, max_possible_weight NOT increased.
            else:
                max_possible_weight += self.config.WEIGHT_REID
                ce = AppearanceEmbedding(
                    vector=candidate.latest_appearance_embedding,
                    model_name=candidate.embedding_model,
                    dimension=candidate.embedding_dimension
                )
                sim = float(cosine_similarity(te, ce))
                q = te.quality_score or 1.0
                ev.reid_evidence = {
                    "comparable": True,
                    "model_compatibility": True,
                    "cosine_similarity": sim,
                    "embedding_quality": q,
                }
                raw_score += self.config.WEIGHT_REID * max(0, sim) * q
        else:
            ev.reid_evidence = {"comparable": False}
            
        # 3. Score Normalization
        if max_possible_weight > 0:
            normalized_score = raw_score / max_possible_weight
        else:
            normalized_score = 0.0
            
        # 4. Consistency Evidence (Soft Penalty)
        if candidate.canonical_vehicle_type == track.vehicle_type:
            ev.consistency_evidence = {"vehicle_type_match": True}
        else:
            ev.consistency_evidence = {"vehicle_type_match": False}
            normalized_score -= self.config.PENALTY_TYPE_MISMATCH
            
        ev.score = max(0.0, min(1.0, normalized_score))
        return ev
