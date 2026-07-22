#!/bin/bash

set -euo pipefail

compose=(docker compose --env-file .env.prod -f docker-compose.prod.yml)

domains=(htb.hackthevalley.io)
rsa_key_size=4096
data_path="./certbot-data"
email="dev@hackthevalley.io"
staging=0

if [ -d "$data_path/conf/live/${domains[0]}" ]; then
  read -p "Existing certificate found. Overwrite? (y/N) " decision
  if [[ "$decision" != "Y" && "$decision" != "y" ]]; then exit; fi
fi

mkdir -p "$data_path/conf"
options_url="https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf"
dhparams_url="https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem"
options_tmp="$data_path/conf/options-ssl-nginx.conf.tmp"
dhparams_tmp="$data_path/conf/ssl-dhparams.pem.tmp"

curl --fail --show-error --silent --location --retry 3 \
  "$options_url" --output "$options_tmp"
curl --fail --show-error --silent --location --retry 3 \
  "$dhparams_url" --output "$dhparams_tmp"

if ! grep -q '^ssl_protocols TLSv1.2 TLSv1.3;' "$options_tmp"; then
  echo "Downloaded options-ssl-nginx.conf failed validation" >&2
  exit 1
fi
if ! grep -q '^-----BEGIN DH PARAMETERS-----$' "$dhparams_tmp" || \
   ! grep -q '^-----END DH PARAMETERS-----$' "$dhparams_tmp"; then
  echo "Downloaded ssl-dhparams.pem failed validation" >&2
  exit 1
fi

mv "$options_tmp" "$data_path/conf/options-ssl-nginx.conf"
mv "$dhparams_tmp" "$data_path/conf/ssl-dhparams.pem"

echo "### Creating dummy certificate ..."
path="/etc/letsencrypt/live/${domains[0]}"
mkdir -p "$data_path/conf/live/${domains[0]}"
"${compose[@]}" run --rm --entrypoint "\
  openssl req -x509 -nodes -newkey rsa:$rsa_key_size -days 1\
  -keyout '$path/privkey.pem' \
  -out '$path/fullchain.pem' \
  -subj '/CN=localhost'" certbot

echo "### Starting nginx ..."
"${compose[@]}" up -d nginx

echo "### Removing dummy certificate ..."
"${compose[@]}" run --rm --entrypoint "\
  rm -Rf /etc/letsencrypt/live/${domains[0]} && \
  rm -Rf /etc/letsencrypt/archive/${domains[0]} && \
  rm -Rf /etc/letsencrypt/renewal/${domains[0]}.conf" certbot

echo "### Requesting Let's Encrypt certificate ..."
domain_args=""
for domain in "${domains[@]}"; do
  domain_args="$domain_args -d $domain"
done

email_arg="--email $email"
staging_arg=""
[ "$staging" != "0" ] && staging_arg="--staging"

"${compose[@]}" run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
  $staging_arg \
  $email_arg \
  $domain_args \
  --rsa-key-size $rsa_key_size \
  --agree-tos \
  --no-eff-email \
  --non-interactive \
  --force-renewal" certbot

echo "### Reloading nginx ..."
"${compose[@]}" exec nginx nginx -s reload
