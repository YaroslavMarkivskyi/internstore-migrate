import uuid
from datetime import datetime, timedelta, timezone

from telemetry.models import Incident, Store


async def _seed_store_and_incidents(client, count: int) -> tuple[str, list[uuid.UUID]]:
    store_id = uuid.uuid4()
    async with client.app.state.session_factory() as session:
        session.add(Store(id=store_id, name=str(store_id)))
        await session.flush()
        ids = []
        for i in range(count):
            incident = Incident(
                store_id=store_id,
                product_id=uuid.uuid4(),
                started_at=datetime.now(timezone.utc) - timedelta(minutes=count - i),
                temperature_at_outbreak=10.0,
                deviation=2.0,
            )
            session.add(incident)
            await session.flush()
            ids.append(incident.id)
        await session.commit()
    return str(store_id), ids


async def test_list_incidents_not_found(client, admin_token):
    resp = await client.get(f"/stores/{uuid.uuid4()}/incidents", headers={"x-internal-token": admin_token})
    assert resp.status_code == 404


async def test_list_incidents_requires_admin(client, customer_token):
    store_id, _ = await _seed_store_and_incidents(client, 1)
    resp = await client.get(f"/stores/{store_id}/incidents", headers={"x-internal-token": customer_token})
    assert resp.status_code == 403


async def test_list_incidents_returns_all_for_store(client, admin_token):
    store_id, ids = await _seed_store_and_incidents(client, 3)
    resp = await client.get(f"/stores/{store_id}/incidents", headers={"x-internal-token": admin_token})
    assert resp.status_code == 200
    assert len(resp.json()) == 3


async def test_delete_last_incident_removes_only_most_recent(client, admin_token):
    store_id, ids = await _seed_store_and_incidents(client, 3)

    resp = await client.delete(f"/stores/{store_id}/incidents/last", headers={"x-internal-token": admin_token})
    assert resp.status_code == 204

    remaining = await client.get(f"/stores/{store_id}/incidents", headers={"x-internal-token": admin_token})
    remaining_ids = {row["id"] for row in remaining.json()}
    assert remaining_ids == {str(ids[0]), str(ids[1])}  # the most recent (ids[2]) was removed


async def test_delete_all_incidents(client, admin_token):
    store_id, _ = await _seed_store_and_incidents(client, 3)

    resp = await client.delete(f"/stores/{store_id}/incidents", headers={"x-internal-token": admin_token})
    assert resp.status_code == 204

    remaining = await client.get(f"/stores/{store_id}/incidents", headers={"x-internal-token": admin_token})
    assert remaining.json() == []
