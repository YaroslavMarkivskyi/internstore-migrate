import uuid
from datetime import datetime, timedelta, timezone

import httpx


def _require_uuid(product_id: str) -> None:
    # STR-148: found live — a caller (in practice, the shopping agent's
    # LLM) occasionally passes something that isn't a real product_id at
    # all (a product's name text, a name fragment) instead of the UUID a
    # prior search_products/get_cart result actually returned. Without
    # this, that reaches Orders, which 422s with a generic Pydantic
    # message, which httpx.raise_for_status() flattens into "Client error
    # '422 Unprocessable Entity' for url '...'" with no actual detail —
    # useless feedback for the model to self-correct from within the same
    # ReAct loop. Failing fast here with an explicit, actionable message
    # gives it something to actually act on.
    try:
        uuid.UUID(product_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(
            f"product_id must be a UUID from a previous search_products or get_cart result, "
            f"got {product_id!r} — do not use a product's name or description as its id."
        ) from exc


class OrdersToolsClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"X-Internal-Token": token}

    async def get_order_status(self, token: str, order_id: str) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/orders/admin/{order_id}", headers=self._headers(token))
        resp.raise_for_status()
        return resp.json()

    async def list_customer_orders(self, token: str, customer_id: str, limit: int = 5) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{self._base_url}/orders/admin",
                params={"owner_id": customer_id},
                headers=self._headers(token),
            )
        resp.raise_for_status()
        return resp.json()[:limit]

    # Orders has no server-side filter for "stuck in Pending" -- this pulls
    # the full admin list and filters client-side, same trade-off as
    # get_unavailable_items in tools/inventory.py. Fine for a thin,
    # low-volume admin tool; would need a real query param on GET
    # /orders/admin if this became a hot path.
    async def get_pending_orders(self, token: str, older_than_minutes: int = 60) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/orders/admin", headers=self._headers(token))
        resp.raise_for_status()
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
        return [
            order
            for order in resp.json()
            if order["status"] == "pending" and datetime.fromisoformat(order["created_at"]) <= cutoff
        ]

    # --- STR-146: cart write-tools. These proxy Orders' existing /cart
    # endpoints unchanged — ownership is enforced entirely by Orders scoping
    # every query to the forwarded token's `sub` (see
    # services/orders/src/orders/routers/cart.py), so there's no
    # customer_id argument here for an LLM to hallucinate: whoever's token
    # is forwarded is whose cart gets touched, full stop.
    async def get_cart(self, token: str) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/cart", headers=self._headers(token))
        resp.raise_for_status()
        return resp.json()

    # --- Customer-scoped order reads. Unlike get_order_status /
    # list_customer_orders above (which hit /admin and need an admin-or-
    # assistant token), these hit Orders' own customer endpoints
    # (routers/orders.py), scoped entirely to the forwarded token's `sub`:
    # `list_orders` filters `owner_id == claims.sub`, `get_order` 404s
    # (not 403 — see its comment) on anyone else's order. So there is no
    # customer_id / owner_id argument for an LLM to hallucinate — the
    # caller's own token is whose orders come back, same trust model as
    # get_cart. Read-only: no status transition, no payment.

    async def get_my_orders(self, token: str, limit: int = 5) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/orders", headers=self._headers(token))
        resp.raise_for_status()
        return resp.json()[:limit]

    async def get_my_order(self, token: str, order_id: str) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/orders/{order_id}", headers=self._headers(token))
        resp.raise_for_status()
        return resp.json()

    async def add_to_cart(self, token: str, product_id: str, quantity: int) -> dict:
        _require_uuid(product_id)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/cart",
                json={"product_id": product_id, "quantity": quantity},
                headers=self._headers(token),
            )
        resp.raise_for_status()
        return resp.json()

    async def remove_from_cart(self, token: str, product_id: str) -> dict:
        _require_uuid(product_id)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.delete(f"{self._base_url}/cart/items/{product_id}", headers=self._headers(token))
        resp.raise_for_status()
        return {"removed_product_id": product_id}
