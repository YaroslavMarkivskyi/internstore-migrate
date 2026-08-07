import asyncio
import uuid

import pytest
from temporalio import activity
from temporalio.api.enums.v1 import WorkflowExecutionStatus
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
    raise ApplicationError("simulated payment failure", non_retryable=True)


@activity.defn(name="release_stock")
async def fake_release_stock_always_fails(input: CheckoutWorkflowInput) -> dict:
    # Simulates Inventory being down for compensation the whole time — this
    # activity has an unbounded RetryPolicy (workflows.py), so nothing here
    # ever stops it from being retried on its own.
    raise ApplicationError("inventory unreachable")


@activity.defn(name="mark_order_rejected")
async def fake_mark_order_rejected(input: CheckoutWorkflowInput) -> dict:
    return {"order_id": input.order_id, "status": "rejected"}


async def test_compensation_failure_stays_running_then_resolves_via_signal():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[CheckoutWorkflow],
            activities=[
                fake_reserve_stock,
                fake_create_order,
                fake_charge_payment_fails,
                fake_release_stock_always_fails,
                fake_mark_order_rejected,
            ],
        ):
            handle = await env.client.start_workflow(
                CheckoutWorkflow.run,
                make_input(order_id=str(uuid.uuid4())),
                id=f"checkout-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )

            # Real (wall-clock) sleep, not simulated workflow time — give
            # release_stock a few genuine retry cycles against the
            # time-skipping server so it's demonstrably stuck, not just
            # not-yet-scheduled.
            await asyncio.sleep(1)
            description = await handle.describe()
            assert description.status == WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_RUNNING

            # Escalation's exhausted-retries threshold is a property of the
            # real release_stock activity (see test_activities.py's
            # test_release_stock_escalates_once_attempt_crosses_threshold) —
            # here we exercise the *workflow's* side of that story: an
            # admin who has resolved compensation manually signals the
            # workflow to stop waiting on it and finish anyway.
            await handle.signal(CheckoutWorkflow.mark_compensation_resolved)
            result = await handle.result()

    assert result.status == "rejected"
