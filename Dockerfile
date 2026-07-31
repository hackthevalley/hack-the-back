FROM python:3.14.6-slim-bookworm

ENV PYTHONUNBUFFERED=1
ENV PATH="/htb/.venv/bin:$PATH"
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /htb

COPY ./pyproject.toml ./uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

ENV PYTHONPATH=/htb/

COPY ./app /htb/app
COPY ./alembic.ini /htb/alembic.ini
COPY ./alembic /htb/alembic
COPY ./templates /htb/templates
COPY ./images /htb/images

EXPOSE 8000
