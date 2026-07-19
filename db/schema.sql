CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    duration_min INTEGER NOT NULL,
    price_eur REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    services TEXT NOT NULL  -- JSON array of service IDs
);

CREATE TABLE IF NOT EXISTS slots (
    id INTEGER PRIMARY KEY,
    staff_id INTEGER NOT NULL REFERENCES staff(id),
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    service_id INTEGER NOT NULL REFERENCES services(id),
    booked INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY,
    slot_id INTEGER NOT NULL REFERENCES slots(id),
    client_name TEXT NOT NULL,
    client_phone TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    reminded INTEGER DEFAULT 0,
    cancelled INTEGER DEFAULT 0
);
