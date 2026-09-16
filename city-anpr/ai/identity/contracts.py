from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid
from enum import Enum

class AssociationStatus(str, Enum):
    MATCHED = "MATCHED"
    PROBABLE = "PROBABLE"
    UNCERTAIN = "UNCERTAIN"
    ANONYMOUS = "ANONYMOUS"
    NEW_VEHICLE = "NEW_VEHICLE"

class AssociationMethod(str, Enum):
    EXACT_PLATE = "EXACT_PLATE"
    FUZZY_PLATE = "FUZZY_PLATE"
    RE_ID = "RE_ID"
    MULTI_MODAL = "MULTI_MODAL"
    MANUAL = "MANUAL"

@dataclass
class IdentityEvidence:
    plate_evidence: Dict[str, Any] = field(default_factory=dict)
    reid_evidence: Dict[str, Any] = field(default_factory=dict)
    temporal_evidence: Dict[str, Any] = field(default_factory=dict)
    topology_evidence: Dict[str, Any] = field(default_factory=dict)
    consistency_evidence: Dict[str, Any] = field(default_factory=dict)
    hard_rejected: bool = False
    rejection_reason: Optional[str] = None
    score: float = 0.0
    candidate_vehicle_id: Optional[uuid.UUID] = None
    
    def to_dict(self) -> dict:
        return {
            "plate_evidence": self.plate_evidence,
            "reid_evidence": self.reid_evidence,
            "temporal_evidence": self.temporal_evidence,
            "topology_evidence": self.topology_evidence,
            "consistency_evidence": self.consistency_evidence,
            "hard_rejected": self.hard_rejected,
            "rejection_reason": self.rejection_reason,
            "score": self.score,
            "candidate_vehicle_id": str(self.candidate_vehicle_id) if self.candidate_vehicle_id else None
        }

@dataclass
class AssociationDecision:
    status: AssociationStatus
    confidence: float
    method: AssociationMethod
    vehicle_id: Optional[uuid.UUID] = None
    evidence: Optional[IdentityEvidence] = None

@dataclass
class ResolverCandidate:
    vehicle_id: uuid.UUID
    canonical_plate_text: Optional[str]
    canonical_vehicle_type: str
    last_detected_at: datetime
    last_junction_id: Optional[str] = None
    latest_appearance_embedding: Optional[List[float]] = None
    embedding_model: Optional[str] = None
    embedding_dimension: Optional[int] = None
