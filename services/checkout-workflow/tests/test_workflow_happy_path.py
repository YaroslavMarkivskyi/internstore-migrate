import uuid

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from checkout_workflow.types import CheckoutWorkflowInput
from checkout_workflow.workflows import CheckoutWorkflow
from tests.conftest import make_input

TASK_QUEUE = "test-checkout-workflow"


@activity.defn(name="reserve_stock")
async def fake_reserve_stock(input: CheckoutWorkflowInput) -> dict:
    return {"order_id": input.order_id, "status": "reserved"}


@activity.defn(name="create_order")
async def fake_create_order(input: CheckoutWorkflowInput) -> dict:
    return {"id": input.order_id, "status": "new"}


@activity.defn(name="charge_payment")
async def fake_charge_payment(input: CheckoutWorkflowInput) -> dict:
    return {"payment_id": str(uuid.uuid4()), "status": "charged"}


@activity.defn(name="update_order_status")
async def fake_update_order_status(args: dict) -> dict:
    return {"order_id": args["order_id"], "status": args["status"]}


@activity.defn(name="publish_order_confirmed")
async def fake_publish_order_confirmed(input: CheckoutWorkflowInput) -> None:
    return None


async def test_happy_path_confirms_order():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[CheckoutWorkflow],
            activities=[
                fake_reserve_stock,
                fake_create_order,
                fake_charge_payment,
                fake_update_order_status,
                fake_publish_order_confirmed,
            ],
        ):
            result = await env.client.execute_workflow(
                CheckoutWorkflow.run,
                make_input(order_id=str(uuid.uuid4())),
                id=f"checkout-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )

    assert result.status == "confirmed"
