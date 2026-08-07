FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project

COPY src ./src
RUN uv sync --no-dev

# No health-checkable HTTP port — this container is a pure Temporal task
# queue poller (services/orders is the API surface for checkout), same
# shape as Orders'/Inventory's outbox worker but split into its own
# independently killable/restartable container per STR-139's verification
# requirement (kill the worker mid-workflow, confirm it resumes).
CMD ["uv", "run", "python", "-m", "checkout_workflow.worker"]
