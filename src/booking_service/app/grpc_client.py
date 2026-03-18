from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import grpc

import flight_service_pb2 as pb2
import flight_service_pb2_grpc as pb2_grpc
from app.circuit_breaker import CircuitBreaker
from app.config import settings
from app.grpc_interceptors import CircuitBreakerInterceptor

logger = logging.getLogger(__name__)

STATUS_TO_NAME = {
    pb2.FLIGHT_STATUS_UNSPECIFIED: "UNSPECIFIED",
    pb2.FLIGHT_STATUS_SCHEDULED: "SCHEDULED",
    pb2.FLIGHT_STATUS_DELAYED: "DELAYED",
    pb2.FLIGHT_STATUS_CANCELLED: "CANCELLED",
    pb2.FLIGHT_STATUS_DEPARTED: "DEPARTED",
    pb2.FLIGHT_STATUS_COMPLETED: "COMPLETED",
}

RETRYABLE_CODES = {
    grpc.StatusCode.UNAVAILABLE,
    grpc.StatusCode.DEADLINE_EXCEEDED,
}

BACKOFF_DELAYS = [0.1, 0.2, 0.4]

flight_service_circuit_breaker = CircuitBreaker(
    name="flight-service",
    failure_threshold=settings.circuit_breaker_failure_threshold,
    window_seconds=settings.circuit_breaker_window_seconds,
    open_timeout_seconds=settings.circuit_breaker_open_timeout_seconds,
)


@dataclass
class FlightDTO:
    id: UUID
    flight_number: str
    airline_code: str
    airline_name: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    total_seats: int
    available_seats: int
    price: Decimal
    status: str
    created_at: datetime
    updated_at: datetime


class FlightGrpcError(Exception):
    def __init__(self, code: grpc.StatusCode, details: str):
        super().__init__(details)
        self.code = code
        self.details = details


class FlightGrpcClient:
    def __init__(self, target: str) -> None:
        base_channel = grpc.insecure_channel(target)

        breaker_interceptor = CircuitBreakerInterceptor(
            breaker=flight_service_circuit_breaker,
            retryable_codes=RETRYABLE_CODES,
        )

        self.channel = grpc.intercept_channel(base_channel, breaker_interceptor)
        self.stub = pb2_grpc.FlightServiceStub(self.channel)

    def _auth_metadata(self) -> list[tuple[str, str]]:
        return [("x-api-key", settings.grpc_api_key)]

    @staticmethod
    def _flight_from_proto(flight: pb2.Flight) -> FlightDTO:
        return FlightDTO(
            id=UUID(flight.id),
            flight_number=flight.flight_number,
            airline_code=flight.airline_code,
            airline_name=flight.airline_name,
            origin=flight.origin,
            destination=flight.destination,
            departure_time=flight.departure_time.ToDatetime(tzinfo=timezone.utc),
            arrival_time=flight.arrival_time.ToDatetime(tzinfo=timezone.utc),
            total_seats=flight.total_seats,
            available_seats=flight.available_seats,
            price=Decimal(flight.price),
            status=STATUS_TO_NAME[flight.status],
            created_at=flight.created_at.ToDatetime(tzinfo=timezone.utc),
            updated_at=flight.updated_at.ToDatetime(tzinfo=timezone.utc),
        )

    @staticmethod
    def _date_to_range(target_date: date) -> tuple[datetime, datetime]:
        start = datetime.combine(target_date, dt_time.min, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        return start, end

    @staticmethod
    def _dt_to_ts(dt: datetime):
        from google.protobuf.timestamp_pb2 import Timestamp

        ts = Timestamp()
        ts.FromDatetime(dt)
        return ts

    def _handle_error(self, exc: grpc.RpcError) -> None:
        raise FlightGrpcError(exc.code(), exc.details() or "gRPC call failed") from exc

    def _call_with_retry(self, rpc_callable, request):
        last_exc: grpc.RpcError | None = None

        for attempt in range(1, 4):
            try:
                return rpc_callable(
                    request,
                    metadata=self._auth_metadata(),
                    timeout=settings.grpc_timeout_seconds,
                )
            except grpc.RpcError as exc:
                code = exc.code()
                details = exc.details() or "gRPC call failed"

                if code not in RETRYABLE_CODES:
                    self._handle_error(exc)

                last_exc = exc
                logger.warning(
                    "gRPC retryable error attempt=%s code=%s details=%s",
                    attempt,
                    code.name,
                    details,
                )

                if attempt == 3:
                    break

                delay = BACKOFF_DELAYS[attempt - 1]
                time.sleep(delay)

        assert last_exc is not None
        self._handle_error(last_exc)

    def search_flights(
        self, origin: str, destination: str, flight_date: date | None = None
    ) -> list[FlightDTO]:
        request = pb2.SearchFlightsRequest(
            origin=origin.upper(), destination=destination.upper()
        )
        if flight_date is not None:
            start, end = self._date_to_range(flight_date)
            request.departure_from.CopyFrom(self._dt_to_ts(start))
            request.departure_to.CopyFrom(self._dt_to_ts(end))

        response = self._call_with_retry(self.stub.SearchFlights, request)
        return [self._flight_from_proto(item) for item in response.flights]

    def get_flight(self, flight_id: UUID) -> FlightDTO:
        request = pb2.GetFlightRequest(flight_id=str(flight_id))
        response = self._call_with_retry(self.stub.GetFlight, request)
        return self._flight_from_proto(response.flight)

    def reserve_seats(self, booking_id: UUID, flight_id: UUID, seat_count: int) -> None:
        request = pb2.ReserveSeatsRequest(
            booking_id=str(booking_id),
            flight_id=str(flight_id),
            seat_count=seat_count,
        )
        self._call_with_retry(self.stub.ReserveSeats, request)

    def release_reservation(self, booking_id: UUID) -> None:
        request = pb2.ReleaseReservationRequest(booking_id=str(booking_id))
        self._call_with_retry(self.stub.ReleaseReservation, request)


flight_client = FlightGrpcClient(settings.flight_grpc_target)
