from __future__ import annotations

import os
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import psycopg
from psycopg.rows import dict_row
from psycopg.errors import InvalidTextRepresentation

from server.errors import ApiError
from server.context import current_user_id, current_role

from openapi_server.apis.orders_api_base import BaseOrdersApi
from openapi_server.models.order_create import OrderCreate
from openapi_server.models.order_update import OrderUpdate
from openapi_server.models.order_response import OrderResponse
from openapi_server.models.order_item_response import OrderItemResponse


def _db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def _rate_limit_minutes() -> int:
    return int(os.getenv("ORDER_RATE_LIMIT_MINUTES", "2"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _d(x: Any) -> Decimal:
    return Decimal(str(x))


def _ctx_user() -> tuple[str, str]:
    uid = current_user_id.get()
    role = current_role.get()
    if not uid or not role:
        raise ApiError("TOKEN_INVALID", "Missing or invalid access token", 401)
    if role not in ("USER", "SELLER", "ADMIN"):
        raise ApiError("TOKEN_INVALID", "Missing or invalid access token", 401)
    return uid, role


def _deny_seller(role: str):
    if role == "SELLER":
        raise ApiError("ACCESS_DENIED", "Access denied", 403)


def _order_response(row: Dict[str, Any], items: List[Dict[str, Any]], promo_code: Optional[str]) -> OrderResponse:
    return OrderResponse(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        status=str(row["status"]),
        promo_code=promo_code,
        total_amount=str(row["total_amount"]),
        discount_amount=str(row["discount_amount"]),
        items=[
            OrderItemResponse(
                product_id=str(it["product_id"]),
                quantity=it["quantity"],
                price_at_order=str(it["price_at_order"]),
            )
            for it in items
        ],
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
    )


async def _fetch_order_items(cur, order_id: str) -> List[Dict[str, Any]]:
    await cur.execute(
        """
        SELECT product_id, quantity, price_at_order
        FROM order_items
        WHERE order_id = %s
        ORDER BY id
        """,
        (order_id,),
    )
    return await cur.fetchall()


class OrdersApiImpl(BaseOrdersApi):
    """
    RBAC (п.10):
      - SELLER: запрещено всё по orders -> ACCESS_DENIED
      - USER: можно только свои
      - ADMIN: можно любые (ownership check пропускаем)
    """

    async def create_order(self, order_create: OrderCreate, request=None) -> OrderResponse:
        user_id, role = _ctx_user()
        _deny_seller(role)

        n = _rate_limit_minutes()
        now = _now()

        items = order_create.items
        promo_code = order_create.promo_code

        async with await psycopg.AsyncConnection.connect(_db_url(), row_factory=dict_row) as conn:
            async with conn.cursor() as cur:
                async with conn.transaction():
                    # 1) rate limit CREATE_ORDER
                    await cur.execute(
                        """
                        SELECT created_at
                        FROM user_operations
                        WHERE user_id = %s AND operation_type = 'CREATE_ORDER'
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (user_id,),
                    )
                    last = await cur.fetchone()
                    if last and (now - last["created_at"]) < timedelta(minutes=n):
                        raise ApiError("ORDER_LIMIT_EXCEEDED", "Order create rate limit exceeded", 429)

                    # 2) active orders CREATED / PAYMENT_PENDING
                    await cur.execute(
                        """
                        SELECT 1
                        FROM orders
                        WHERE user_id = %s AND status IN ('CREATED','PAYMENT_PENDING')
                        LIMIT 1
                        """,
                        (user_id,),
                    )
                    if await cur.fetchone():
                        raise ApiError("ORDER_HAS_ACTIVE", "User already has active order", 409)

                    # 3) catalog + 4) stock check (lock products)
                    product_ids = [str(it.product_id) for it in items]
                    try:
                        await cur.execute(
                            """
                            SELECT id, status, price, stock
                            FROM products
                            WHERE id = ANY(%s)
                            FOR UPDATE
                            """,
                            (product_ids,),
                        )
                    except InvalidTextRepresentation:
                        raise ApiError("VALIDATION_ERROR", "Invalid product_id format", 400)

                    products = await cur.fetchall()
                    by_id = {str(p["id"]): p for p in products}

                    for it in items:
                        pid = str(it.product_id)
                        if pid not in by_id:
                            raise ApiError("PRODUCT_NOT_FOUND", "Product not found", 404, {"product_id": pid})
                        if str(by_id[pid]["status"]) != "ACTIVE":
                            raise ApiError("PRODUCT_INACTIVE", "Product is inactive", 409, {"product_id": pid})

                    insufficient = []
                    for it in items:
                        pid = str(it.product_id)
                        have = int(by_id[pid]["stock"])
                        need = int(it.quantity)
                        if have < need:
                            insufficient.append({"product_id": pid, "requested": need, "available": have})
                    if insufficient:
                        raise ApiError("INSUFFICIENT_STOCK", "Insufficient stock", 409, {"items": insufficient})

                    # 5) reserve stock
                    for it in items:
                        pid = str(it.product_id)
                        need = int(it.quantity)
                        await cur.execute("UPDATE products SET stock = stock - %s WHERE id = %s", (need, pid))

                    # 6) snapshot prices & 7) totals
                    snap: List[Tuple[str, int, Decimal]] = []
                    total = Decimal("0.00")
                    for it in items:
                        pid = str(it.product_id)
                        qty = int(it.quantity)
                        price = _d(by_id[pid]["price"])
                        snap.append((pid, qty, price))
                        total += price * qty

                    discount = Decimal("0.00")
                    promo_id = None
                    promo_code_used = None

                    if promo_code:
                        await cur.execute(
                            """
                            SELECT id, code, discount_type, discount_value, min_order_amount,
                                   max_uses, current_uses, valid_from, valid_until, active
                            FROM promo_codes
                            WHERE code = %s
                            FOR UPDATE
                            """,
                            (promo_code,),
                        )
                        promo = await cur.fetchone()
                        if not promo:
                            raise ApiError("PROMO_CODE_INVALID", "Promo code invalid", 422)
                        if not promo["active"]:
                            raise ApiError("PROMO_CODE_INVALID", "Promo code inactive", 422)
                        if int(promo["current_uses"]) >= int(promo["max_uses"]):
                            raise ApiError("PROMO_CODE_INVALID", "Promo code exhausted", 422)
                        if not (promo["valid_from"] <= now <= promo["valid_until"]):
                            raise ApiError("PROMO_CODE_INVALID", "Promo code out of date", 422)
                        if total < _d(promo["min_order_amount"]):
                            raise ApiError("PROMO_CODE_MIN_AMOUNT", "Order amount below promo minimum", 422)

                        dtype = str(promo["discount_type"])
                        dval = _d(promo["discount_value"])

                        if dtype == "PERCENTAGE":
                            raw = (total * dval) / Decimal("100")
                            cap = total * Decimal("0.70")
                            discount = raw if raw <= cap else cap
                        else:
                            discount = dval if dval <= total else total

                        total = total - discount
                        promo_id = str(promo["id"])
                        promo_code_used = str(promo["code"])

                        await cur.execute(
                            "UPDATE promo_codes SET current_uses = current_uses + 1 WHERE id = %s",
                            (promo_id,),
                        )

                    # 8) insert order + items + user_operations
                    await cur.execute(
                        """
                        INSERT INTO orders (user_id, status, promo_code_id, total_amount, discount_amount)
                        VALUES (%s, 'CREATED', %s, %s, %s)
                        RETURNING id, user_id, status, promo_code_id, total_amount, discount_amount, created_at, updated_at
                        """,
                        (user_id, promo_id, total, discount),
                    )
                    order_row = await cur.fetchone()
                    order_id = str(order_row["id"])

                    for pid, qty, price in snap:
                        await cur.execute(
                            """
                            INSERT INTO order_items (order_id, product_id, quantity, price_at_order)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (order_id, pid, qty, price),
                        )

                    await cur.execute(
                        "INSERT INTO user_operations (user_id, operation_type) VALUES (%s, 'CREATE_ORDER')",
                        (user_id,),
                    )

                    items_rows = await _fetch_order_items(cur, order_id)
                    return _order_response(order_row, items_rows, promo_code_used)

    async def update_order(self, id: str, order_update: OrderUpdate, request=None) -> OrderResponse:
        user_id, role = _ctx_user()
        _deny_seller(role)

        n = _rate_limit_minutes()
        now = _now()
        items = order_update.items

        async with await psycopg.AsyncConnection.connect(_db_url(), row_factory=dict_row) as conn:
            async with conn.cursor() as cur:
                async with conn.transaction():
                    await cur.execute("SELECT * FROM orders WHERE id = %s FOR UPDATE", (id,))
                    order = await cur.fetchone()
                    if not order:
                        raise ApiError("ORDER_NOT_FOUND", "Order not found", 404, {"id": id})

                    # ownership: только если не ADMIN
                    if role != "ADMIN" and str(order["user_id"]) != str(user_id):
                        raise ApiError("ORDER_OWNERSHIP_VIOLATION", "Order belongs to another user", 403)

                    if str(order["status"]) != "CREATED":
                        raise ApiError("INVALID_STATE_TRANSITION", "Order cannot be updated in this state", 409)

                    # rate limit UPDATE_ORDER
                    await cur.execute(
                        """
                        SELECT created_at
                        FROM user_operations
                        WHERE user_id = %s AND operation_type = 'UPDATE_ORDER'
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (user_id,),
                    )
                    last = await cur.fetchone()
                    if last and (now - last["created_at"]) < timedelta(minutes=n):
                        raise ApiError("ORDER_LIMIT_EXCEEDED", "Order update rate limit exceeded", 429)

                    # return previous stock
                    old_items = await _fetch_order_items(cur, id)
                    for it in old_items:
                        await cur.execute(
                            "UPDATE products SET stock = stock + %s WHERE id = %s",
                            (int(it["quantity"]), str(it["product_id"])),
                        )

                    # lock products
                    product_ids = [str(it.product_id) for it in items]
                    try:
                        await cur.execute(
                            """
                            SELECT id, status, price, stock
                            FROM products
                            WHERE id = ANY(%s)
                            FOR UPDATE
                            """,
                            (product_ids,),
                        )
                    except InvalidTextRepresentation:
                        raise ApiError("VALIDATION_ERROR", "Invalid product_id format", 400)

                    products = await cur.fetchall()
                    by_id = {str(p["id"]): p for p in products}

                    for it in items:
                        pid = str(it.product_id)
                        if pid not in by_id:
                            raise ApiError("PRODUCT_NOT_FOUND", "Product not found", 404, {"product_id": pid})
                        if str(by_id[pid]["status"]) != "ACTIVE":
                            raise ApiError("PRODUCT_INACTIVE", "Product is inactive", 409, {"product_id": pid})

                    insufficient = []
                    for it in items:
                        pid = str(it.product_id)
                        have = int(by_id[pid]["stock"])
                        need = int(it.quantity)
                        if have < need:
                            insufficient.append({"product_id": pid, "requested": need, "available": have})
                    if insufficient:
                        raise ApiError("INSUFFICIENT_STOCK", "Insufficient stock", 409, {"items": insufficient})

                    for it in items:
                        pid = str(it.product_id)
                        need = int(it.quantity)
                        await cur.execute("UPDATE products SET stock = stock - %s WHERE id = %s", (need, pid))

                    # rewrite items snapshot
                    await cur.execute("DELETE FROM order_items WHERE order_id = %s", (id,))
                    total = Decimal("0.00")
                    for it in items:
                        pid = str(it.product_id)
                        qty = int(it.quantity)
                        price = _d(by_id[pid]["price"])
                        total += price * qty
                        await cur.execute(
                            "INSERT INTO order_items (order_id, product_id, quantity, price_at_order) VALUES (%s,%s,%s,%s)",
                            (id, pid, qty, price),
                        )

                    # promo recalculation (as you already did)
                    discount = Decimal("0.00")
                    promo_code_used = None
                    promo_id = order["promo_code_id"]
                    if promo_id is not None:
                        await cur.execute(
                            """
                            SELECT id, code, discount_type, discount_value, min_order_amount,
                                   max_uses, current_uses, valid_from, valid_until, active
                            FROM promo_codes
                            WHERE id = %s
                            FOR UPDATE
                            """,
                            (str(promo_id),),
                        )
                        promo = await cur.fetchone()
                        if not promo or (not promo["active"]) or not (promo["valid_from"] <= now <= promo["valid_until"]):
                            await cur.execute("UPDATE orders SET promo_code_id = NULL, discount_amount = 0 WHERE id = %s", (id,))
                            await cur.execute("UPDATE promo_codes SET current_uses = GREATEST(current_uses - 1, 0) WHERE id = %s", (str(promo_id),))
                            promo_id = None
                        else:
                            if total < _d(promo["min_order_amount"]):
                                await cur.execute("UPDATE orders SET promo_code_id = NULL, discount_amount = 0 WHERE id = %s", (id,))
                                await cur.execute("UPDATE promo_codes SET current_uses = GREATEST(current_uses - 1, 0) WHERE id = %s", (str(promo_id),))
                                promo_id = None
                            else:
                                dtype = str(promo["discount_type"])
                                dval = _d(promo["discount_value"])
                                if dtype == "PERCENTAGE":
                                    raw = (total * dval) / Decimal("100")
                                    cap = total * Decimal("0.70")
                                    discount = raw if raw <= cap else cap
                                else:
                                    discount = dval if dval <= total else total
                                promo_code_used = str(promo["code"])

                    total_final = total - discount

                    await cur.execute(
                        """
                        UPDATE orders
                        SET total_amount = %s, discount_amount = %s
                        WHERE id = %s
                        RETURNING id, user_id, status, promo_code_id, total_amount, discount_amount, created_at, updated_at
                        """,
                        (total_final, discount, id),
                    )
                    updated = await cur.fetchone()

                    await cur.execute(
                        "INSERT INTO user_operations (user_id, operation_type) VALUES (%s, 'UPDATE_ORDER')",
                        (user_id,),
                    )

                    items_rows = await _fetch_order_items(cur, id)
                    return _order_response(updated, items_rows, promo_code_used)

    async def cancel_order(self, id: str, request=None) -> OrderResponse:
        user_id, role = _ctx_user()
        _deny_seller(role)

        now = _now()

        async with await psycopg.AsyncConnection.connect(_db_url(), row_factory=dict_row) as conn:
            async with conn.cursor() as cur:
                async with conn.transaction():
                    await cur.execute("SELECT * FROM orders WHERE id = %s FOR UPDATE", (id,))
                    order = await cur.fetchone()
                    if not order:
                        raise ApiError("ORDER_NOT_FOUND", "Order not found", 404, {"id": id})

                    if role != "ADMIN" and str(order["user_id"]) != str(user_id):
                        raise ApiError("ORDER_OWNERSHIP_VIOLATION", "Order belongs to another user", 403)

                    if str(order["status"]) not in ("CREATED", "PAYMENT_PENDING"):
                        raise ApiError("INVALID_STATE_TRANSITION", "Cannot cancel in this state", 409)

                    items_rows = await _fetch_order_items(cur, id)
                    for it in items_rows:
                        await cur.execute(
                            "UPDATE products SET stock = stock + %s WHERE id = %s",
                            (int(it["quantity"]), str(it["product_id"])),
                        )

                    promo_id = order["promo_code_id"]
                    promo_code_used = None
                    if promo_id is not None:
                        await cur.execute("SELECT code FROM promo_codes WHERE id = %s FOR UPDATE", (str(promo_id),))
                        promo = await cur.fetchone()
                        if promo:
                            promo_code_used = str(promo["code"])
                        await cur.execute(
                            "UPDATE promo_codes SET current_uses = GREATEST(current_uses - 1, 0) WHERE id = %s",
                            (str(promo_id),),
                        )

                    await cur.execute(
                        """
                        UPDATE orders
                        SET status = 'CANCELED'
                        WHERE id = %s
                        RETURNING id, user_id, status, promo_code_id, total_amount, discount_amount, created_at, updated_at
                        """,
                        (id,),
                    )
                    updated = await cur.fetchone()

                    await cur.execute(
                        "INSERT INTO user_operations (user_id, operation_type) VALUES (%s, 'UPDATE_ORDER')",
                        (user_id,),
                    )

                    return _order_response(updated, items_rows, promo_code_used)
