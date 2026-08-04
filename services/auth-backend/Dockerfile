FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project

COPY src ./src
RUN uv sync --no-dev

EXPOSE 3000
CMD ["sh", "-c", "uv run uvicorn auth_backend.main:create_app --factory --host 0.0.0.0 --port ${PORT:-3000} --reload"]
