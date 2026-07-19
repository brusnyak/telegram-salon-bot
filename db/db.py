import json
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

DB_PATH = Path(__file__).parent / "salon.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


async def init_db():
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        with open(SCHEMA_PATH) as f:
            await db.executescript(f.read())
        await db.commit()
    await seed_if_empty()


@asynccontextmanager
async def get_db():
    conn = await aiosqlite.connect(str(DB_PATH))
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
    finally:
        await conn.close()


async def seed_if_empty():
    async with get_db() as db:
        services_count = await db.execute_fetchall("SELECT COUNT(*) as c FROM services")
        staff_count = await db.execute_fetchall("SELECT COUNT(*) as c FROM staff")
        slots_count = await db.execute_fetchall("SELECT COUNT(*) as c FROM slots")
        if services_count[0][0] > 0 and staff_count[0][0] > 0 and slots_count[0][0] > 0:
            return

        await db.execute("DELETE FROM bookings")
        await db.execute("DELETE FROM slots")
        await db.execute("DELETE FROM staff")
        await db.execute("DELETE FROM services")

        services = [
            (1, "Haircut", 30, 25.0),
            (2, "Colouring", 90, 55.0),
            (3, "Nails", 45, 30.0),
            (4, "Massage", 60, 40.0),
        ]
        await db.executemany("INSERT INTO services VALUES (?,?,?,?)", services)

        staff = [
            (1, "Lucia", json.dumps([1, 2])),
            (2, "Martina", json.dumps([1, 3, 4])),
            (3, "Eva", json.dumps([2, 4])),
        ]
        await db.executemany("INSERT INTO staff VALUES (?,?,?)", staff)

        # Generate slots: today + next 6 days, 10:00-17:00 hourly
        import datetime

        base = datetime.date.today()
        slots = []
        slot_id = 1
        for day_offset in range(7):
            d = (base + datetime.timedelta(days=day_offset)).isoformat()
            for staff_id in range(1, 4):
                for hour in range(10, 17):
                    for svc in [1, 2, 3, 4]:
                        if svc not in json.loads(staff[staff_id - 1][2]):
                            continue
                        slots.append((slot_id, staff_id, d, f"{hour:02d}:00", svc, 0))
                        slot_id += 1
        await db.executemany("INSERT INTO slots VALUES (?,?,?,?,?,?)", slots)
        await db.commit()
