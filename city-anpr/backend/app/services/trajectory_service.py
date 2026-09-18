import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc
from sqlalchemy.orm import selectinload

from backend.app.models.tracking import VehicleTrack
from backend.app.models.vehicle import Vehicle
from backend.app.models.observation import PlateObservationModel

from ai.identity.resolver import MultimodalIdentityResolver
from ai.contracts.models import TrackedVehicle, PlateObservation, AppearanceEmbedding

logger = logging.getLogger(__name__)

class TrajectoryService:
    def __init__(self, session: AsyncSession, resolver: MultimodalIdentityResolver):
        self.session = session
        self.resolver = resolver

    async def stitch_unassociated_tracks(self) -> int:
        """
        Attempt to associate completed/local VehicleTrack sessions from different cameras
        using the existing 3A.3 Identity Resolver.
        """
        stmt = (
            select(VehicleTrack)
            .where(VehicleTrack.association_status.is_(None))
            .options(
                selectinload(VehicleTrack.plate_observations),
                selectinload(VehicleTrack.camera)
            )
            .order_by(asc(VehicleTrack.last_seen_at))
        )
        res = await self.session.execute(stmt)
        unassociated_tracks = res.scalars().all()

        stitched_count = 0
        for track in unassociated_tracks:
            # Build AI contracts for the resolver
            ai_plates = []
            for p in track.plate_observations:
                ai_plates.append(PlateObservation(
                    plate_text=p.plate_text,
                    detection_confidence=p.detection_confidence,
                    ocr_confidence=p.ocr_confidence,
                    bbox=p.bbox,
                    timestamp=p.timestamp,
                    frame_number=p.frame_number,
                    camera_id=p.camera_id
                ))
                
            ai_embedding = None
            if track.appearance_embedding and track.embedding_model and track.embedding_dimension:
                ai_embedding = AppearanceEmbedding(
                    vector=track.appearance_embedding,
                    model_name=track.embedding_model,
                    dimension=track.embedding_dimension,
                    quality_score=track.embedding_quality
                )
                
            ai_track = TrackedVehicle(
                track_id=track.local_track_id,
                vehicle_type=track.vehicle_type,
                bbox=track.last_bbox,
                confidence=track.confidence,
                first_seen=track.first_seen_at,
                last_seen=track.last_seen_at,
                appearance_embedding=ai_embedding,
                camera_id=track.camera_id
            )
            
            # Use the Identity Resolver
            decision = await self.resolver.resolve(
                track=ai_track,
                plates=ai_plates,
                camera_id=track.camera_id,
                timestamp=track.last_seen_at
            )
            
            # Apply decision
            track.association_status = decision.status.value
            track.association_confidence = decision.confidence
            track.association_method = decision.method.value
            if decision.evidence:
                track.association_evidence = decision.evidence.to_dict()
                
            # Only PROBABLE or MATCHED are associated to global identities
            if decision.status.value in ("MATCHED", "PROBABLE"):
                track.vehicle_id = decision.vehicle_id
                stitched_count += 1
                
                if decision.vehicle_id:
                    v_stmt = select(Vehicle).where(Vehicle.vehicle_id == decision.vehicle_id)
                    v_res = await self.session.execute(v_stmt)
                    vehicle = v_res.scalars().first()
                    
                    if vehicle:
                        vehicle.last_detected_at = max(vehicle.last_detected_at, track.last_seen_at)
                        vehicle.total_detections_count += 1
                        
                        logger.info(f"Vehicle {vehicle.vehicle_id} arrived at Camera {track.camera_id}")

            elif decision.status.value == "NEW_VEHICLE":
                canonical_plate = ai_plates[0].plate_text if ai_plates else None
                v = Vehicle(
                    canonical_plate_text=canonical_plate,
                    canonical_vehicle_type=track.vehicle_type,
                    first_detected_at=track.first_seen_at,
                    last_detected_at=track.last_seen_at,
                    total_detections_count=1
                )
                self.session.add(v)
                await self.session.flush()
                track.vehicle_id = v.vehicle_id
                stitched_count += 1
                logger.info(f"New Vehicle {v.vehicle_id} started trajectory at Camera {track.camera_id}")
                
        await self.session.commit()
        return stitched_count

    async def get_trajectory(self, vehicle_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """
        Builds a chronological trajectory representation for a Vehicle.
        """
        v_stmt = (
            select(Vehicle)
            .options(
                selectinload(Vehicle.tracks).selectinload(VehicleTrack.camera)
            )
            .where(Vehicle.vehicle_id == vehicle_id)
        )
        v_res = await self.session.execute(v_stmt)
        vehicle = v_res.scalars().first()
        
        if not vehicle:
            return None
            
        # Order tracks chronologically
        tracks = sorted(vehicle.tracks, key=lambda t: t.first_seen_at)
        
        journey = []
        for i, t in enumerate(tracks):
            journey.append({
                "sequence": i + 1,
                "camera_id": t.camera_id,
                "camera_name": t.camera.name if t.camera else None,
                "junction_id": t.junction_id,
                "junction_name": t.junction_name,
                "local_track_id": t.local_track_id,
                "first_seen_at": t.first_seen_at.isoformat(),
                "last_seen_at": t.last_seen_at.isoformat(),
                "association_status": t.association_status,
                "association_method": t.association_method,
                "association_confidence": t.association_confidence,
            })
            
        return {
            "vehicle_id": str(vehicle.vehicle_id),
            "canonical_plate": vehicle.canonical_plate_text,
            "vehicle_type": vehicle.canonical_vehicle_type,
            "journey": journey
        }
