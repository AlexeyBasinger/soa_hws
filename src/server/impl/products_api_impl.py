from __future__ import annotations

import os
from decimal import Decimal
from typing import Any, Optional, Dict

import psycopg
from psycopg.rows import dict_row
from psycopg.errors import InvalidTextRepresentation

from server.errors import ApiError
from server.context import current_user_id, current_role

# from generated.src.openapi_server.apis.products_api_base import BaseProductsApi
# from generated.src.openapi_server.models.product_create import ProductCreate
# from generated.src.openapi_server.models.product_update import ProductUpdate
# from generated.src.openapi_server.models.product_response import ProductResponse
# from generated.src.openapi_server.models.product_page import ProductPage

from openapi_server.apis.products_api_base import BaseProductsApi
from openapi_server.models.product_create import ProductCreate
from openapi_server.models.product_update import ProductUpdate
from openapi_server.models.product_response import ProductResponse
from openapi_server.models.product_page import ProductPage


def _db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def _ctx_user() -> tuple[str, str]:
    uid = current_user_id.get()
    role = current_role.get()
    if not uid or not role:
        raise ApiError("TOKEN_INVALID", "Missing or invalid access token", 401)
    if role not in ("USER", "SELLER", "ADMIN"):
        raise ApiError("TOKEN_INVALID", "Missing or invalid access token", 401)
    return uid, role


def _to_decimal(v: Any) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        raise ApiError("VALIDATION_ERROR", "Invalid price", 400, {"field": "price", "value": v})


def _row_to_product(row: Dict[str, Any]) -> ProductResponse:
    return ProductResponse(
        id=str(row["id"]),
        name=row["name"],
        description=row.get("description"),
        price=str(row["price"]),
        stock=row["stock"],
        category=row["category"],
        status=str(row["status"]),
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
    )


async def _ensure_seller_owns(cur, product_id: str, seller_id: str):
    await cur.execute("SELECT seller_id FROM products WHERE id = %s", (product_id,))
    row = await cur.fetchone()
    if not row:
        raise ApiError("PRODUCT_NOT_FOUND", "Product not found", 404, {"id": product_id})
    if row["seller_id"] is None or str(row["seller_id"]) != str(seller_id):
        raise ApiError("ACCESS_DENIED", "Access denied", 403)


class ProductsApiImpl(BaseProductsApi):
    async def create_product(self, product_create: ProductCreate) -> ProductResponse:
        uid, role = _ctx_user()
        if role == "USER":
            raise ApiError("ACCESS_DENIED", "Access denied", 403)

        price = _to_decimal(product_create.price)

        # SELLER и ADMIN создают товар "как себя"
        seller_id = uid

        async with await psycopg.AsyncConnection.connect(_db_url(), row_factory=dict_row) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO products (name, description, price, stock, category, status, seller_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, name, description, price, stock, category, status, created_at, updated_at
                    """,
                    (
                        product_create.name,
                        product_create.description,
                        price,
                        product_create.stock,
                        product_create.category,
                        product_create.status,
                        seller_id,
                    ),
                )
                row = await cur.fetchone()
                await conn.commit()

        return _row_to_product(row)

    async def get_product_by_id(self, id: str) -> ProductResponse:
        async with await psycopg.AsyncConnection.connect(_db_url(), row_factory=dict_row) as conn:
            async with conn.cursor() as cur:
                try:
                    await cur.execute(
                        """
                        SELECT id, name, description, price, stock, category, status, created_at, updated_at
                        FROM products
                        WHERE id = %s
                        """,
                        (id,),
                    )
                except InvalidTextRepresentation:
                    raise ApiError("VALIDATION_ERROR", "Invalid id format", 400, {"field": "id", "value": id})
                row = await cur.fetchone()

        if not row:
            raise ApiError("PRODUCT_NOT_FOUND", "Product not found", 404, {"id": id})

        return _row_to_product(row)

    async def list_products(
        self,
        page: int,
        size: int,
        status: Optional[str],
        category: Optional[str],
    ) -> ProductPage:
        if page < 0 or size <= 0:
            raise ApiError("VALIDATION_ERROR", "Invalid pagination", 400, {"page": page, "size": size})

        where = []
        params = []

        if status is not None:
            where.append("status = %s")
            params.append(status)

        if category is not None:
            where.append("category = %s")
            params.append(category)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        offset = page * size

        async with await psycopg.AsyncConnection.connect(_db_url(), row_factory=dict_row) as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT COUNT(*) AS cnt FROM products {where_sql}", params)
                total = int((await cur.fetchone())["cnt"])

                await cur.execute(
                    f"""
                    SELECT id, name, description, price, stock, category, status, created_at, updated_at
                    FROM products
                    {where_sql}
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    params + [size, offset],
                )
                rows = await cur.fetchall()

        content = [_row_to_product(r) for r in rows]
        return ProductPage(content=content, totalElements=total, page=page, size=size)

    async def update_product(self, id: str, product_update: ProductUpdate) -> ProductResponse:
        uid, role = _ctx_user()
        if role == "USER":
            raise ApiError("ACCESS_DENIED", "Access denied", 403)

        price = _to_decimal(product_update.price)

        async with await psycopg.AsyncConnection.connect(_db_url(), row_factory=dict_row) as conn:
            async with conn.cursor() as cur:
                # SELLER только свои
                if role == "SELLER":
                    await _ensure_seller_owns(cur, id, uid)

                try:
                    await cur.execute(
                        """
                        UPDATE products
                        SET name = %s,
                            description = %s,
                            price = %s,
                            stock = %s,
                            category = %s,
                            status = %s
                        WHERE id = %s
                        RETURNING id, name, description, price, stock, category, status, created_at, updated_at
                        """,
                        (
                            product_update.name,
                            product_update.description,
                            price,
                            product_update.stock,
                            product_update.category,
                            product_update.status,
                            id,
                        ),
                    )
                except InvalidTextRepresentation:
                    raise ApiError("VALIDATION_ERROR", "Invalid id format", 400, {"field": "id", "value": id})

                row = await cur.fetchone()
                await conn.commit()

        if not row:
            raise ApiError("PRODUCT_NOT_FOUND", "Product not found", 404, {"id": id})

        return _row_to_product(row)

    async def archive_product(self, id: str) -> ProductResponse:
        uid, role = _ctx_user()
        if role == "USER":
            raise ApiError("ACCESS_DENIED", "Access denied", 403)

        async with await psycopg.AsyncConnection.connect(_db_url(), row_factory=dict_row) as conn:
            async with conn.cursor() as cur:
                if role == "SELLER":
                    await _ensure_seller_owns(cur, id, uid)

                try:
                    await cur.execute(
                        """
                        UPDATE products
                        SET status = 'ARCHIVED'
                        WHERE id = %s
                        RETURNING id, name, description, price, stock, category, status, created_at, updated_at
                        """,
                        (id,),
                    )
                except InvalidTextRepresentation:
                    raise ApiError("VALIDATION_ERROR", "Invalid id format", 400, {"field": "id", "value": id})

                row = await cur.fetchone()
                await conn.commit()

        if not row:
            raise ApiError("PRODUCT_NOT_FOUND", "Product not found", 404, {"id": id})

        return _row_to_product(row)
