from __future__ import annotations

import json
import time
import uuid
import os
from datetime import datetime, timezone
from typing import Tuple

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from server.errors import ApiError
from server.context import current_user_id, current_role

# from impl.generated.src.openapi_server.apis.products_api import router as products_router
# from impl.generated.src.openapi_server.apis.orders_api import router as orders_router
# from impl.generated.src.openapi_server.apis.auth_api import router as auth_router

from openapi_server.apis.products_api import router as products_router
from openapi_server.apis.orders_api import router as orders_router
from openapi_server.apis.auth_api import router as auth_router


app = FastAPI(title="Marketplace API")

app.include_router(auth_router)
app.include_router(products_router)
app.include_router(orders_router)

MAX_BODY_LOG = 10_000
ALLOWED_ROLES = {"USER", "SELLER", "ADMIN"}


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is not set")
    return secret


def _decode_access_token(token: str) -> Tuple[str, str]:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    except ExpiredSignatureError:
        raise ApiError("TOKEN_EXPIRED", "Access token expired", 401)
    except InvalidTokenError:
        raise ApiError("TOKEN_INVALID", "Access token invalid", 401)

    if payload.get("type") != "access":
        raise ApiError("TOKEN_INVALID", "Access token invalid", 401)

    user_id = payload.get("sub")
    role = payload.get("role")

    if not user_id:
        raise ApiError("TOKEN_INVALID", "Access token invalid", 401)
    if not role or role not in ALLOWED_ROLES:
        raise ApiError("TOKEN_INVALID", "Access token invalid", 401)

    return str(user_id), str(role)


def _is_public_path(path: str) -> bool:
    if path.startswith("/auth/"):
        return True
    if path in ("/docs", "/openapi.json", "/redoc"):
        return True
    return False


def _mask_sensitive_body(body_text: str | None) -> str | None:
    if body_text is None:
        return None

    try:
        data = json.loads(body_text)
    except Exception:
        return body_text

    if isinstance(data, dict):
        sensitive_keys = {"password", "refresh_token", "access_token"}

        def mask(obj):
            if isinstance(obj, dict):
                out = {}
                for k, v in obj.items():
                    if k in sensitive_keys:
                        out[k] = "***"
                    else:
                        out[k] = mask(v)
                return out
            if isinstance(obj, list):
                return [mask(x) for x in obj]
            return obj

        try:
            return json.dumps(mask(data), ensure_ascii=False)[:MAX_BODY_LOG]
        except Exception:
            return body_text

    return body_text


def _api_error_to_response(exc: ApiError) -> JSONResponse:
    body = {"error_code": exc.error_code, "message": exc.message}
    if exc.details is not None:
        body["details"] = exc.details
    return JSONResponse(status_code=exc.status_code, content=body)


@app.middleware("http")
async def request_id_auth_and_logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    start = time.perf_counter()
    body_text = None
    response = None
    status_code = 500
    user_id = None
    role = None

    try:
        if request.method in ("POST", "PUT", "DELETE"):
            body = await request.body()
            if body:
                raw_body_text = body.decode("utf-8", errors="replace")[:MAX_BODY_LOG]
                body_text = _mask_sensitive_body(raw_body_text)

            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}

            request._receive = receive

        if not _is_public_path(request.url.path):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                response = JSONResponse(
                    status_code=401,
                    content={
                        "error_code": "TOKEN_INVALID",
                        "message": "Missing or invalid access token",
                    },
                )
                status_code = 401
                return response

            token = auth.removeprefix("Bearer ").strip()

            try:
                user_id, role = _decode_access_token(token)
            except ApiError as exc:
                response = _api_error_to_response(exc)
                status_code = exc.status_code
                return response

            request.state.user_id = user_id
            request.state.role = role
            current_user_id.set(user_id)
            current_role.set(role)
        else:
            request.state.user_id = None
            request.state.role = None
            current_user_id.set(None)
            current_role.set(None)

        response = await call_next(request)
        status_code = response.status_code
        return response

    finally:
        duration_ms = int((time.perf_counter() - start) * 1000)

        if response is not None:
            response.headers["X-Request-Id"] = request_id

        log = {
            "request_id": request_id,
            "method": request.method,
            "endpoint": request.url.path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if body_text is not None:
            log["request_body"] = body_text

        if role is not None:
            log["role"] = role

        print(json.dumps(log, ensure_ascii=False))


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError):
    return _api_error_to_response(exc)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    fields = []
    for e in exc.errors():
        loc = e.get("loc", [])
        field = ".".join(str(x) for x in loc[1:]) if len(loc) > 1 else ".".join(str(x) for x in loc)
        fields.append({"field": field, "issue": e.get("msg")})

    return JSONResponse(
        status_code=400,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": {"fields": fields},
        },
    )
