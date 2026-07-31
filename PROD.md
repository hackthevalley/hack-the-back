# Production deployment

Production uses `docker-compose.prod.yml`. The regular `docker-compose.yml`
remains the local development stack with live reload, exposed API/database
ports, and unrestricted CORS.

## First deployment

1. Copy `.env.prod.example` to `.env.prod` on the production server.
2. Replace every placeholder. Generate `SECRET_KEY` and a URL-safe database
   password with `openssl rand -hex 32`.
3. Copy the wallet credentials to these paths on the server:

   ```text
   certs/apple/cert.pem
   certs/apple/key.pem
   certs/apple/wwdr.pem
   certs/google/credentials.json
   ```

   Protect the private credentials:

   ```bash
   chmod 600 certs/apple/key.pem certs/google/credentials.json
   ```

   These files stay outside Git and are mounted read-only into the API
   container.
4. Run the production preflight:

   ```bash
   ./prod-preflight.sh
   ```

5. Confirm DNS for `htb.hackthevalley.io` points to the server and ports 80 and
   443 are open.
6. Initialize the TLS certificate:

   ```bash
   ./certbot-init.sh
   ```

7. Check the services:

   ```bash
   docker compose --env-file .env.prod -f docker-compose.prod.yml ps
   docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=100
   ```

## Subsequent deployments

Wait for the `Backend tests` workflow to finish successfully for the commit on
`main`, then run:

```bash
./deploy.sh
```

The workflow builds the production image after tests pass and publishes both
`main` and immutable `sha-<full-commit>` tags to
`ghcr.io/hackthevalley/hack-the-back`. The deploy script pulls the immutable tag
matching the checked-out revision, runs migrations, and replaces the API only
after its health check passes.

The container package must be public for anonymous pulls from the droplet. After
the workflow publishes it for the first time, open the package settings on
GitHub and change its visibility to public. If the package remains private,
authenticate Docker on the droplet with a read-only classic personal access
token before deploying:

```bash
echo "$GHCR_READ_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

## One-time Alembic adoption

The existing production database was originally created with SQLModel
`create_all()` and therefore has no Alembic revision marker. Before the first
deployment containing the migration service, take a database backup, copy the
new files to the server, and mark the existing schema as the reviewed baseline:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml pull htb
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm migrate \
  uv run --no-sync alembic stamp bf8b33c13520
```

This command does not alter application tables; it records that the existing
schema corresponds to the initial revision. Confirm it before deploying:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm migrate \
  uv run --no-sync alembic current
```

Future deployments run `alembic upgrade head` once before FastAPI starts. Fresh
databases are created entirely from the migration history; application workers
only seed default rows.

Do not use `docker compose down --volumes`: the named volumes contain the
PostgreSQL database and uploaded resumes. Back up both volumes before upgrades.

## Local development

```bash
docker compose up --build
```

Local CORS defaults to `*`. Production restricts it through `CORS_ORIGINS` in
`.env.prod`.
