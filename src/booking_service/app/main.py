from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import grpc
from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.grpc_client import FlightGrpcError, flight_client
from app.models import Booking, BookingStatus
from app.schemas import BookingOut, CreateBookingRequest, FlightOut
from fastapi.responses import JSONResponse
from app.circuit_breaker import CircuitBreakerOpenError

app = FastAPI(title="Booking Service", version="1.0.0")


@app.exception_handler(CircuitBreakerOpenError)
def circuit_breaker_open_handler(request, exc: CircuitBreakerOpenError):
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)},
    )


def map_grpc_error(exc: FlightGrpcError) -> HTTPException:
    if exc.code == grpc.StatusCode.NOT_FOUND:
        return HTTPException(status_code=404, detail=exc.details)

    if exc.code in {
        grpc.StatusCode.RESOURCE_EXHAUSTED,
        grpc.StatusCode.FAILED_PRECONDITION,
        grpc.StatusCode.ALREADY_EXISTS,
    }:
        return HTTPException(status_code=409, detail=exc.details)

    if exc.code == grpc.StatusCode.INVALID_ARGUMENT:
        return HTTPException(status_code=400, detail=exc.details)

    if exc.code in {grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED}:
        return HTTPException(status_code=503, detail="Flight Service is unavailable")

    if exc.code == grpc.StatusCode.UNAUTHENTICATED:
        return HTTPException(
            status_code=502, detail="inter-service authentication failed"
        )

    return HTTPException(status_code=500, detail=exc.details)


@app.get("/flights", response_model=list[FlightOut])
def search_flights(
    origin: str = Query(..., min_length=3, max_length=3),
    destination: str = Query(..., min_length=3, max_length=3),
    date: str | None = Query(default=None),
):
    parsed_date = None
    if date is not None:
        try:
            from datetime import date as dt_date

            parsed_date = dt_date.fromisoformat(date)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="date must be in YYYY-MM-DD format"
            ) from exc
    try:
        flights = flight_client.search_flights(
            origin=origin, destination=destination, flight_date=parsed_date
        )
        return [FlightOut(**flight.__dict__) for flight in flights]
    except FlightGrpcError as exc:
        raise map_grpc_error(exc)


@app.get("/flights/{flight_id}", response_model=FlightOut)
def get_flight(flight_id: UUID):
    try:
        flight = flight_client.get_flight(flight_id)
        return FlightOut(**flight.__dict__)
    except FlightGrpcError as exc:
        raise map_grpc_error(exc)


@app.post("/bookings", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(payload: CreateBookingRequest, db: Session = Depends(get_db)):
    booking_id = uuid4()

    try:
        flight = flight_client.get_flight(payload.flight_id)
        flight_client.reserve_seats(
            booking_id=booking_id,
            flight_id=payload.flight_id,
            seat_count=payload.seat_count,
        )
    except FlightGrpcError as exc:
        raise map_grpc_error(exc)

    total_price = (flight.price * Decimal(payload.seat_count)).quantize(Decimal("0.01"))
    booking = Booking(
        id=booking_id,
        user_id=payload.user_id,
        flight_id=payload.flight_id,
        passenger_name=payload.passenger_name,
        passenger_email=payload.passenger_email,
        seat_count=payload.seat_count,
        total_price=total_price,
        status=BookingStatus.CONFIRMED,
    )

    try:
        with db.begin():
            db.add(booking)
        db.refresh(booking)
        return booking
    except Exception as exc:
        try:
            flight_client.release_reservation(booking_id)
        except FlightGrpcError:
            pass
        raise HTTPException(
            status_code=500, detail="failed to persist booking"
        ) from exc


@app.get("/bookings/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: UUID, db: Session = Depends(get_db)):
    booking = db.scalar(select(Booking).where(Booking.id == booking_id))
    if booking is None:
        raise HTTPException(status_code=404, detail="booking not found")
    return booking


@app.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(booking_id: UUID, db: Session = Depends(get_db)):
    booking = db.scalar(select(Booking).where(Booking.id == booking_id))
    if booking is None:
        raise HTTPException(status_code=404, detail="booking not found")
    if booking.status != BookingStatus.CONFIRMED:
        raise HTTPException(
            status_code=409, detail="booking is not in CONFIRMED status"
        )

    try:
        flight_client.release_reservation(booking.id)
    except FlightGrpcError as exc:
        raise map_grpc_error(exc)

    booking.status = BookingStatus.CANCELLED
    booking.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(booking)
    return booking


@app.get("/bookings", response_model=list[BookingOut])
def list_bookings(user_id: UUID = Query(...), db: Session = Depends(get_db)):
    bookings = db.scalars(
        select(Booking)
        .where(Booking.user_id == user_id)
        .order_by(Booking.created_at.desc())
    ).all()
    return list(bookings)
