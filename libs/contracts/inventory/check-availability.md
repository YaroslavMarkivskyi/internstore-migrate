# Inventory: `POST /stocks/check-availability`

The sync-call contract Orders will use at checkout to verify stock before
placing an order — the single synchronous inter-service call in the system,
per the previously agreed schema (see
[docs/adr/0002-event-broker-kafka.md](../../docs/adr/0002-event-broker-kafka.md)).
Everything else between Orders and Inventory happens over Kafka
(`OrderCreated` → `StockReserved`/`StockReservationFailed`, etc.).

Reachable at `/api/inventory/stocks/check-availability` through nginx.
Availability is summed across all stocks — it does not reserve or decrement
anything; reservation is a separate future ticket (ORDC-04) alongside Orders.

## Request

```json
{
  "items": [
    { "product_id": "3c7f9e2a-3b8b-4b7a-9b8b-2f6b6a3c9f7a", "quantity": 2 },
    { "product_id": "9e1a2b3c-4d5e-4f60-8a1b-2c3d4e5f6071", "quantity": 1 }
  ]
}
```

- `items`: non-empty list.
- `product_id`: UUID. References Catalog's `Product.id` — Inventory does not
  validate that the product exists in Catalog.
- `quantity`: integer, > 0.

## Response — `200 OK`

```json
{
  "sufficient": false,
  "items": [
    {
      "product_id": "3c7f9e2a-3b8b-4b7a-9b8b-2f6b6a3c9f7a",
      "requested": 2,
      "available": 2,
      "sufficient": true
    },
    {
      "product_id": "9e1a2b3c-4d5e-4f60-8a1b-2c3d4e5f6071",
      "requested": 1,
      "available": 0,
      "sufficient": false
    }
  ]
}
```

- `sufficient` (top-level): `true` only if every requested line item is
  individually sufficient.
- `items[].available`: total quantity summed across all stocks for that
  `product_id`. `0` if the product has no `StockItem` rows anywhere
  (unknown product IDs are treated as zero stock, not an error).

## Not covered here

- Reservation, decrementing stock, or publishing `StockReserved` /
  `StockReservationFailed` — that's ORDC-04, done together with Orders.
- Any notion of per-stock availability (e.g. "enough at the nearest
  warehouse") — this endpoint only answers the sum-across-all-stocks
  question checkout needs.

## Source of truth

Implementation: [services/inventory/src/inventory/routers/stocks.py](../../services/inventory/src/inventory/routers/stocks.py).
Schemas: [services/inventory/src/inventory/schemas.py](../../services/inventory/src/inventory/schemas.py)
(`CheckAvailabilityRequest`, `CheckAvailabilityResponse`). If those diverge
from this doc, the code wins — update this file to match.
