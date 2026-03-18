from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

import flight_service_pb2 as pb2
import flight_service_pb2_grpc as pb2_grpc
from app.cache import (
    cache_get_json,
    cache_set_json,
    flight_cache_key,
    invalidate_flight_cache,
    remember_search_key_for_flight,
    search_cache_key,
)
from app.config import settings
from app.db import SessionLocal
from app.models import Flight, FlightStatus, ReservationStatus, SeatReservation

logger = logging.getLogger(__name__)

PROTO_FLIGHT_STATUS = {
    FlightStatus.SCHEDULED: pb2.FLIGHT_STATUS_SCHEDULED,
    FlightStatus.DELAYED: pb2.FLIGHT_STATUS_DELAYED,
    FlightStatus.CANCELLED: pb2.FLIGHT_STATUS_CANCELLED,
    FlightStatus.DEPARTED: pb2.FLIGHT_STATUS_DEPARTED,
    FlightStatus.COMPLETED: pb2.FLIGHT_STATUS_COMPLETED,
}

PROTO_RESERVATION_STATUS = {
    ReservationStatus.ACTIVE: pb2.RESERVATION_STATUS_ACTIVE,
    ReservationStatus.RELEASED: pb2.RESERVATION_STATUS_RELEASED,
    ReservationStatus.EXPIRED: pb2.RESERVATION_STATUS_EXPIRED,
}

STATUS_NAME_TO_PROTO = {
    "SCHEDULED": pb2.FLIGHT_STATUS_SCHEDULED,
    "DELAYED": pb2.FLIGHT_STATUS_DELAYED,
    "CANCELLED": pb2.FLIGHT_STATUS_CANCELLED,
    "DEPARTED": pb2.FLIGHT_STATUS_DEPARTED,
    "COMPLETED": pb2.FLIGHT_STATUS_COMPLETED,
}


def require_auth(context: grpc.ServicerContext) -> None:
    metadata = dict(context.invocation_metadata())
    api_key = metadata.get("x-api-key")
    if not api_key or api_key != settings.grpc_api_key:
        context.abort(
            grpc.StatusCode.UNAUTHENTICATED, "missing or invalid service credentials"
        )


def dt_to_ts(value: datetime | None) -> Timestamp:
    ts = Timestamp()
    if value is None:
        return ts
    ts.FromDatetime(value.astimezone(timezone.utc).replace(tzinfo=timezone.utc))
    return ts


def flight_to_proto(flight: Flight) -> pb2.Flight:
    return pb2.Flight(
        id=str(flight.id),
        flight_number=flight.flight_number,
        airline_code=flight.airline.code,
        airline_name=flight.airline.name,
        origin=flight.departure_airport_code,
        destination=flight.arrival_airport_code,
        departure_time=dt_to_ts(flight.departure_time),
        arrival_time=dt_to_ts(flight.arrival_time),
        total_seats=flight.total_seats,
        available_seats=flight.available_seats,
        price=str(flight.price),
        status=PROTO_FLIGHT_STATUS[flight.status],
        created_at=dt_to_ts(flight.created_at),
        updated_at=dt_to_ts(flight.updated_at),
    )


def reservation_to_proto(reservation: SeatReservation) -> pb2.SeatReservation:
    return pb2.SeatReservation(
        id=str(reservation.id),
        booking_id=str(reservation.booking_id),
        flight_id=str(reservation.flight_id),
        seats=reservation.seats,
        status=PROTO_RESERVATION_STATUS[reservation.status],
        expires_at=dt_to_ts(reservation.expires_at),
        created_at=dt_to_ts(reservation.created_at),
        updated_at=dt_to_ts(reservation.updated_at),
    )


def flight_to_cache_dict(flight: Flight) -> dict:
    return {
        "id": str(flight.id),
        "flight_number": flight.flight_number,
        "airline_code": flight.airline.code,
        "airline_name": flight.airline.name,
        "origin": flight.departure_airport_code,
        "destination": flight.arrival_airport_code,
        "departure_time": flight.departure_time.isoformat(),
        "arrival_time": flight.arrival_time.isoformat(),
        "total_seats": flight.total_seats,
        "available_seats": flight.available_seats,
        "price": str(flight.price),
        "status": flight.status.value,
        "created_at": flight.created_at.isoformat(),
        "updated_at": flight.updated_at.isoformat(),
    }


