import datetime as dt
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models import BookingStatus


class FlightOut(BaseModel):
    id: UUID
    flight_number: str
    airline_code: str
    airline_name: str
    origin: str
    destination: str
    departure_time: dt.datetime
    arrival_time: dt.datetime
    total_seats: int
    available_seats: int
    price: Decimal
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime


class CreateBookingRequest(BaseModel):
    user_id: UUID
    flight_id: UUID
    passenger_name: str
    passenger_email: str
    seat_count: int


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    flight_id: UUID
    passenger_name: str
    passenger_email: str
    seat_count: int
    total_price: Decimal
    status: BookingStatus
    created_at: dt.datetime
    updated_at: dt.datetime


class FlightsQuery(BaseModel):
    origin: str
    destination: str
    date: dt.date | None = None
