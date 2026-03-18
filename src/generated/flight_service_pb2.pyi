import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class FlightStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FLIGHT_STATUS_UNSPECIFIED: _ClassVar[FlightStatus]
    FLIGHT_STATUS_SCHEDULED: _ClassVar[FlightStatus]
    FLIGHT_STATUS_DELAYED: _ClassVar[FlightStatus]
    FLIGHT_STATUS_CANCELLED: _ClassVar[FlightStatus]
    FLIGHT_STATUS_DEPARTED: _ClassVar[FlightStatus]
    FLIGHT_STATUS_COMPLETED: _ClassVar[FlightStatus]

class ReservationStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RESERVATION_STATUS_UNSPECIFIED: _ClassVar[ReservationStatus]
    RESERVATION_STATUS_ACTIVE: _ClassVar[ReservationStatus]
    RESERVATION_STATUS_RELEASED: _ClassVar[ReservationStatus]
    RESERVATION_STATUS_EXPIRED: _ClassVar[ReservationStatus]

FLIGHT_STATUS_UNSPECIFIED: FlightStatus
FLIGHT_STATUS_SCHEDULED: FlightStatus
FLIGHT_STATUS_DELAYED: FlightStatus
FLIGHT_STATUS_CANCELLED: FlightStatus
FLIGHT_STATUS_DEPARTED: FlightStatus
FLIGHT_STATUS_COMPLETED: FlightStatus
RESERVATION_STATUS_UNSPECIFIED: ReservationStatus
RESERVATION_STATUS_ACTIVE: ReservationStatus
RESERVATION_STATUS_RELEASED: ReservationStatus
RESERVATION_STATUS_EXPIRED: ReservationStatus

class Flight(_message.Message):
    __slots__ = (
        "id",
        "flight_number",
        "airline_code",
        "airline_name",
        "origin",
        "destination",
        "departure_time",
        "arrival_time",
        "total_seats",
        "available_seats",
        "price",
        "status",
        "created_at",
        "updated_at",
    )
    ID_FIELD_NUMBER: _ClassVar[int]
    FLIGHT_NUMBER_FIELD_NUMBER: _ClassVar[int]
    AIRLINE_CODE_FIELD_NUMBER: _ClassVar[int]
    AIRLINE_NAME_FIELD_NUMBER: _ClassVar[int]
    ORIGIN_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_FIELD_NUMBER: _ClassVar[int]
    DEPARTURE_TIME_FIELD_NUMBER: _ClassVar[int]
    ARRIVAL_TIME_FIELD_NUMBER: _ClassVar[int]
    TOTAL_SEATS_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_SEATS_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    flight_number: str
    airline_code: str
    airline_name: str
    origin: str
    destination: str
    departure_time: _timestamp_pb2.Timestamp
    arrival_time: _timestamp_pb2.Timestamp
    total_seats: int
    available_seats: int
    price: str
    status: FlightStatus
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(
        self,
        id: _Optional[str] = ...,
        flight_number: _Optional[str] = ...,
        airline_code: _Optional[str] = ...,
        airline_name: _Optional[str] = ...,
        origin: _Optional[str] = ...,
        destination: _Optional[str] = ...,
        departure_time: _Optional[
            _Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]
        ] = ...,
        arrival_time: _Optional[
            _Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]
        ] = ...,
        total_seats: _Optional[int] = ...,
        available_seats: _Optional[int] = ...,
        price: _Optional[str] = ...,
        status: _Optional[_Union[FlightStatus, str]] = ...,
        created_at: _Optional[
            _Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]
        ] = ...,
        updated_at: _Optional[
            _Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]
        ] = ...,
    ) -> None: ...

class SeatReservation(_message.Message):
    __slots__ = (
        "id",
        "booking_id",
        "flight_id",
        "seats",
        "status",
        "expires_at",
        "created_at",
        "updated_at",
    )
    ID_FIELD_NUMBER: _ClassVar[int]
    BOOKING_ID_FIELD_NUMBER: _ClassVar[int]
    FLIGHT_ID_FIELD_NUMBER: _ClassVar[int]
    SEATS_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    booking_id: str
    flight_id: str
    seats: int
    status: ReservationStatus
    expires_at: _timestamp_pb2.Timestamp
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(
        self,
        id: _Optional[str] = ...,
        booking_id: _Optional[str] = ...,
        flight_id: _Optional[str] = ...,
        seats: _Optional[int] = ...,
        status: _Optional[_Union[ReservationStatus, str]] = ...,
        expires_at: _Optional[
            _Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]
        ] = ...,
        created_at: _Optional[
            _Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]
        ] = ...,
        updated_at: _Optional[
            _Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]
        ] = ...,
    ) -> None: ...

