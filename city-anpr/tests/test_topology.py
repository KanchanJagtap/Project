"""
Tests for 3A.1 Camera Topology Foundation.
"""

import uuid
from datetime import datetime, timezone
import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from backend.app.db.base import Base
from backend.app.models.junction import Junction
from backend.app.models.topology import TopologyEdge
from backend.app.main import app
from backend.app.db.session import get_db

@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Dependency override
    async def override_get_db():
        async with session_factory() as session:
            yield session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with session_factory() as session:
        # Create junctions
        j1 = Junction(junction_id="j1", name="Junction 1")
        j2 = Junction(junction_id="j2", name="Junction 2")
        session.add_all([j1, j2])
        await session.commit()
        yield session

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_topology_edge_creation_and_relationships(db_session):
    """1. Create edge and 2. test Junction relationships and 3,4,5. test persistence."""
    edge = TopologyEdge(
        source_junction_id="j1",
        target_junction_id="j2",
        distance_meters=500.0,
        min_travel_time_sec=30.0,
        max_travel_time_sec=120.0,
        is_active=True
    )
    db_session.add(edge)
    await db_session.commit()
    
    # Test relationships
    stmt_edges = select(TopologyEdge)
    res_edges = await db_session.execute(stmt_edges)
    edges = res_edges.scalars().all()
    assert len(edges) == 1
    e = edges[0]
    assert e.distance_meters == 500.0
    assert e.min_travel_time_sec == 30.0
    assert e.max_travel_time_sec == 120.0
    assert e.is_active is True

@pytest.mark.asyncio
async def test_topology_self_loop_rejection(db_session):
    """6. Self-loop rejection via db constraint."""
    edge = TopologyEdge(
        source_junction_id="j1",
        target_junction_id="j1", # Self loop
        distance_meters=100.0,
        min_travel_time_sec=10.0,
        max_travel_time_sec=20.0,
    )
    db_session.add(edge)
    with pytest.raises(IntegrityError):
        await db_session.commit()

@pytest.mark.asyncio
async def test_topology_invalid_travel_time_rejection(db_session):
    """7. Invalid travel-time range rejection via db constraint."""
    edge = TopologyEdge(
        source_junction_id="j1",
        target_junction_id="j2",
        distance_meters=100.0,
        min_travel_time_sec=20.0,
        max_travel_time_sec=10.0, # Max < Min
    )
    db_session.add(edge)
    with pytest.raises(IntegrityError):
        await db_session.commit()

@pytest.mark.asyncio
async def test_topology_invalid_distance(db_session):
    """7b. Invalid distance via db constraint."""
    edge = TopologyEdge(
        source_junction_id="j1",
        target_junction_id="j2",
        distance_meters=-5.0, # Negative distance
        min_travel_time_sec=10.0,
        max_travel_time_sec=20.0,
    )
    db_session.add(edge)
    with pytest.raises(IntegrityError):
        await db_session.commit()

@pytest.mark.asyncio
async def test_topology_api_response(db_session):
    """8. API response test."""
    edge = TopologyEdge(
        source_junction_id="j1",
        target_junction_id="j2",
        distance_meters=500.0,
        min_travel_time_sec=30.0,
        max_travel_time_sec=120.0,
        is_active=True
    )
    db_session.add(edge)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/topology/edges")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 1
        edge_data = next((e for e in data if e["source_junction_id"] == "j1" and e["target_junction_id"] == "j2"), None)
        assert edge_data is not None
        assert edge_data["distance_meters"] == 500.0
