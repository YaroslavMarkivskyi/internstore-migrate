from dataclasses import replace

import httpx
import pytest
from temporalio.testing import ActivityEnvironment

from checkout_workflow import activities
from tests.conftest import make_input

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def settings_env(monkeypatch):
    monkeypatch.setenv("INTERNAL_TOKEN_SECRET", "test-secret")
    monkeypatch.setenv("INVENTORY_BASE_URL", "http://inventory.invalid")
    monkeypatch.setenv("ORDERS_BASE_URL", "http://orders.invalid")
    monkeypatch.setenv("PAYMENTS_BASE_URL", "http://payments.invalid")
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "kafka.invalid:9092")
    monkeypatch.setenv("ESCALATION_ATTEMPT_THRESHOLD", "10")


class FakeResponse:
    def __init__(self, json_body: dict, status_code: int = 200) -> None:
        self._json = json_body
        self.status_code = status_code

    def json(self) -> dict:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)


class FakeAsyncClient:
    """Records every call and returns whatever `responses` was configured
    with, in order — swapped in for httpx.AsyncClient via monkeypatch
    (activities.py has no DI seam for its httpx client, unlike the
    FastAPI services' request-scoped clients, since activities are plain
    functions rather than routes)."""

    calls: list[tuple[str, str, dict]] = []
    responses: list[FakeResponse] = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def post(self, url: str, json: dict, headers: dict) -> FakeResponse:
        FakeAsyncClient.calls.append(("POST", url, json))
        return FakeAsyncClient.responses.pop(0)

    async def patch(self, url: str, json: dict, headers: dict) -> FakeResponse:
        FakeAsyncClient.calls.append(("PATCH", url, json))
        return FakeAsyncClient.responses.pop(0)


@pytest.fixture(autouse=True)
def fake_http(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.responses = []
    monkeypatch.setattr(activities.httpx, "AsyncClient", FakeAsyncClient)
    return FakeAsyncClient


class FakeKafkaProducer:
    sent: list[tuple[str, str, dict]] = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def send(self, topic: str, event_type: str, payload: dict) -> None:
        FakeKafkaProducer.sent.append((topic, event_type, payload))


@pytest.fixture(autouse=True)
def fake_kafka(monkeypatch):
    FakeKafkaProducer.sent = []
    monkeypatch.setattr(activities, "KafkaEventProducer", FakeKafkaProducer)
    return FakeKafkaProducer


async def test_reserve_stock_calls_inventory_and_returns_reserved(fake_http):
    fake_http.responses = [FakeResponse({"order_id": "order-1", "status": "reserved"})]
    env = ActivityEnvironment()

    result = await env.run(activities.reserve_stock, make_input(order_id="order-1"))

    assert result["status"] == "reserved"
    method, url, body = fake_http.calls[0]
    assert url == "http://inventory.invalid/stocks/reserve"
    assert body["order_id"] == "order-1"


async def test_reserve_stock_raises_on_insufficient_stock(fake_http):
    fake_http.responses = [FakeResponse({"order_id": "order-1", "status": "insufficient_stock"})]
    env = ActivityEnvironment()

    with pytest.raises(activities.ActivityError):
        await env.run(activities.reserve_stock, make_input(order_id="order-1"))


async def test_charge_payment_raises_on_failed_status(fake_http):
    fake_http.responses = [FakeResponse({"payment_id": "pay-1", "status": "failed"})]
    env = ActivityEnvironment()

    with pytest.raises(activities.ActivityError):
        await env.run(activities.charge_payment, make_input(order_id="order-1", amount=19.99))


async def test_create_order_posts_id_and_items(fake_http):
    fake_http.responses = [FakeResponse({"id": "order-1", "status": "new"})]
    env = ActivityEnvironment()

    await env.run(activities.create_order, make_input(order_id="order-1"))

    method, url, body = fake_http.calls[0]
    assert url == "http://orders.invalid/internal/checkout-workflow/orders"
    assert body["id"] == "order-1"
    assert body["items"] == [{"product_id": "product-1", "quantity": 2}]


async def test_mark_order_rejected_patches_status(fake_http):
    fake_http.responses = [FakeResponse({"order_id": "order-1", "status": "rejected"})]
    env = ActivityEnvironment()

    result = await env.run(activities.mark_order_rejected, make_input(order_id="order-1"))

    assert result["status"] == "rejected"
    method, url, body = fake_http.calls[0]
    assert method == "PATCH"
    assert body["status"] == "rejected"


async def test_release_stock_escalates_once_attempt_crosses_threshold(fake_http, fake_kafka):
    fake_http.responses = [FakeResponse({"order_id": "order-1", "status": "released"})]
    env = ActivityEnvironment()
    # Attempt 11 is the first attempt past escalation_attempt_threshold=10 —
    # see activities.release_stock's `== threshold + 1` check.
    env.info = replace(env.info, attempt=11)

    await env.run(activities.release_stock, make_input(order_id="order-1"))

    assert len(fake_kafka.sent) == 1
    topic, event_type, payload = fake_kafka.sent[0]
    assert topic == "ops-events"
    assert event_type == "EscalationRequired"
    assert payload["order_id"] == "order-1"


async def test_release_stock_does_not_escalate_below_threshold(fake_http, fake_kafka):
    fake_http.responses = [FakeResponse({"order_id": "order-1", "status": "released"})]
    env = ActivityEnvironment()
    env.info = replace(env.info, attempt=3)

    await env.run(activities.release_stock, make_input(order_id="order-1"))

    assert fake_kafka.sent == []
