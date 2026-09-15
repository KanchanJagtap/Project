"""Initial database foundation for all 8 core tables

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-15 14:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. junctions
    op.create_table(
        'junctions',
        sa.Column('junction_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('target_cycle_seconds', sa.Integer(), nullable=False, server_default='120'),
        sa.Column('min_green_seconds', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('max_green_seconds', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='NORMAL'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('junction_id')
    )

    # 2. cameras
    op.create_table(
        'cameras',
        sa.Column('camera_id', sa.String(length=64), nullable=False),
        sa.Column('source', sa.String(length=512), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=True),
        sa.Column('resolution_width', sa.Integer(), nullable=True),
        sa.Column('resolution_height', sa.Integer(), nullable=True),
        sa.Column('fps', sa.Float(), nullable=True),
        sa.Column('queue_roi', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=True),
        sa.Column('lane_configuration', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
        sa.Column('direction_configuration', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('camera_id')
    )

    # 3. junction_approaches
    op.create_table(
        'junction_approaches',
        sa.Column('approach_id', sa.String(length=64), nullable=False),
        sa.Column('junction_id', sa.String(length=64), nullable=False),
        sa.Column('camera_id', sa.String(length=64), nullable=True),
        sa.Column('direction_name', sa.String(length=64), nullable=False),
        sa.Column('cardinal_direction', sa.String(length=16), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['camera_id'], ['cameras.camera_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['junction_id'], ['junctions.junction_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('approach_id'),
        sa.UniqueConstraint('camera_id')
    )

    # 4. vehicles
    op.create_table(
        'vehicles',
        sa.Column('vehicle_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('canonical_plate_text', sa.String(length=32), nullable=True),
        sa.Column('canonical_vehicle_type', sa.String(length=20), nullable=False),
        sa.Column('first_detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_detections_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_stolen', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_wanted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('notes', sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint('vehicle_id')
    )
    op.create_index(
        'uq_vehicles_canonical_plate',
        'vehicles',
        ['canonical_plate_text'],
        unique=True,
        postgresql_where=sa.text('canonical_plate_text IS NOT NULL'),
        sqlite_where=sa.text('canonical_plate_text IS NOT NULL')
    )
    op.create_index('idx_vehicles_last_detected', 'vehicles', ['last_detected_at'])

    # 5. vehicle_tracks
    op.create_table(
        'vehicle_tracks',
        sa.Column('track_session_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('vehicle_id', sa.Uuid(as_uuid=True), nullable=True),
        sa.Column('camera_id', sa.String(length=64), nullable=False),
        sa.Column('local_track_id', sa.Integer(), nullable=False),
        sa.Column('vehicle_type', sa.String(length=20), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('best_confidence', sa.Float(), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('first_seen_frame', sa.Integer(), nullable=False),
        sa.Column('last_seen_frame', sa.Integer(), nullable=False),
        sa.Column('frames_tracked', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('last_bbox', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
        sa.Column('center', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=True),
        sa.Column('trajectory_summary', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
        sa.Column('type_history', sa.ARRAY(sa.String()).with_variant(sa.JSON(), 'sqlite'), nullable=False),
        sa.ForeignKeyConstraint(['camera_id'], ['cameras.camera_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.vehicle_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('track_session_id')
    )
    op.create_index('idx_tracks_camera_time', 'vehicle_tracks', ['camera_id', 'last_seen_at'])
    op.create_index('idx_tracks_vehicle_id', 'vehicle_tracks', ['vehicle_id'])
    op.create_index('idx_tracks_local_active', 'vehicle_tracks', ['camera_id', 'local_track_id', 'last_seen_frame'])

    # 6. plate_observations
    op.create_table(
        'plate_observations',
        sa.Column('observation_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('plate_text', sa.String(length=32), nullable=False),
        sa.Column('raw_plate_text', sa.String(length=64), nullable=True),
        sa.Column('camera_id', sa.String(length=64), nullable=False),
        sa.Column('track_session_id', sa.Uuid(as_uuid=True), nullable=True),
        sa.Column('vehicle_id', sa.Uuid(as_uuid=True), nullable=True),
        sa.Column('frame_number', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('detection_confidence', sa.Float(), nullable=False),
        sa.Column('ocr_confidence', sa.Float(), nullable=False),
        sa.Column('association_confidence', sa.Float(), nullable=True),
        sa.Column('bbox', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
        sa.Column('vehicle_bbox', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=True),
        sa.Column('crop_image_uri', sa.String(length=512), nullable=True),
        sa.Column('ocr_variant', sa.String(length=32), nullable=True),
        sa.Column('coordinate_space', sa.String(length=32), nullable=False, server_default='frame'),
        sa.ForeignKeyConstraint(['camera_id'], ['cameras.camera_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['track_session_id'], ['vehicle_tracks.track_session_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.vehicle_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('observation_id')
    )
    op.create_index('idx_plate_obs_plate_text', 'plate_observations', ['plate_text'])
    op.create_index('idx_plate_obs_camera_time', 'plate_observations', ['camera_id', 'timestamp'])
    op.create_index('idx_plate_obs_track_session', 'plate_observations', ['track_session_id'])
    op.create_index('idx_plate_obs_vehicle_id', 'plate_observations', ['vehicle_id'])

    # 7. traffic_snapshots
    op.create_table(
        'traffic_snapshots',
        sa.Column('snapshot_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('camera_id', sa.String(length=64), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('frame_number', sa.Integer(), nullable=True),
        sa.Column('active_vehicle_count', sa.Integer(), nullable=False),
        sa.Column('queue_length', sa.Integer(), nullable=False),
        sa.Column('moving_vehicles', sa.Integer(), nullable=False),
        sa.Column('slow_vehicles', sa.Integer(), nullable=False),
        sa.Column('stationary_vehicles', sa.Integer(), nullable=False),
        sa.Column('traffic_pressure', sa.Float(), nullable=False),
        sa.Column('traffic_level', sa.String(length=16), nullable=False),
        sa.Column('metrics', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
        sa.ForeignKeyConstraint(['camera_id'], ['cameras.camera_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('snapshot_id')
    )
    op.create_index('idx_snapshots_camera_time', 'traffic_snapshots', ['camera_id', 'timestamp'])
    op.create_index('idx_snapshots_level', 'traffic_snapshots', ['traffic_level'])

    # 8. signal_decisions
    op.create_table(
        'signal_decisions',
        sa.Column('decision_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('junction_id', sa.String(length=64), nullable=False),
        sa.Column('approach_id', sa.String(length=64), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('priority_score', sa.Float(), nullable=False),
        sa.Column('green_time', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=256), nullable=False),
        sa.Column('is_emergency_override', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(['approach_id'], ['junction_approaches.approach_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['junction_id'], ['junctions.junction_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('decision_id')
    )
    op.create_index('idx_signals_junction_time', 'signal_decisions', ['junction_id', 'timestamp'])
    op.create_index('idx_signals_approach_time', 'signal_decisions', ['approach_id', 'timestamp'])


def downgrade() -> None:
    op.drop_table('signal_decisions')
    op.drop_table('traffic_snapshots')
    op.drop_table('plate_observations')
    op.drop_table('vehicle_tracks')
    op.drop_table('vehicles')
    op.drop_table('junction_approaches')
    op.drop_table('cameras')
    op.drop_table('junctions')
