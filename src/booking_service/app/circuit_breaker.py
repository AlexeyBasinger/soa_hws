from __future__ import annotations

import logging
from collections import deque
from threading import Lock
from time import monotonic

logger = logging.getLogger(__name__)


class CircuitBreakerOpenError(Exception):
    pass


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int,
        window_seconds: int,
        open_timeout_seconds: int,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.open_timeout_seconds = open_timeout_seconds

        self._state = "CLOSED"
        self._failure_timestamps: deque[float] = deque()
        self._opened_at: float | None = None
        self._half_open_probe_in_flight = False
        self._lock = Lock()

    @property
    def state(self) -> str:
        return self._state

    def _prune_failures(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._failure_timestamps and self._failure_timestamps[0] < cutoff:
            self._failure_timestamps.popleft()

    def _transition(self, new_state: str, reason: str) -> None:
        if self._state == new_state:
            return

        logger.warning(
            "circuit breaker transition service=%s %s -> %s reason=%s",
            self.name,
            self._state,
            new_state,
            reason,
        )

        self._state = new_state

        if new_state == "OPEN":
            self._opened_at = monotonic()
            self._half_open_probe_in_flight = False
        elif new_state == "HALF_OPEN":
            self._half_open_probe_in_flight = True
        elif new_state == "CLOSED":
            self._opened_at = None
            self._half_open_probe_in_flight = False
            self._failure_timestamps.clear()

    def before_call(self) -> None:
        with self._lock:
            now = monotonic()

            if self._state == "CLOSED":
                return

            if self._state == "OPEN":
                assert self._opened_at is not None
                elapsed = now - self._opened_at
                if elapsed >= self.open_timeout_seconds:
                    self._transition("HALF_OPEN", "open timeout elapsed")
                    return

                raise CircuitBreakerOpenError(
                    f"{self.name} temporarily unavailable: circuit breaker is OPEN"
                )

            if self._state == "HALF_OPEN":
                raise CircuitBreakerOpenError(
                    f"{self.name} temporarily unavailable: probe request in progress"
                )

    def record_success(self) -> None:
        with self._lock:
            if self._state == "HALF_OPEN":
                self._transition("CLOSED", "probe succeeded")
            elif self._state == "CLOSED":
                now = monotonic()
                self._prune_failures(now)

    def record_failure(self) -> None:
        with self._lock:
            now = monotonic()

            if self._state == "HALF_OPEN":
                self._transition("OPEN", "probe failed")
                return

            if self._state == "CLOSED":
                self._failure_timestamps.append(now)
                self._prune_failures(now)

                if len(self._failure_timestamps) >= self.failure_threshold:
                    self._transition(
                        "OPEN",
                        f"failure threshold reached: {len(self._failure_timestamps)} failures in window",
                    )
