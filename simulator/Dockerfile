# IoT fleet simulator (ADR-0019). Build context: this directory.
FROM ghcr.io/astral-sh/uv:0.12.19 AS uv

FROM python:3.13.15-slim-trixie AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src
# Dependencies first, so that code changes reuse the cached layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.13.15-slim-trixie
RUN useradd --system --uid 10001 --no-create-home simulator
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1
USER simulator
ENTRYPOINT ["veritrace-simulator"]
CMD ["--help"]
