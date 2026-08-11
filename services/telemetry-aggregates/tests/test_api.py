import uuid
from datetime import datetime, timedelta, timezone

from telemetry_aggregates.models import HourlyAggregate

NOW = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)


async def _add_row(client, store_id, product_id, hour_bucket, avg=5.0, count=1):
    async with client.app.state.session_factory() as session:
        session.add(
            HourlyAggregate(
                store_id=store_id,
                product_id=product_id,
                hour_bucket=hour_bucket,
                avg_temperature=avg,
                min_temperature=avg,
                max_temperature=avg,
                reading_count=count,
            )
        )
        await session.commit()


def _auth(token: str) -> dict:
    return {"X-Internal-Token": token}


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_get_aggregates_requires_internal_token(client):
    resp = await client.get(f"/aggregates/{uuid.uuid4()}/{uuid.uuid4()}")
    assert resp.status_code == 401


async def test_get_aggregates_requires_admin_role(client, customer_token):
    resp = await client.get(f"/aggregates/{uuid.uuid4()}/{uuid.uuid4()}", headers=_auth(customer_token))
    assert resp.status_code == 403


async def test_get_aggregates_returns_rows_for_store_and_product(client, admin_token):
    store_id, product_id = uuid.uuid4(), uuid.uuid4()
    other_product = uuid.uuid4()
    await _add_row(client, store_id, product_id, NOW - timedelta(hours=2), avg=4.0)
    await _add_row(client, store_id, product_id, NOW - timedelta(hours=1), avg=5.0)
    await _add_row(client, store_id, other_product, NOW - timedelta(hours=1), avg=99.0)

    resp = await client.get(f"/aggregates/{store_id}/{product_id}", headers=_auth(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert [row["avg_temperature"] for row in body] == [4.0, 5.0]  # ordered by hour_bucket


async def test_get_aggregates_empty_for_unknown_pair(client, admin_token):
    resp = await client.get(f"/aggregates/{uuid.uuid4()}/{uuid.uuid4()}", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_aggregates_period_filters_out_old_rows(client, admin_token):
    store_id, product_id = uuid.uuid4(), uuid.uuid4()
    await _add_row(client, store_id, product_id, NOW - timedelta(days=200), avg=1.0)  # outside "3months"
    await _add_row(client, store_id, product_id, NOW - timedelta(days=1), avg=2.0)

    resp = await client.get(
        f"/aggregates/{store_id}/{product_id}", params={"period": "3months"}, headers=_auth(admin_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["avg_temperature"] == 2.0


async def test_get_aggregates_period_all_returns_everything(client, admin_token):
    store_id, product_id = uuid.uuid4(), uuid.uuid4()
    await _add_row(client, store_id, product_id, NOW - timedelta(days=200), avg=1.0)
    await _add_row(client, store_id, product_id, NOW - timedelta(days=1), avg=2.0)

    resp = await client.get(
        f"/aggregates/{store_id}/{product_id}", params={"period": "all"}, headers=_auth(admin_token)
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2
