import uuid
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.vehicle import Vehicle
from backend.app.models.tracking import VehicleTrack
from backend.app.models.topology import TopologyEdge
from backend.app.models.camera import CameraModel
from backend.app.models.junction import JunctionApproach

from ai.identity.contracts import ResolverCandidate
from ai.identity.resolver import CandidateGenerator, MultimodalIdentityResolver

class SQLAlchemyCandidateGenerator(CandidateGenerator):
    def __init__(self, session: AsyncSession):
        self.session = session
        self.current_camera_junction_id = None
        
    async def get_candidates(
        self,
        plate_texts: List[str],
        current_camera_id: str,
        timestamp: datetime,
    ) -> List[ResolverCandidate]:
        
        # Determine current junction
        cam_stmt = select(CameraModel).options(selectinload(CameraModel.approach)).where(CameraModel.camera_id == current_camera_id)
        cam_res = await self.session.execute(cam_stmt)
        cam = cam_res.scalars().first()
        self.current_camera_junction_id = cam.approach.junction_id if cam and cam.approach else None
        
        conditions = []
        if plate_texts:
            conditions.append(Vehicle.canonical_plate_text.in_(plate_texts))
            
        # Add Spatio-Temporal condition (e.g. seen in last 10 minutes)
        # In a real system, we'd join with topology here.
        # For this prototype, we'll fetch recently seen vehicles.
        time_threshold = timestamp.timestamp() - 600  # 10 minutes
        recent_dt = datetime.fromtimestamp(time_threshold, tz=timezone.utc)
        conditions.append(Vehicle.last_detected_at >= recent_dt)
        
        stmt = (
            select(Vehicle)
            .options(selectinload(Vehicle.tracks).selectinload(VehicleTrack.camera).selectinload(CameraModel.approach))
            .where(or_(*conditions))
            .limit(100)
        )
        res = await self.session.execute(stmt)
        vehicles = res.scalars().all()
        
        candidates = []
        for v in vehicles:
            # Find the latest track for this vehicle to get junction and embedding
            last_junction_id = None
            latest_emb = None
            emb_model = None
            emb_dim = None
            
            if v.tracks:
                latest_track = sorted(v.tracks, key=lambda t: t.last_seen_at, reverse=True)[0]
                if latest_track.camera and latest_track.camera.approach:
                    last_junction_id = latest_track.camera.approach.junction_id
                latest_emb = latest_track.appearance_embedding
                emb_model = latest_track.embedding_model
                emb_dim = latest_track.embedding_dimension
                
            candidates.append(
                ResolverCandidate(
                    vehicle_id=v.vehicle_id,
                    canonical_plate_text=v.canonical_plate_text,
                    canonical_vehicle_type=v.canonical_vehicle_type,
                    last_detected_at=v.last_detected_at,
                    last_junction_id=last_junction_id,
                    latest_appearance_embedding=latest_emb,
                    embedding_model=emb_model,
                    embedding_dimension=emb_dim
                )
            )
            
        return candidates

    async def check_topology(
        self,
        source_junction_id: str,
        target_junction_id: str,
    ) -> Optional[dict]:
        if target_junction_id == "current_junction":
            target_junction_id = self.current_camera_junction_id
            
        if not target_junction_id or not source_junction_id:
            return None
            
        stmt = select(TopologyEdge).where(
            TopologyEdge.source_junction_id == source_junction_id,
            TopologyEdge.target_junction_id == target_junction_id,
            TopologyEdge.is_active == True
        )
        res = await self.session.execute(stmt)
        edge = res.scalars().first()
        
        if edge:
            return {
                "min_travel_time_sec": edge.min_travel_time_sec,
                "max_travel_time_sec": edge.max_travel_time_sec
            }
        return None
