CREATE TABLE IF NOT EXISTS inventory (
    event_id INTEGER PRIMARY KEY,
    event_name VARCHAR(120) NOT NULL,
    available_seats INTEGER NOT NULL CHECK (available_seats >= 0)
);

CREATE TABLE IF NOT EXISTS reservations (
    id UUID PRIMARY KEY,
    event_id INTEGER NOT NULL,
    email VARCHAR(255) NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    status VARCHAR(30) NOT NULL,
    notification_status VARCHAR(30) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO inventory (event_id, event_name, available_seats)
VALUES (1, 'Concierto de prueba', 10)
ON CONFLICT (event_id) DO NOTHING;