class SearchFlightsRequest(_message.Message):
    __slots__ = ("origin", "destination", "departure_from", "departure_to")
    ORIGIN_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_FIELD_NUMBER: _ClassVar[int]
    DEPARTURE_FROM_FIELD_NUMBER: _ClassVar[int]
    DEPARTURE_TO_FIELD_NUMBER: _ClassVar[int]
    origin: str
    destination: str
    departure_from: _timestamp_pb2.Timestamp
    departure_to: _timestamp_pb2.Timestamp
    def __init__(
        self,
        origin: _Optional[str] = ...,
        destination: _Optional[str] = ...,
        departure_from: _Optional[
            _Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]
        ] = ...,
        departure_to: _Optional[
            _Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]
        ] = ...,
    ) -> None: ...

class SearchFlightsResponse(_message.Message):
    __slots__ = ("flights",)
    FLIGHTS_FIELD_NUMBER: _ClassVar[int]
    flights: _containers.RepeatedCompositeFieldContainer[Flight]
    def __init__(
        self, flights: _Optional[_Iterable[_Union[Flight, _Mapping]]] = ...
    ) -> None: ...

class GetFlightRequest(_message.Message):
    __slots__ = ("flight_id",)
    FLIGHT_ID_FIELD_NUMBER: _ClassVar[int]
    flight_id: str
    def __init__(self, flight_id: _Optional[str] = ...) -> None: ...

class GetFlightResponse(_message.Message):
    __slots__ = ("flight",)
    FLIGHT_FIELD_NUMBER: _ClassVar[int]
    flight: Flight
    def __init__(self, flight: _Optional[_Union[Flight, _Mapping]] = ...) -> None: ...

class ReserveSeatsRequest(_message.Message):
    __slots__ = ("booking_id", "flight_id", "seat_count", "hold_until")
    BOOKING_ID_FIELD_NUMBER: _ClassVar[int]
    FLIGHT_ID_FIELD_NUMBER: _ClassVar[int]
    SEAT_COUNT_FIELD_NUMBER: _ClassVar[int]
    HOLD_UNTIL_FIELD_NUMBER: _ClassVar[int]
    booking_id: str
    flight_id: str
    seat_count: int
    hold_until: _timestamp_pb2.Timestamp
    def __init__(
        self,
        booking_id: _Optional[str] = ...,
        flight_id: _Optional[str] = ...,
        seat_count: _Optional[int] = ...,
        hold_until: _Optional[
            _Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]
        ] = ...,
    ) -> None: ...

class ReserveSeatsResponse(_message.Message):
    __slots__ = ("reservation", "remaining_available_seats")
    RESERVATION_FIELD_NUMBER: _ClassVar[int]
    REMAINING_AVAILABLE_SEATS_FIELD_NUMBER: _ClassVar[int]
    reservation: SeatReservation
    remaining_available_seats: int
    def __init__(
        self,
        reservation: _Optional[_Union[SeatReservation, _Mapping]] = ...,
        remaining_available_seats: _Optional[int] = ...,
    ) -> None: ...

class ReleaseReservationRequest(_message.Message):
    __slots__ = ("booking_id",)
    BOOKING_ID_FIELD_NUMBER: _ClassVar[int]
    booking_id: str
    def __init__(self, booking_id: _Optional[str] = ...) -> None: ...

class ReleaseReservationResponse(_message.Message):
    __slots__ = ("reservation", "released_seats", "remaining_available_seats")
    RESERVATION_FIELD_NUMBER: _ClassVar[int]
    RELEASED_SEATS_FIELD_NUMBER: _ClassVar[int]
    REMAINING_AVAILABLE_SEATS_FIELD_NUMBER: _ClassVar[int]
    reservation: SeatReservation
    released_seats: int
    remaining_available_seats: int
    def __init__(
        self,
        reservation: _Optional[_Union[SeatReservation, _Mapping]] = ...,
        released_seats: _Optional[int] = ...,
        remaining_available_seats: _Optional[int] = ...,
    ) -> None: ...
