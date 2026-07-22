# hack-the-back

## Local development with Docker

Local Compose runs `alembic upgrade head` after PostgreSQL becomes healthy and
before FastAPI starts:

```bash
docker compose up --build
```

If your existing local volume was created before Alembic adoption, either mark
that schema as the initial revision:

```bash
docker compose build migrate
docker compose run --rm migrate uv run alembic stamp bf8b33c13520
```

Or, if the local data is disposable, recreate the local database from the
migration history:

```bash
docker compose down --volumes
docker compose up --build
```

`down --volumes` permanently deletes only this Compose project's local database
volume. Do not use it in production.

## Local development without Docker

Run migrations before starting FastAPI:

```bash
uv run alembic upgrade head
uv run fastapi dev app/main.py
```

API documentation remains enabled locally at `/docs`. Production disables it
through `ENABLE_API_DOCS=false`.
