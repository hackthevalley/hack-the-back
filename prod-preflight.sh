#!/usr/bin/env bash

set -Eeuo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo_dir"

required_files=(
  .env.prod
  certs/apple/cert.pem
  certs/apple/key.pem
  certs/apple/wwdr.pem
  certs/google/credentials.json
)

missing_files=()
for file in "${required_files[@]}"; do
  if [[ ! -r "$file" ]]; then
    missing_files+=("$file")
  fi
done

if (( ${#missing_files[@]} > 0 )); then
  echo "Production preflight failed. These required files are missing or unreadable:" >&2
  printf '  - %s\n' "${missing_files[@]}" >&2
  exit 1
fi

for secret_file in certs/apple/key.pem certs/google/credentials.json; do
  mode="$(stat -c '%a' "$secret_file")"
  if (( (8#$mode & 077) != 0 )); then
    echo "$secret_file is accessible by group or other users (mode $mode)." >&2
    echo "Run: chmod 600 $secret_file" >&2
    exit 1
  fi
done

echo "Production preflight passed."
