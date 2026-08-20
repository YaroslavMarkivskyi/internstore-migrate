FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project

COPY src ./src
RUN uv sync --no-dev

EXPOSE 8090
CMD ["sh", "-c", "uv run uvicorn internal_gate.main:create_app --factory --host 127.0.0.1 --port ${PORT:-8090} --reload"]
