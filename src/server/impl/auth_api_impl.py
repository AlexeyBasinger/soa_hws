from __future__ import annotations

import os
import uuid
import time
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import psycopg
from psycopg.rows import dict_row
from psycopg.errors import UniqueViolation

from server.errors import ApiError

from openapi_server.apis.auth_api_base import BaseAuthApi
from openapi_server.models.auth_register_request import AuthRegisterRequest
from openapi_server.models.auth_login_request import AuthLoginRequest
from openapi_server.models.auth_refresh_request import AuthRefreshRequest
from openapi_server.models.auth_tokens_response import AuthTokensResponse


ALLOWED_ROLES = {"USER", "SELLER", "ADMIN"}


def _db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is not set")
    return secret


def _access_ttl_minutes() -> int:
    return int(os.getenv("ACCESS_TTL_MINUTES", "20"))  # 15–30 минут по ТЗ


def _refresh_ttl_days() -> int:
    return int(os.getenv("REFRESH_TTL_DAYS", "14"))  # 7–30 дней по ТЗ


def _hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _make_access_token(user_id: str, role: str) -> tuple[str, int]:
    ttl_min = _access_ttl_minutes()
    exp = _now() + timedelta(minutes=ttl_min)
    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": int(time.time()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, _jwt_secret(), algorithm="HS256")
    return token, ttl_min * 60


def _make_refresh_token() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex


def _hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


class AuthApiImpl(BaseAuthApi):
    async def register(self, auth_register_request: AuthRegisterRequest) -> None:
        email = auth_register_request.email.strip().lower()
        password = auth_register_request.password

        if not email:
            raise ApiError("VALIDATION_ERROR", "Email is required", 400, {"field": "email"})
        if not password:
            raise ApiError("VALIDATION_ERROR", "Password is required", 400, {"field": "password"})

        pwd_hash = _hash_password(password)

        async with await psycopg.AsyncConnection.connect(_db_url(), row_factory=dict_row) as conn:
            async with conn.cursor() as cur:
                try:
                    await cur.execute(
                        "INSERT INTO users (email, password_hash) VALUES (%s, %s)",
                        (email, pwd_hash),
                    )
                    await conn.commit()
                except UniqueViolation:
                    raise ApiError("VALIDATION_ERROR", "Email already registered", 400, {"field": "email"})

        return None

    async def login(self, auth_login_request: AuthLoginRequest) -> AuthTokensResponse:
        email = auth_login_request.email.strip().lower()
        password = auth_login_request.password

        async with await psycopg.AsyncConnection.connect(_db_url(), row_factory=dict_row) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id, password_hash, role FROM users WHERE email = %s",
                    (email,),
                )
                user = await cur.fetchone()

        if not user or not _verify_password(password, user["password_hash"]):
            raise ApiError("TOKEN_INVALID", "Invalid credentials", 401)

        user_id = str(user["id"])
        role = str(user["role"])
        if role not in ALLOWED_ROLES:
            role = "USER"

        access_token, expires_in = _make_access_token(user_id, role)

        refresh_token = _make_refresh_token()
        refresh_hash = _hash_refresh_token(refresh_token)
        refresh_exp = _now() + timedelta(days=_refresh_ttl_days())

        async with await psycopg.AsyncConnection.connect(_db_url(), row_factory=dict_row) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO refresh_tokens (user_id, token_hash, expires_at, revoked)
                    VALUES (%s, %s, %s, FALSE)
                    """,
                    (user_id, refresh_hash, refresh_exp),
                )
                await conn.commit()

        return AuthTokensResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=expires_in,
        )

    async def refresh(self, auth_refresh_request: AuthRefreshRequest) -> AuthTokensResponse:
        refresh_token = auth_refresh_request.refresh_token
        refresh_hash = _hash_refresh_token(refresh_token)
        now = _now()

        async with await psycopg.AsyncConnection.connect(_db_url(), row_factory=dict_row) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, user_id, expires_at, revoked
                    FROM refresh_tokens
                    WHERE token_hash = %s
                    """,
                    (refresh_hash,),
                )
                rt = await cur.fetchone()

                if (not rt) or rt["revoked"] or (rt["expires_at"] <= now):
                    raise ApiError("REFRESH_TOKEN_INVALID", "Refresh token invalid", 401)

                user_id = str(rt["user_id"])

                # роль пользователя
                await cur.execute("SELECT role FROM users WHERE id = %s", (user_id,))
                u = await cur.fetchone()
                role = str(u["role"]) if u and u.get("role") else "USER"
                if role not in ALLOWED_ROLES:
                    role = "USER"

                # rotation refresh token
                new_refresh = _make_refresh_token()
                new_refresh_hash = _hash_refresh_token(new_refresh)
                new_refresh_exp = now + timedelta(days=_refresh_ttl_days())

                await cur.execute("UPDATE refresh_tokens SET revoked = TRUE WHERE id = %s", (str(rt["id"]),))
                await cur.execute(
                    """
                    INSERT INTO refresh_tokens (user_id, token_hash, expires_at, revoked)
                    VALUES (%s, %s, %s, FALSE)
                    """,
                    (user_id, new_refresh_hash, new_refresh_exp),
                )

                access_token, expires_in = _make_access_token(user_id, role)
                await conn.commit()

        return AuthTokensResponse(
            access_token=access_token,
            refresh_token=new_refresh,
            token_type="Bearer",
            expires_in=expires_in,
        )
