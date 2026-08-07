import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from checkout_workflow.activities import (
    charge_payment,
    create_order,
    mark_order_rejected,
    publish_order_confirmed,
    refund_payment,
    release_stock,
    reserve_stock,
    update_order_status,
)
from checkout_workflow.config import load_settings
from checkout_workflow.workflows import CheckoutWorkflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = load_settings()
    logger.info("Connecting to Temporal at %s", settings.temporal_host)
    client = await Client.connect(settings.temporal_host)

    # Runs as its own container/deployment (services/checkout-workflow's
    # Dockerfile), independently killable/restartable from any API-serving
    # pod — see docker-compose.yml's checkout-workflow-worker service and
    # STR-139's verification step (kill the worker mid-workflow, confirm it
    # resumes from Temporal's persisted history on restart rather than
    # losing state).
    worker = Worker(
        client,
        task_queue=settings.task_queue,
        workflows=[CheckoutWorkflow],
        activities=[
            reserve_stock,
            release_stock,
            create_order,
            update_order_status,
            mark_order_rejected,
            charge_payment,
            refund_payment,
            publish_order_confirmed,
        ],
    )
    logger.info("Polling task queue %s", settings.task_queue)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
