INSERT INTO airlines (id, code, name) VALUES
('11111111-1111-1111-1111-111111111111', 'SU', 'Aeroflot'),
('22222222-2222-2222-2222-222222222222', 'DP', 'Pobeda');

INSERT INTO airports (code, name, city, country) VALUES
('SVO', 'Sheremetyevo International Airport', 'Moscow', 'Russia'),
('VKO', 'Vnukovo International Airport', 'Moscow', 'Russia'),
('LED', 'Pulkovo Airport', 'Saint Petersburg', 'Russia'),
('KZN', 'Kazan International Airport', 'Kazan', 'Russia');

INSERT INTO flights (
  id,
  flight_number,
  airline_id,
  departure_airport_code,
  arrival_airport_code,
  departure_time,
  arrival_time,
  total_seats,
  available_seats,
  price,
  status
) VALUES
(
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  'SU1234',
  '11111111-1111-1111-1111-111111111111',
  'SVO',
  'LED',
  '2026-04-01T09:00:00Z',
  '2026-04-01T10:30:00Z',
  180,
  180,
  5500.00,
  'SCHEDULED'
),
(
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  'DP2001',
  '22222222-2222-2222-2222-222222222222',
  'VKO',
  'LED',
  '2026-04-01T12:00:00Z',
  '2026-04-01T13:25:00Z',
  189,
  189,
  4200.00,
  'SCHEDULED'
),
(
  'cccccccc-cccc-cccc-cccc-cccccccccccc',
  'SU1450',
  '11111111-1111-1111-1111-111111111111',
  'SVO',
  'KZN',
  '2026-04-01T15:00:00Z',
  '2026-04-01T16:40:00Z',
  160,
  160,
  6100.00,
  'SCHEDULED'
);
