FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
RUN uv sync --no-dev

EXPOSE 8000
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn orders.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
