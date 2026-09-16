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
        
        # 1. Resolve current junction dynamically
        cam_stmt = select(CameraModel).options(selectinload(CameraModel.approach)).where(CameraModel.camera_id == current_camera_id)
        cam_res = await self.session.execute(cam_stmt)
        cam = cam_res.scalars().first()
        self.current_camera_junction_id = cam.approach.junction_id if cam and cam.approach else None
        
        # 2. Get active incoming edges to this junction
        valid_source_junctions = []
        if self.current_camera_junction_id:
            edge_stmt = select(TopologyEdge.source_junction_id).where(
                TopologyEdge.target_junction_id == self.current_camera_junction_id,
                TopologyEdge.is_active == True
            )
            edge_res = await self.session.execute(edge_stmt)
            valid_source_junctions = [r for r in edge_res.scalars().all()]
            
        # 3. Explicitly bounded constraints
        conditions = []
        # A. Exact Plate
        if plate_texts:
            conditions.append(Vehicle.canonical_plate_text.in_(plate_texts))
            
        # B. Topology-linked recent vehicles
        if valid_source_junctions:
            # Approx max travel time in the city could be 30 mins
            time_threshold = timestamp.timestamp() - 1800
            recent_dt = datetime.fromtimestamp(time_threshold, tz=timezone.utc)
            
            # We would join on VehicleTrack to verify last_junction_id in valid_source_junctions
            # For simplicity in this demo, we approximate by recent detection and we filter manually later.
            conditions.append(
                Vehicle.last_detected_at >= recent_dt
            )
            
        # C. Re-ID Retrieval
        # (Explicitly omitted/abstracted because DB does not support pgvector yet)
        
        if not conditions:
            return []
            
        stmt = (
            select(Vehicle)
            .options(selectinload(Vehicle.tracks).selectinload(VehicleTrack.camera).selectinload(CameraModel.approach))
            .where(or_(*conditions))
        )
        res = await self.session.execute(stmt)
        vehicles = res.scalars().all()
        
        candidates = []
        for v in vehicles:
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
                
            # If fetched via recent_dt, enforce the spatial constraint now
            if not plate_texts or v.canonical_plate_text not in plate_texts:
                if last_junction_id not in valid_source_junctions:
                    continue # Discard conceptually unbounded candidates
                    
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
        target_camera_id: str,
    ) -> Optional[dict]:
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
