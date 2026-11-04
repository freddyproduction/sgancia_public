#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/backup.sh
# Code/release selection is an explicit operator step before running this script.
docker compose stop api mail worker backup telegram
trap 'printf "Aggiornamento non completato: servizi applicativi lasciati fermi. Consultare docs/aggiornamenti.md e il backup appena creato.\n" >&2' ERR
docker compose build migrate
docker compose run --rm -T migrate alembic upgrade head
docker compose run --rm -T migrate alembic check
docker compose up -d
for attempt in {1..30}; do
  if docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready')" >/dev/null 2>&1; then
    printf 'Aggiornamento e controllo disponibilità riusciti. Verificare accesso e saldi.\n';exit 0
  fi
  sleep 2
done
printf 'Servizio non pronto: controllare lo stato senza ripristini automatici o downgrade.\n' >&2
exit 1
