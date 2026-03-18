import os


class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://booking_user:booking_pass@localhost:5433/booking_db",
    )
    flight_grpc_target: str = os.getenv("FLIGHT_GRPC_TARGET", "localhost:50051")
    grpc_api_key: str = os.getenv("GRPC_API_KEY", "dev-internal-api-key")
    grpc_timeout_seconds: float = float(os.getenv("GRPC_TIMEOUT_SECONDS", "1.5"))

    circuit_breaker_failure_threshold: int = int(os.getenv("CB_FAILURE_THRESHOLD", "5"))
    circuit_breaker_window_seconds: int = int(os.getenv("CB_WINDOW_SECONDS", "30"))
    circuit_breaker_open_timeout_seconds: int = int(
        os.getenv("CB_OPEN_TIMEOUT_SECONDS", "15")
    )


settings = Settings()
