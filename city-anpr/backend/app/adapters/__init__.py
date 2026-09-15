"""
Adapters Package.
Re-exports all contract-to-model and ingestion adapters.
"""

from .ingestion import (
    IngestionBatch,
    IngestionResult,
    camera_contract_to_model,
    frame_result_to_batch,
    plate_observation_to_model,
    signal_decision_to_model,
    tracked_vehicle_to_model,
    traffic_snapshot_to_model,
)

__all__ = [
    "IngestionBatch",
    "IngestionResult",
    "frame_result_to_batch",
    "camera_contract_to_model",
    "tracked_vehicle_to_model",
    "plate_observation_to_model",
    "traffic_snapshot_to_model",
    "signal_decision_to_model",
]
