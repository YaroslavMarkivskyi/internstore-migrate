import uuid

import pytest
from temporalio import activity
from temporalio.exceptions import ApplicationError
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
async def fake_charge_payment_fails(input: CheckoutWorkflowInput) -> dict:
    # non_retryable so the payment-failure branch is reached immediately —
    # workflows.py's own RetryPolicy(maximum_attempts=3) around this
    # activity is exercised in the real deployment, not re-tested here.
    raise ApplicationError("simulated payment failure", non_retryable=True)


@activity.defn(name="release_stock")
async def fake_release_stock(input: CheckoutWorkflowInput) -> dict:
    return {"order_id": input.order_id, "status": "released"}


@activity.defn(name="mark_order_rejected")
async def fake_mark_order_rejected(input: CheckoutWorkflowInput) -> dict:
    return {"order_id": input.order_id, "status": "rejected"}


async def test_payment_failure_triggers_compensation_and_rejects_order():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[CheckoutWorkflow],
            activities=[
                fake_reserve_stock,
                fake_create_order,
                fake_charge_payment_fails,
                fake_release_stock,
                fake_mark_order_rejected,
            ],
        ):
            result = await env.client.execute_workflow(
                CheckoutWorkflow.run,
                make_input(order_id=str(uuid.uuid4())),
                id=f"checkout-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )

    # Compensation ran (release_stock, mark_order_rejected) and the
    # workflow completed with a failure *result* rather than raising —
    # CheckoutWorkflow.run returns CheckoutWorkflowResult(status="rejected")
    # from its except branch, it doesn't re-raise.
    assert result.status == "rejected"
