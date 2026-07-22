# Production deployment

Production uses `docker-compose.prod.yml`. The regular `docker-compose.yml`
remains the local development stack with live reload, exposed API/database
ports, and unrestricted CORS.

## First deployment

1. Copy `.env.prod.example` to `.env.prod` on the production server.
2. Replace every placeholder. Generate `SECRET_KEY` and a URL-safe database
   password with `openssl rand -hex 32`.
3. Confirm DNS for `htb.hackthevalley.io` points to the server and ports 80 and
   443 are open.
4. Initialize the TLS certificate:

   ```bash
   ./certbot-init.sh
   ```

5. Check the services:

   ```bash
   docker compose --env-file .env.prod -f docker-compose.prod.yml ps
   docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=100
   ```

## Subsequent deployments

```bash
git pull --ff-only
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

Do not use `docker compose down --volumes`: the named volumes contain the
PostgreSQL database and uploaded resumes. Back up both volumes before upgrades.

## Local development

```bash
docker compose up --build
```

Local CORS defaults to `*`. Production restricts it through `CORS_ORIGINS` in
`.env.prod`.
