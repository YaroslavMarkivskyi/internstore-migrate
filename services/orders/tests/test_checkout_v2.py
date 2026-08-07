import asyncio
import uuid

import pytest

from orders.temporal_client import get_temporal_client

CHECKOUT_PAYLOAD = {
    "contact_name": "Jane Doe",
    "contact_email": "jane@example.com",
    "contact_phone": "+15551234567",
    "payment_method": "card",
}


class FakeDescription:
    class _Status:
        def __init__(self, name: str) -> None:
            self.name = name

    def __init__(self, running: bool) -> None:
        self.status = self._Status(
            "WORKFLOW_EXECUTION_STATUS_RUNNING" if running else "WORKFLOW_EXECUTION_STATUS_COMPLETED"
        )


class FakeWorkflowHandle:
    """Stands in for temporalio.client.WorkflowHandle — configured per-test
    to resolve quickly, hang past the wait timeout, or raise, without a
    real Temporal server. See services/checkout-workflow's own tests for
    coverage of the actual workflow/activity behavior this fakes out."""

    def __init__(self, workflow_id: str, *, result: dict | None = None, hangs: bool = False, fails: bool = False) -> None:
        self.id = workflow_id
        self._result = result
        self._hangs = hangs
        self._fails = fails

    async def result(self) -> dict:
        if self._hangs:
            await asyncio.sleep(3600)
        if self._fails:
            from temporalio.client import WorkflowFailureError

            raise WorkflowFailureError(message="simulated failure")
        return self._result

    async def describe(self) -> FakeDescription:
        return FakeDescription(running=self._hangs)


class FakeTemporalClient:
    def __init__(self) -> None:
        self.started: list[tuple[str, dict, str]] = []
        self.next_handle_kwargs: dict = {}
        self._handles: dict[str, FakeWorkflowHandle] = {}

    async def start_workflow(self, name: str, input: dict, *, id: str, task_queue: str) -> FakeWorkflowHandle:
        self.started.append((name, input, id))
        handle = FakeWorkflowHandle(id, **self.next_handle_kwargs)
        self._handles[id] = handle
        return handle

    def get_workflow_handle(self, workflow_id: str) -> FakeWorkflowHandle:
        return self._handles.setdefault(workflow_id, FakeWorkflowHandle(workflow_id, hangs=True))


@pytest.fixture
def fake_temporal_client() -> FakeTemporalClient:
    return FakeTemporalClient()


async def _add_item(client, headers, product_id: str, quantity: int = 2) -> None:
    resp = await client.post("/cart", json={"product_id": product_id, "quantity": quantity}, headers=headers)
    assert resp.status_code == 201


async def test_checkout_v2_happy_path_returns_confirmed_and_clears_cart(
    client, customer_token, fake_catalog_client, fake_temporal_client
):
    client.app.dependency_overrides[get_temporal_client] = lambda: fake_temporal_client

    headers = {"x-internal-token": customer_token}
    product_id = str(uuid.uuid4())
    await _add_item(client, headers, product_id, quantity=2)
    fake_catalog_client.set_price(product_id, 10.0)
    fake_temporal_client.next_handle_kwargs = {"result": {"order_id": "irrelevant", "status": "confirmed"}}

    resp = await client.post("/checkout/v2", json=CHECKOUT_PAYLOAD, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "confirmed"
    assert body["workflow_id"].startswith("checkout-")

    cart_resp = await client.get("/cart", headers=headers)
    assert cart_resp.json() == {"items": []}

    # The workflow was started with the total computed server-side from
    # Catalog, not trusted from the client.
    name, workflow_input, workflow_id = fake_temporal_client.started[0]
    assert name == "CheckoutWorkflow"
    assert workflow_input["amount"] == 20.0
    assert workflow_id == body["workflow_id"]


async def test_checkout_v2_falls_back_to_202_on_wait_timeout(
    client, customer_token, fake_catalog_client, fake_temporal_client
):
    client.app.dependency_overrides[get_temporal_client] = lambda: fake_temporal_client
    client.app.state.settings.checkout_v2_wait_seconds = 0.05

    headers = {"x-internal-token": customer_token}
    product_id = str(uuid.uuid4())
    await _add_item(client, headers, product_id, quantity=1)
    fake_catalog_client.set_price(product_id, 5.0)
    fake_temporal_client.next_handle_kwargs = {"hangs": True}

    resp = await client.post("/checkout/v2", json=CHECKOUT_PAYLOAD, headers=headers)
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "running"
    assert body["workflow_id"]

    # Cart is still cleared even though the workflow hasn't finished —
    # checkout has been handed off, same timing as the existing /checkout.
    cart_resp = await client.get("/cart", headers=headers)
    assert cart_resp.json() == {"items": []}


async def test_checkout_v2_empty_cart_returns_422(client, customer_token, fake_temporal_client):
    client.app.dependency_overrides[get_temporal_client] = lambda: fake_temporal_client
    headers = {"x-internal-token": customer_token}

    resp = await client.post("/checkout/v2", json=CHECKOUT_PAYLOAD, headers=headers)
    assert resp.status_code == 422
    assert fake_temporal_client.started == []


async def test_checkout_v2_returns_503_when_temporal_unavailable(client, customer_token):
    client.app.dependency_overrides[get_temporal_client] = lambda: None
    headers = {"x-internal-token": customer_token}

    resp = await client.post("/checkout/v2", json=CHECKOUT_PAYLOAD, headers=headers)
    assert resp.status_code == 503


async def test_get_checkout_v2_status_running(client, customer_token, fake_temporal_client):
    client.app.dependency_overrides[get_temporal_client] = lambda: fake_temporal_client
    headers = {"x-internal-token": customer_token}
    workflow_id = f"checkout-{uuid.uuid4()}"
    fake_temporal_client._handles[workflow_id] = FakeWorkflowHandle(workflow_id, hangs=True)

    resp = await client.get(f"/checkout/v2/{workflow_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


async def test_internal_create_order_is_idempotent_by_id(client, admin_token):
    headers = {"x-internal-token": admin_token}
    order_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    payload = {
        "id": order_id,
        "owner_id": "customer-1",
        "contact_name": "Ada Lovelace",
        "contact_email": "ada@example.com",
        "contact_phone": None,
        "payment_method": "card",
        "items": [{"product_id": product_id, "quantity": 2}],
    }

    first = await client.post("/internal/checkout-workflow/orders", json=payload, headers=headers)
    second = await client.post("/internal/checkout-workflow/orders", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"] == order_id
    assert first.json()["items"] == [{"product_id": product_id, "quantity": 2}]


async def test_internal_update_order_status_unknown_order_404(client, admin_token):
    headers = {"x-internal-token": admin_token}
    resp = await client.patch(
        f"/internal/checkout-workflow/orders/{uuid.uuid4()}/status",
        json={"status": "paid"},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_internal_update_order_status_sets_status(client, admin_token):
    headers = {"x-internal-token": admin_token}
    order_id = str(uuid.uuid4())
    await client.post(
        "/internal/checkout-workflow/orders",
        json={
            "id": order_id,
            "owner_id": "customer-1",
            "contact_name": "Ada Lovelace",
            "contact_email": "ada@example.com",
            "contact_phone": None,
            "payment_method": "card",
            "items": [{"product_id": str(uuid.uuid4()), "quantity": 1}],
        },
        headers=headers,
    )

    resp = await client.patch(
        f"/internal/checkout-workflow/orders/{order_id}/status",
        json={"status": "paid"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "paid"