def flight_dict_to_proto(data: dict) -> pb2.Flight:
    return pb2.Flight(
        id=data["id"],
        flight_number=data["flight_number"],
        airline_code=data["airline_code"],
        airline_name=data["airline_name"],
        origin=data["origin"],
        destination=data["destination"],
        departure_time=dt_to_ts(datetime.fromisoformat(data["departure_time"])),
        arrival_time=dt_to_ts(datetime.fromisoformat(data["arrival_time"])),
        total_seats=int(data["total_seats"]),
        available_seats=int(data["available_seats"]),
        price=str(data["price"]),
        status=STATUS_NAME_TO_PROTO[data["status"]],
        created_at=dt_to_ts(datetime.fromisoformat(data["created_at"])),
        updated_at=dt_to_ts(datetime.fromisoformat(data["updated_at"])),
    )


class FlightService(pb2_grpc.FlightServiceServicer):
    def SearchFlights(
        self, request: pb2.SearchFlightsRequest, context: grpc.ServicerContext
    ) -> pb2.SearchFlightsResponse:
        require_auth(context)

        origin = request.origin.strip().upper()
        destination = request.destination.strip().upper()
        if not origin or not destination:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "origin and destination are required"
            )

        date_token = "all"
        if request.HasField("departure_from"):
            date_token = (
                request.departure_from.ToDatetime(tzinfo=timezone.utc)
                .date()
                .isoformat()
            )

        key = search_cache_key(origin, destination, date_token)
        cached = cache_get_json(key)
        if cached is not None:
            return pb2.SearchFlightsResponse(
                flights=[flight_dict_to_proto(item) for item in cached]
            )

        with SessionLocal() as session:
            stmt = (
                select(Flight)
                .options(joinedload(Flight.airline))
                .where(
                    Flight.departure_airport_code == origin,
                    Flight.arrival_airport_code == destination,
                    Flight.status == FlightStatus.SCHEDULED,
                )
                .order_by(Flight.departure_time.asc())
            )

            if request.HasField("departure_from"):
                stmt = stmt.where(
                    Flight.departure_time
                    >= request.departure_from.ToDatetime(tzinfo=timezone.utc)
                )
            if request.HasField("departure_to"):
                stmt = stmt.where(
                    Flight.departure_time
                    < request.departure_to.ToDatetime(tzinfo=timezone.utc)
                )

            flights = session.scalars(stmt).all()
            payload = [flight_to_cache_dict(f) for f in flights]

            cache_set_json(key, payload)
            for item in payload:
                remember_search_key_for_flight(item["id"], key)

            return pb2.SearchFlightsResponse(
                flights=[flight_dict_to_proto(item) for item in payload]
            )

    def GetFlight(
        self, request: pb2.GetFlightRequest, context: grpc.ServicerContext
    ) -> pb2.GetFlightResponse:
        require_auth(context)

        try:
            flight_id = uuid.UUID(request.flight_id)
        except ValueError:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "flight_id must be a valid UUID"
            )

        key = flight_cache_key(str(flight_id))
        cached = cache_get_json(key)
        if cached is not None:
            return pb2.GetFlightResponse(flight=flight_dict_to_proto(cached))

        with SessionLocal() as session:
            stmt = (
                select(Flight)
                .options(joinedload(Flight.airline))
                .where(Flight.id == flight_id)
            )
            flight = session.scalar(stmt)
            if flight is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "flight not found")

            payload = flight_to_cache_dict(flight)
            cache_set_json(key, payload)

            return pb2.GetFlightResponse(flight=flight_dict_to_proto(payload))

    def ReserveSeats(
        self, request: pb2.ReserveSeatsRequest, context: grpc.ServicerContext
    ) -> pb2.ReserveSeatsResponse:
        require_auth(context)

        if not request.booking_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "booking_id is required")
        if request.seat_count <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "seat_count must be > 0")

        try:
            booking_id = uuid.UUID(request.booking_id)
            flight_id = uuid.UUID(request.flight_id)
        except ValueError:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "booking_id and flight_id must be valid UUIDs",
            )

        with SessionLocal() as session:
            try:
                with session.begin():
                    existing = session.scalar(
                        select(SeatReservation).where(
                            SeatReservation.booking_id == booking_id
                        )
                    )
                    if existing is not None:
                        if (
                            existing.flight_id == flight_id
                            and existing.seats == request.seat_count
                            and existing.status == ReservationStatus.ACTIVE
                        ):
                            flight = session.scalar(
                                select(Flight).where(Flight.id == existing.flight_id)
                            )
                            if flight is None:
                                context.abort(
                                    grpc.StatusCode.NOT_FOUND, "flight not found"
                                )

                            return pb2.ReserveSeatsResponse(
                                reservation=reservation_to_proto(existing),
                                remaining_available_seats=flight.available_seats,
                            )

                        context.abort(
                            grpc.StatusCode.ALREADY_EXISTS,
                            "reservation for this booking already exists with different parameters",
                        )
                    flight = session.scalar(
                        select(Flight).where(Flight.id == flight_id).with_for_update()
                    )
                    if flight is None:
                        context.abort(grpc.StatusCode.NOT_FOUND, "flight not found")
                    if flight.status != FlightStatus.SCHEDULED:
                        context.abort(
                            grpc.StatusCode.FAILED_PRECONDITION,
                            "flight is not available for booking",
                        )
                    if flight.available_seats < request.seat_count:
                        context.abort(
                            grpc.StatusCode.RESOURCE_EXHAUSTED,
                            "not enough seats available",
                        )

                    reservation = SeatReservation(
                        flight_id=flight.id,
                        booking_id=booking_id,
                        seats=request.seat_count,
                        status=ReservationStatus.ACTIVE,
                        expires_at=(
                            request.hold_until.ToDatetime(tzinfo=timezone.utc)
                            if request.HasField("hold_until")
                            else None
                        ),
                    )

                    flight.available_seats -= request.seat_count
                    flight.updated_at = datetime.now(timezone.utc)

                    session.add(reservation)
                    session.flush()
                    session.refresh(flight)
                    session.refresh(reservation)

                    invalidate_flight_cache(str(flight.id))

                    return pb2.ReserveSeatsResponse(
                        reservation=reservation_to_proto(reservation),
                        remaining_available_seats=flight.available_seats,
                    )
            except IntegrityError:
                session.rollback()
                context.abort(
                    grpc.StatusCode.ABORTED, "concurrent reservation conflict"
                )

    def ReleaseReservation(
        self, request: pb2.ReleaseReservationRequest, context: grpc.ServicerContext
    ) -> pb2.ReleaseReservationResponse:
        require_auth(context)

        if not request.booking_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "booking_id is required")

        try:
            booking_id = uuid.UUID(request.booking_id)
        except ValueError:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "booking_id must be a valid UUID"
            )

        with SessionLocal() as session:
            with session.begin():
                reservation = session.scalar(
                    select(SeatReservation)
                    .where(SeatReservation.booking_id == booking_id)
                    .with_for_update()
                )
                if reservation is None:
                    context.abort(grpc.StatusCode.NOT_FOUND, "reservation not found")
                if reservation.status != ReservationStatus.ACTIVE:
                    context.abort(
                        grpc.StatusCode.FAILED_PRECONDITION, "reservation is not active"
                    )

                flight = session.scalar(
                    select(Flight)
                    .where(Flight.id == reservation.flight_id)
                    .with_for_update()
                )
                if flight is None:
                    context.abort(grpc.StatusCode.NOT_FOUND, "flight not found")

                released = reservation.seats
                flight.available_seats += released
                flight.updated_at = datetime.now(timezone.utc)

                reservation.status = ReservationStatus.RELEASED
                reservation.updated_at = datetime.now(timezone.utc)

                session.flush()
                session.refresh(flight)
                session.refresh(reservation)

                invalidate_flight_cache(str(flight.id))

                return pb2.ReleaseReservationResponse(
                    reservation=reservation_to_proto(reservation),
                    released_seats=released,
                    remaining_available_seats=flight.available_seats,
                )
