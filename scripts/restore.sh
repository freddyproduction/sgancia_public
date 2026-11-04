#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
if [[ $# -ne 2 || "$2" != '--confirm-restore' || ! -f "$1" ]]; then
  printf 'Uso: scripts/restore.sh backups/file.sgb --confirm-restore\nArrestare prima i servizi api, mail, worker, backup e telegram; ripristino distruttivo del database corrente.\n' >&2
  exit 2
fi
for service in $(docker compose --profile telegram ps --status running --services); do
  case "$service" in api|mail|worker|backup|telegram)
    printf 'Arrestare api, mail, worker, backup e telegram prima del ripristino: docker compose --profile telegram stop api mail worker backup telegram\n' >&2
    exit 2;;
  esac
done
mkdir -p .local
temporary="$(mktemp .local/restore.XXXXXXXX)"
database_dump="$(mktemp .local/database-restore.XXXXXXXX)"
trap 'rm -f "$temporary" "$database_dump"' EXIT
# Authenticate the entire file BEFORE any database modification.
docker compose run --rm --no-deps -T api python -m app.backup decrypt < "$1" > "$temporary"
docker compose run --rm --no-deps -T api python -m app.attachment_backup stage < "$temporary" > "$database_dump"
docker compose exec -T db pg_restore -U sgancia -d sgancia --clean --if-exists --exit-on-error --single-transaction < "$database_dump"
# Restored backups must not resurrect revoked sessions or previously delivered links.
docker compose exec -T db psql -U sgancia -d sgancia -v ON_ERROR_STOP=1 <<'SQL'
BEGIN;
DELETE FROM sessions;
DELETE FROM gate_grants;
DELETE FROM webauthn_challenges;
DO $$ BEGIN
  IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='instance' AND column_name='backup_policy') THEN EXECUTE 'UPDATE instance SET backup_policy=jsonb_set(backup_policy::jsonb, ''{enabled}'', ''false'')::json'; END IF;
  IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='instance' AND column_name='guest_links_enabled') THEN EXECUTE 'UPDATE instance SET guest_links_enabled=false'; END IF;
  IF to_regclass('maintenance_jobs') IS NOT NULL THEN EXECUTE 'UPDATE maintenance_jobs SET status=''failed'', error=''restore_review'' WHERE status IN (''pending'',''running'')'; END IF;
  IF to_regclass('service_heartbeats') IS NOT NULL THEN EXECUTE 'DELETE FROM service_heartbeats'; END IF;
  IF to_regclass('group_invitations') IS NOT NULL THEN EXECUTE 'UPDATE group_invitations SET used=true'; END IF;
  IF to_regclass('participant_claims') IS NOT NULL THEN EXECUTE 'UPDATE participant_claims SET used=true'; END IF;
  IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='invitations' AND column_name='revoked') THEN EXECUTE 'UPDATE invitations SET revoked=true WHERE NOT used'; END IF;
  IF to_regclass('invitations') IS NOT NULL THEN EXECUTE 'UPDATE invitations SET used=true'; END IF;
  IF to_regclass('expense_plans') IS NOT NULL THEN EXECUTE 'UPDATE expense_plans SET enabled=false, error=''restore_review'' WHERE kind=''recurring'''; END IF;
  IF to_regclass('guest_links') IS NOT NULL THEN EXECUTE 'UPDATE guest_links SET revoked=true'; END IF;
  IF to_regclass('installation_challenges') IS NOT NULL THEN EXECUTE 'DELETE FROM installation_challenges'; END IF;
  IF to_regclass('installation_passkeys') IS NOT NULL THEN EXECUTE 'DELETE FROM installation_passkeys'; END IF;
  IF to_regclass('reveal_jobs') IS NOT NULL THEN EXECUTE 'UPDATE reveal_jobs SET status=''blocked'', error=''restore_review'' WHERE status=''pending'''; END IF;
  IF to_regclass('import_batches') IS NOT NULL THEN EXECUTE 'DELETE FROM import_batches WHERE NOT applied'; END IF;
  IF to_regclass('account_tokens') IS NOT NULL THEN EXECUTE 'DELETE FROM account_tokens'; END IF;
  IF to_regclass('notification_preferences') IS NOT NULL THEN EXECUTE 'UPDATE notification_preferences SET config=jsonb_set(config::jsonb, ''{enabled}'', ''false'')::json'; END IF;
  IF to_regclass('notifications') IS NOT NULL THEN EXECUTE 'UPDATE notifications SET email_status=''cancelled'' WHERE email_status=''queued'''; END IF;
  IF to_regclass('mail_messages') IS NOT NULL THEN EXECUTE 'DELETE FROM mail_messages'; END IF;
END $$;
COMMIT;
SQL
docker compose run --rm --no-deps -T api python -m app.telegram_recovery
printf 'Database e allegati del backup ripristinati. Conservare la chiave applicativa originale e verificare prima di riavviare api.\n'
