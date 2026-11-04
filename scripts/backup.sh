#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
mkdir -p backups
backup_file="backups/sgancia-$(date -u +%Y%m%dT%H%M%SZ)-${RANDOM}.sgb"
temporary="${backup_file}.partial"
trap 'rm -f "$temporary"' EXIT
docker compose exec -T db pg_dump -U sgancia -Fc sgancia | docker compose run --rm --no-deps -T api python -m app.attachment_backup pack | docker compose run --rm --no-deps -T api python -m app.backup encrypt > "$temporary"
mv "$temporary" "$backup_file"
printf 'Backup cifrato creato: %s\n' "$backup_file"
