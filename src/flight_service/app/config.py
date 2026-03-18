import os


class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://flight_user:flight_pass@localhost:5434/flight_db",
    )
    grpc_port: int = int(os.getenv("GRPC_PORT", "50051"))
    grpc_api_key: str = os.getenv("GRPC_API_KEY", "dev-internal-api-key")

    redis_sentinels: str = os.getenv("REDIS_SENTINELS", "localhost:26379")
    redis_master_name: str = os.getenv("REDIS_MASTER_NAME", "mymaster")
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))


settings = Settings()
