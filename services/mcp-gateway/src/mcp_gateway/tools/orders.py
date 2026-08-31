import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from mcp_gateway.models import ProductEmbedding

logger = logging.getLogger(__name__)


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
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        session_factory: async_sessionmaker | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        # Optional: the mirrored product_embeddings table (same AI_DB_URL as
        # ProductSearchClient). Used only to enrich cart responses with
        # names/prices/totals — see _enrich_cart. None in tests that only
        # care about the HTTP proxying, in which case the cart is returned
        # with quantities but no prices.
        self._session_factory = session_factory

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"X-Internal-Token": token}

    async def _enrich_cart(self, cart: dict) -> dict:
        """Orders stores only {product_id, quantity} per line (no price
        snapshot — see services/orders/src/orders/routers/cart.py). The
        shopping agent needs real names and a real total to report back
        (it must not do the arithmetic itself), so join each line to the
        mirrored product_embeddings row for name + current price and sum a
        cart total here."""
        items = cart.get("items") or []
        product_ids: list[uuid.UUID] = []
        for item in items:
            try:
                product_ids.append(uuid.UUID(str(item["product_id"])))
            except (KeyError, ValueError, TypeError):
                continue

        catalog: dict[str, tuple[str | None, float | None]] = {}
        if product_ids and self._session_factory is not None:
            try:
                async with self._session_factory() as session:
                    rows = await session.execute(
                        select(ProductEmbedding.product_id, ProductEmbedding.name, ProductEmbedding.price).where(
                            ProductEmbedding.product_id.in_(product_ids)
                        )
                    )
                    for row in rows:
                        catalog[str(row.product_id)] = (row.name, row.price)
            except Exception as exc:  # best-effort — the cart itself must still come back
                logger.warning("Cart price enrichment failed, returning quantities only: %s", exc)

        enriched: list[dict] = []
        total = 0.0
        priced = False
        for item in items:
            pid = str(item.get("product_id"))
            quantity = item.get("quantity", 0)
            name, unit_price = catalog.get(pid, (None, None))
            line_total = round(unit_price * quantity, 2) if unit_price is not None else None
            if line_total is not None:
                total += line_total
                priced = True
            enriched.append(
                {
                    "product_id": pid,
                    "name": name,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "line_total": line_total,
                }
            )
        return {"items": enriched, "total": round(total, 2) if priced else None}

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
        return await self._enrich_cart(resp.json())

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
        return await self._enrich_cart(resp.json())

    async def remove_from_cart(self, token: str, product_id: str) -> dict:
        _require_uuid(product_id)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.delete(f"{self._base_url}/cart/items/{product_id}", headers=self._headers(token))
            resp.raise_for_status()
            # Orders' DELETE returns 204 with no body — re-read so the agent
            # gets the updated cart (with the new total) to report from.
            cart_resp = await client.get(f"{self._base_url}/cart", headers=self._headers(token))
        cart_resp.raise_for_status()
        return await self._enrich_cart(cart_resp.json())
