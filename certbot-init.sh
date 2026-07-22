#!/bin/bash

set -euo pipefail

compose=(docker compose --env-file .env.prod -f docker-compose.prod.yml)

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo_dir"

./prod-preflight.sh

domains=(htb.hackthevalley.io)
rsa_key_size=4096
data_path="./certbot-data"
email="dev@hackthevalley.io"
staging=0

certificate_exists=0
if [ -d "$data_path/conf/live/${domains[0]}" ]; then
  certificate_exists=1
  read -p "Existing certificate found. Overwrite? (y/N) " decision
  if [[ "$decision" != "Y" && "$decision" != "y" ]]; then exit; fi
fi

mkdir -p "$data_path/conf"

echo "### Stopping nginx so Certbot can listen on port 80 ..."
"${compose[@]}" stop nginx

if [ "$certificate_exists" = "1" ]; then
  echo "### Removing existing certificate ..."
  "${compose[@]}" run --rm --entrypoint sh certbot -c "\
    rm -rf /etc/letsencrypt/live/${domains[0]} \
           /etc/letsencrypt/archive/${domains[0]} \
           /etc/letsencrypt/renewal/${domains[0]}.conf"
fi

certbot_args=(
  certonly
  --standalone
  --preferred-challenges http
  --email "$email"
  --rsa-key-size "$rsa_key_size"
  --agree-tos
  --no-eff-email
  --non-interactive
)

for domain in "${domains[@]}"; do
  certbot_args+=(-d "$domain")
done

if [ "$staging" != "0" ]; then
  certbot_args+=(--staging)
fi

echo "### Requesting Let's Encrypt certificate on port 80 ..."
"${compose[@]}" run --rm --publish 80:80 \
  --entrypoint certbot certbot "${certbot_args[@]}"

echo "### Starting the production services ..."
"${compose[@]}" up --build -d nginx certbot
