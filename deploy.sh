#!/usr/bin/env bash

set -Eeuo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
compose=(docker compose --env-file .env.prod -f docker-compose.prod.yml)

cd "$repo_dir"

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "Tracked files have uncommitted changes; refusing to deploy over them." >&2
  git status --short
  exit 1
fi

echo "### Pulling the latest fast-forward changes ..."
git pull --ff-only

revision="$(git rev-parse HEAD)"
export APP_IMAGE="ghcr.io/hackthevalley/hack-the-back:sha-$revision"

echo "### Checking production secrets and certificates ..."
./prod-preflight.sh

echo "### Validating the production Compose configuration ..."
"${compose[@]}" config --quiet

echo "### Pulling the tested application image for $revision ..."
"${compose[@]}" pull htb

echo "### Building the reverse proxy ..."
"${compose[@]}" build --provenance=false nginx

echo "### Gracefully replacing changed services and waiting for health checks ..."
"${compose[@]}" up -d --remove-orphans --wait --wait-timeout 180

echo "### Removing dangling images from previous builds ..."
docker image prune --force

echo "### Deployment status ..."
"${compose[@]}" ps
