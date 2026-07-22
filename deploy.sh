#!/usr/bin/env bash

set -Eeuo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
compose=(docker compose --env-file .env.prod -f docker-compose.prod.yml)

cd "$repo_dir"

if [[ ! -f .env.prod ]]; then
  echo "Missing $repo_dir/.env.prod" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "Tracked files have uncommitted changes; refusing to deploy over them." >&2
  git status --short
  exit 1
fi

echo "### Pulling the latest fast-forward changes ..."
git pull --ff-only

echo "### Validating the production Compose configuration ..."
"${compose[@]}" config --quiet

echo "### Building and starting production services ..."
"${compose[@]}" up -d --build --remove-orphans --wait --wait-timeout 180

echo "### Removing dangling images from previous builds ..."
docker image prune --force

echo "### Deployment status ..."
"${compose[@]}" ps
