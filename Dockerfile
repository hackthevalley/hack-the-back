FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED 1
 
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/ 
ENV PATH="/app/.venv/bin:$PATH"
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates postgresql && apt-get clean

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project


RUN mkdir /htb/

ENV PYTHONPATH=/htb/

COPY ./pyproject.toml ./uv.lock ./.env /htb/

COPY ./app /htb/app

WORKDIR /htb
# install python dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen
EXPOSE 8000