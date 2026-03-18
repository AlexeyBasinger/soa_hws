CREATE TYPE flight_status AS ENUM (
  'SCHEDULED',
  'DELAYED',
  'CANCELLED',
  'DEPARTED',
  'COMPLETED'
);

CREATE TYPE seat_reservation_status AS ENUM (
  'ACTIVE',
  'RELEASED',
  'EXPIRED'
);

CREATE TABLE airlines (
  id UUID PRIMARY KEY,
  code VARCHAR(8) NOT NULL UNIQUE,
  name VARCHAR(255) NOT NULL
);

CREATE TABLE airports (
  code CHAR(3) PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  city VARCHAR(100) NOT NULL,
  country VARCHAR(100) NOT NULL
);

CREATE TABLE flights (
  id UUID PRIMARY KEY,
  flight_number VARCHAR(16) NOT NULL,
  airline_id UUID NOT NULL REFERENCES airlines(id),
  departure_airport_code CHAR(3) NOT NULL REFERENCES airports(code),
  arrival_airport_code CHAR(3) NOT NULL REFERENCES airports(code),
  departure_time TIMESTAMPTZ NOT NULL,
  arrival_time TIMESTAMPTZ NOT NULL,
  total_seats INT NOT NULL CHECK (total_seats > 0),
  available_seats INT NOT NULL CHECK (available_seats >= 0 AND available_seats <= total_seats),
  price NUMERIC(12,2) NOT NULL CHECK (price > 0),
  status flight_status NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT chk_arrival_after_departure CHECK (arrival_time > departure_time),
  CONSTRAINT chk_different_airports CHECK (departure_airport_code <> arrival_airport_code)
);

CREATE UNIQUE INDEX uq_flights_number_departure_date
  ON flights (flight_number, ((departure_time AT TIME ZONE 'UTC')::date));

CREATE INDEX idx_flights_search
  ON flights (departure_airport_code, arrival_airport_code, departure_time);

CREATE TABLE seat_reservations (
  id UUID PRIMARY KEY,
  flight_id UUID NOT NULL REFERENCES flights(id) ON DELETE CASCADE,
  booking_id UUID NOT NULL UNIQUE,
  seats INT NOT NULL CHECK (seats > 0),
  status seat_reservation_status NOT NULL,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_seat_reservations_flight_status
  ON seat_reservations (flight_id, status);
