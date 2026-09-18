import asyncio
from datetime import datetime, timezone, timedelta
from tests.test_trajectory_service import TrajectoryServiceTests

async def run():
    test = TrajectoryServiceTests()
    await test.asyncSetUp()
    
    t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    await test._add_track("CamA", 1, t1, plate="MH12AB1234")
    t2 = t1 + timedelta(seconds=90)
    await test._add_track("CamB", 2, t2, plate="MH12AB1234")
    t3 = t2 + timedelta(seconds=90)
    await test._add_track("CamC", 3, t3, plate="MH12AB1234")
    
    result = await test.service.stitch_unassociated_tracks()
    import json
    print("STRUCTURED TRANSITION EVENT:")
    print(json.dumps(result.events[1], indent=2))
    
    from sqlalchemy import select
    from backend.app.models.vehicle import Vehicle
    v_res = await test.session.execute(select(Vehicle))
    v = v_res.scalars().first()
    traj = await test.service.get_trajectory(v.vehicle_id)
    
    print("\nEXAMPLE A->B->C TRAJECTORY RESULT:")
    print(json.dumps(traj, indent=2))
    
    await test.asyncTearDown()

asyncio.run(run())
