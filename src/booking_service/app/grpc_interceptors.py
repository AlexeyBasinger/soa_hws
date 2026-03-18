from __future__ import annotations

import grpc

from app.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError


class CircuitBreakerInterceptor(grpc.UnaryUnaryClientInterceptor):
    def __init__(
        self,
        breaker: CircuitBreaker,
        retryable_codes: set[grpc.StatusCode],
    ) -> None:
        self.breaker = breaker
        self.retryable_codes = retryable_codes

    def intercept_unary_unary(self, continuation, client_call_details, request):
        self.breaker.before_call()

        try:
            response = continuation(client_call_details, request)
            self.breaker.record_success()
            return response
        except grpc.RpcError as exc:
            if exc.code() in self.retryable_codes:
                self.breaker.record_failure()
            else:
                self.breaker.record_success()
            raise
