import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from checkout_workflow.activities import (
        charge_payment,
        create_order,
        mark_order_rejected,
        publish_order_confirmed,
        release_stock,
        reserve_stock,
        update_order_status,
    )
    from checkout_workflow.types import CheckoutWorkflowInput, CheckoutWorkflowResult


@workflow.defn
class CheckoutWorkflow:
    def __init__(self) -> None:
        self._compensation_resolved = False

    # Escalation resume path (STR-139): once release_stock's activity has
    # escalated (see activities._escalate), an admin who resolved
    # compensation manually — e.g. released stock directly in Inventory's
    # DB — signals this instead of waiting on the still-unboundedly-retrying
    # activity to eventually succeed on its own.
    @workflow.signal
    async def mark_compensation_resolved(self) -> None:
        self._compensation_resolved = True

    @workflow.run
    async def run(self, checkout_request: CheckoutWorkflowInput) -> CheckoutWorkflowResult:
        # Deliberately outside the try/except below, matching the ticket's
        # sketch: nothing has been reserved yet, so a reserve_stock failure
        # (retries exhausted) has nothing to compensate — the workflow just
        # fails outright.
        await workflow.execute_activity(
            reserve_stock,
            checkout_request,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        try:
            await workflow.execute_activity(
                create_order,
                checkout_request,
                start_to_close_timeout=timedelta(seconds=15),
            )

            await workflow.execute_activity(
                charge_payment,
                checkout_request,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

            # Explicit status transition — not implicit from the payment
            # activity's own result, per the ticket's sketch.
            await workflow.execute_activity(
                update_order_status,
                {"order_id": checkout_request.order_id, "status": "paid"},
                start_to_close_timeout=timedelta(seconds=15),
            )

        except ActivityError:
            # Compensation chain, reverse order of the forward path.
            # release_stock gets an unbounded RetryPolicy — maximum_attempts=0
            # is the Python SDK's documented sentinel for "no maximum"
            # (confirmed against temporalio.common.RetryPolicy's docs before
            # using it here, per the ticket's explicit "don't guess" note),
            # so it keeps retrying with the SDK's default capped exponential
            # backoff instead of giving up and leaving the workflow silently
            # stuck.
            release_handle = workflow.start_activity(
                release_stock,
                checkout_request,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=0),
            )
            # Race the (potentially forever-retrying) compensation activity
            # against an admin's mark_compensation_resolved signal, so an
            # escalated workflow doesn't have to sit in Running state until
            # release_stock itself eventually succeeds.
            resolved = asyncio.ensure_future(workflow.wait_condition(lambda: self._compensation_resolved))
            await workflow.wait([release_handle, resolved], return_when=asyncio.FIRST_COMPLETED)
            if not release_handle.done():
                release_handle.cancel()
            else:
                # Surface a genuine failure from release_stock itself (as
                # opposed to us abandoning it via the signal above) —
                # shouldn't normally happen given the unbounded retry, but
                # don't swallow it silently if it does.
                await release_handle
            if not resolved.done():
                resolved.cancel()

            await workflow.execute_activity(
                mark_order_rejected,
                checkout_request,
                start_to_close_timeout=timedelta(seconds=15),
            )
            return CheckoutWorkflowResult(order_id=checkout_request.order_id, status="rejected")

        # Kafka, not Temporal — async fan-out for Notifications etc.
        await workflow.execute_activity(
            publish_order_confirmed,
            checkout_request,
            start_to_close_timeout=timedelta(seconds=15),
        )

        return CheckoutWorkflowResult(order_id=checkout_request.order_id, status="confirmed")
