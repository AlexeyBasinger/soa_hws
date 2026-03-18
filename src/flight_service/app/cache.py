from __future__ import annotations

import json
import logging

from redis.exceptions import RedisError
from redis.sentinel import Sentinel

from app.config import settings

logger = logging.getLogger(__name__)


def _parse_sentinels(raw: str) -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        host, port = item.split(":")
        result.append((host.strip(), int(port.strip())))
    return result


sentinel = Sentinel(
    _parse_sentinels(settings.redis_sentinels),
    socket_timeout=0.5,
    decode_responses=True,
)


def _redis_master():
    return sentinel.master_for(
        settings.redis_master_name,
        socket_timeout=0.5,
        decode_responses=True,
    )


def flight_cache_key(flight_id: str) -> str:
    return f"flight:{flight_id}"


def search_cache_key(origin: str, destination: str, date_token: str) -> str:
    return f"search:{origin}:{destination}:{date_token}"


def search_index_key(flight_id: str) -> str:
    return f"flight_search_keys:{flight_id}"


def cache_get_json(key: str):
    try:
        raw = _redis_master().get(key)
        if raw is None:
            logger.info("cache miss key=%s", key)
            return None
        logger.info("cache hit key=%s", key)
        return json.loads(raw)
    except RedisError:
        logger.exception("redis get failed key=%s", key)
        return None


def cache_set_json(key: str, payload, ttl_seconds: int | None = None) -> None:
    ttl = ttl_seconds or settings.cache_ttl_seconds
    try:
        _redis_master().set(key, json.dumps(payload), ex=ttl)
    except RedisError:
        logger.exception("redis set failed key=%s", key)


def remember_search_key_for_flight(flight_id: str, key: str) -> None:
    idx_key = search_index_key(flight_id)
    try:
        r = _redis_master()
        pipe = r.pipeline()
        pipe.sadd(idx_key, key)
        pipe.expire(idx_key, settings.cache_ttl_seconds)
        pipe.execute()
    except RedisError:
        logger.exception(
            "redis index update failed flight_id=%s key=%s", flight_id, key
        )


def invalidate_flight_cache(flight_id: str) -> None:
    idx_key = search_index_key(flight_id)
    try:
        r = _redis_master()
        related_search_keys = list(r.smembers(idx_key))
        keys_to_delete = [flight_cache_key(flight_id), idx_key, *related_search_keys]
        if keys_to_delete:
            r.delete(*keys_to_delete)
        logger.info(
            "cache invalidated flight_id=%s deleted_keys=%s",
            flight_id,
            len(keys_to_delete),
        )
    except RedisError:
        logger.exception("redis invalidation failed flight_id=%s", flight_id)
