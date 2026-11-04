# Catalogo database generato

Generato dai modelli SQLAlchemy; le migrazioni restano la fonte per vincoli SQL aggiuntivi. Nessun dato di installazione incluso.

## account_tokens

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| token_hash | VARCHAR(64) | no |  |
| user_id | VARCHAR(36) | no | users.id |
| purpose | VARCHAR(16) | no |  |
| email | VARCHAR(254) | no |  |
| auth_version | INTEGER | no |  |
| expires | BIGINT | no |  |
| used | BOOLEAN | no |  |

## attachments

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| group_id | VARCHAR(36) | no | groups.id |
| expense_id | VARCHAR(36) | sì | expense_versions.expense_id |
| settlement_id | VARCHAR(36) | sì | settlements.id |
| expense_revision | INTEGER | sì | expense_versions.version |
| uploader_id | VARCHAR(36) | no | users.id |
| storage_key | VARCHAR(40) | no |  |
| filename | VARCHAR(180) | no |  |
| media_type | VARCHAR(60) | no |  |
| size | BIGINT | no |  |
| preview_size | BIGINT | no |  |
| sha256 | VARCHAR(64) | no |  |
| deleted | BOOLEAN | no |  |
| created | BIGINT | no |  |

## audit_events

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| actor | VARCHAR(36) | sì |  |
| event | VARCHAR(60) | no |  |
| resource | VARCHAR(36) | sì |  |
| at | BIGINT | no |  |

## budgets

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| group_id | VARCHAR(36) | no | groups.id |
| user_id | VARCHAR(36) | no | users.id |
| participant_id | VARCHAR(36) | no | participants.id |
| name | VARCHAR(100) | no |  |
| scope | VARCHAR(12) | no |  |
| currency | VARCHAR(3) | no |  |
| amount | BIGINT | no |  |
| threshold | INTEGER | no |  |
| start | VARCHAR(10) | no |  |
| end | VARCHAR(10) | no |  |
| category | VARCHAR(60) | no |  |
| tag | VARCHAR(40) | no |  |
| version | INTEGER | no |  |

## categories

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| group_id | VARCHAR(36) | no | groups.id |
| name | VARCHAR(60) | no |  |
| name_key | VARCHAR(180) | no |  |

## currency_changes

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| group_id | VARCHAR(36) | no | groups.id |
| actor_id | VARCHAR(36) | no | users.id |
| snapshot | JSON | no |  |
| created | BIGINT | no |  |

## expense_disputes

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| expense_id | VARCHAR(36) | no | expenses.id |
| participant_id | VARCHAR(36) | no | participants.id |
| version | INTEGER | no |  |
| reason | VARCHAR(2000) | no |  |
| status | VARCHAR(16) | no |  |
| resolution | VARCHAR(2000) | no |  |
| resolver_id | VARCHAR(36) | sì | users.id |
| created | BIGINT | no |  |
| resolved_at | BIGINT | sì |  |

## expense_jobs

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| plan_id | VARCHAR(36) | no | expense_plans.id |
| date | VARCHAR(10) | no |  |
| audience | JSON | sì |  |
| status | VARCHAR(16) | no |  |
| attempts | INTEGER | no |  |
| next_attempt | BIGINT | no |  |
| error | VARCHAR(40) | no |  |
| expense_id | VARCHAR(36) | sì | expenses.id |

## expense_plans

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| group_id | VARCHAR(36) | no | groups.id |
| owner_id | VARCHAR(36) | no | users.id |
| participant_id | VARCHAR(36) | no | participants.id |
| name | VARCHAR(100) | no |  |
| kind | VARCHAR(20) | no |  |
| draft | JSON | no |  |
| audience | JSON | sì |  |
| currency | VARCHAR(3) | no |  |
| frequency | VARCHAR(12) | no |  |
| interval | INTEGER | no |  |
| start | VARCHAR(10) | no |  |
| until | VARCHAR(10) | sì |  |
| cursor | INTEGER | no |  |
| enabled | BOOLEAN | no |  |
| auto_fx | BOOLEAN | no |  |
| version | INTEGER | no |  |
| error | VARCHAR(40) | no |  |

## expense_versions

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| expense_id | VARCHAR(36) | no | expenses.id |
| version | INTEGER | no |  |
| actor_id | VARCHAR(36) | no | users.id |
| snapshot | JSON | no |  |
| created | BIGINT | no |  |

## expenses

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| group_id | VARCHAR(36) | no | groups.id |
| author_id | VARCHAR(36) | no | users.id |
| title | VARCHAR(200) | no |  |
| description | VARCHAR(4000) | no |  |
| date | VARCHAR(10) | no |  |
| category | VARCHAR(60) | no |  |
| total | BIGINT | no |  |
| version | INTEGER | no |  |
| audience | JSON | sì |  |
| deleted | BOOLEAN | no |  |
| items | JSON | no |  |

## final_reports

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| group_id | VARCHAR(36) | no | groups.id |
| user_id | VARCHAR(36) | no | users.id |
| participant_id | VARCHAR(36) | no | participants.id |
| snapshot | JSON | no |  |
| created | BIGINT | no |  |

## gate_grants

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| credential_id | VARCHAR(1400) | sì |  |
| token_hash | VARCHAR(64) | no |  |
| expires | BIGINT | no |  |
| version | INTEGER | no |  |

## group_invitations

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| issuer_id | VARCHAR(36) | sì | users.id |
| accepted_user_id | VARCHAR(36) | sì | users.id |
| token_hash | VARCHAR(64) | no |  |
| group_id | VARCHAR(36) | no | groups.id, participants.group_id |
| role | VARCHAR(16) | no |  |
| email | VARCHAR(254) | sì |  |
| expires | BIGINT | no |  |
| used | BOOLEAN | no |  |
| participant_id | VARCHAR(36) | sì | participants.id |

## group_join_codes

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| token_hash | VARCHAR(64) | no |  |
| group_id | VARCHAR(36) | no | groups.id |
| role | VARCHAR(16) | no |  |
| secret | BLOB | no |  |

## group_operations

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| group_id | VARCHAR(36) | no | groups.id |
| actor_id | VARCHAR(36) | no | users.id |
| kind | VARCHAR(30) | no |  |
| snapshot | JSON | no |  |
| created | BIGINT | no |  |

## groups

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| name | VARCHAR(100) | no |  |
| currency | VARCHAR(3) | no |  |
| state | VARCHAR(16) | no |  |
| owner_id | VARCHAR(36) | no | users.id |
| description | VARCHAR(2000) | no |  |
| icon | VARCHAR(16) | no |  |
| image | BLOB | sì |  |
| metadata_version | INTEGER | no |  |
| smart_balances | BOOLEAN | no |  |
| deleted | BOOLEAN | no |  |

## guest_links

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| group_id | VARCHAR(36) | no | groups.id |
| token_hash | VARCHAR(64) | no |  |
| password_hash | VARCHAR(256) | sì |  |
| expires | BIGINT | no |  |
| revoked | BOOLEAN | no |  |
| uses | INTEGER | no |  |
| max_uses | INTEGER | sì |  |
| show_names | BOOLEAN | no |  |
| show_details | BOOLEAN | no |  |
| show_attachments | BOOLEAN | no |  |
| show_exports | BOOLEAN | no |  |

## idempotency_records

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| key | VARCHAR(200) | no |  |
| user_id | VARCHAR(36) | no | users.id |
| request_hash | VARCHAR(64) | no |  |
| response | JSON | no |  |

## import_batches

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| group_id | VARCHAR(36) | no | groups.id |
| user_id | VARCHAR(36) | no | users.id |
| participant_id | VARCHAR(36) | no | participants.id |
| currency | VARCHAR(3) | no |  |
| payload | VARCHAR | no |  |
| expires | BIGINT | no |  |
| applied | BOOLEAN | no |  |
| response | JSON | sì |  |

## imported_expenses

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| group_id | VARCHAR(36) | no | groups.id |
| participant_id | VARCHAR(36) | no | participants.id |
| origin | VARCHAR(64) | no |  |
| expense_id | VARCHAR(36) | no | expenses.id |

## installation_challenges

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(64) | no |  |
| user_id | VARCHAR(36) | sì | users.id |
| purpose | VARCHAR(10) | no |  |
| challenge | VARCHAR(128) | no |  |
| gate_version | INTEGER | no |  |
| auth_version | INTEGER | sì |  |
| expires | BIGINT | no |  |

## installation_passkeys

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| credential_id | VARCHAR(1400) | no |  |
| user_id | VARCHAR(36) | no | users.id |
| public_key | VARCHAR(3000) | no |  |
| sign_count | BIGINT | no |  |
| name | VARCHAR(100) | no |  |
| gate_version | INTEGER | no |  |
| auth_version | INTEGER | no |  |

## instance

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | INTEGER | no |  |
| gate_hash | VARCHAR(256) | no |  |
| gate_version | INTEGER | no |  |
| gate_enabled | BOOLEAN | no |  |
| guest_links_enabled | BOOLEAN | no |  |
| superadmin_id | VARCHAR(36) | sì | users.id |
| runtime_policy | JSON | no |  |
| backup_policy | JSON | no |  |
| telegram_config | VARCHAR(4000) | sì |  |
| smtp_config | VARCHAR(16000) | sì |  |
| registration | VARCHAR(20) | no |  |

## invitations

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| token_hash | VARCHAR(64) | no |  |
| email | VARCHAR(254) | no |  |
| expires | BIGINT | no |  |
| used | BOOLEAN | no |  |
| id | VARCHAR(36) | no |  |
| created | BIGINT | no |  |
| revoked | BOOLEAN | no |  |
| version | INTEGER | no |  |
| issuer_id | VARCHAR(36) | sì | users.id |
| used_by | VARCHAR(36) | sì | users.id |
| requested_role | VARCHAR(16) | no |  |
| issuer_auth_version | INTEGER | sì |  |

## ledger_entries

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| group_id | VARCHAR(36) | no | expenses.group_id, participants.group_id |
| expense_id | VARCHAR(36) | no | expenses.id |
| participant_id | VARCHAR(36) | no | participants.id |
| revision | INTEGER | no |  |
| paid | BIGINT | no |  |
| owed | BIGINT | no |  |

## mail_messages

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| payload | VARCHAR(24000) | no |  |
| token_hash | VARCHAR(64) | sì |  |
| expires | BIGINT | no |  |
| attempts | INTEGER | no |  |
| next_attempt | BIGINT | no |  |
| status | VARCHAR(16) | no |  |

## maintenance_jobs

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| slot | VARCHAR(160) | no |  |
| kind | VARCHAR(20) | no |  |
| status | VARCHAR(20) | no |  |
| requested_by | VARCHAR(36) | sì | users.id |
| created | BIGINT | no |  |
| started | BIGINT | sì |  |
| finished | BIGINT | sì |  |
| error | VARCHAR(40) | no |  |
| result | JSON | no |  |

## notification_preferences

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| user_id | VARCHAR(36) | no | users.id |
| scope | VARCHAR(36) | no |  |
| config | JSON | no |  |
| started_at | BIGINT | no |  |

## notifications

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| user_id | VARCHAR(36) | no | users.id |
| group_id | VARCHAR(36) | no | groups.id |
| event_key | VARCHAR(180) | no |  |
| kind | VARCHAR(20) | no |  |
| resource | VARCHAR(36) | no |  |
| audience | JSON | sì |  |
| participant_id | VARCHAR(36) | no | participants.id |
| created | BIGINT | no |  |
| read_at | BIGINT | sì |  |
| email_status | VARCHAR(20) | no |  |
| folder | VARCHAR(16) | no |  |

## participant_claims

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| issuer_id | VARCHAR(36) | sì | users.id |
| token_hash | VARCHAR(64) | no |  |
| participant_id | VARCHAR(36) | no | participants.id |
| email | VARCHAR(254) | no |  |
| expires | BIGINT | no |  |
| used | BOOLEAN | no |  |

## participants

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| group_id | VARCHAR(36) | no | groups.id |
| name | VARCHAR(100) | no |  |
| user_id | VARCHAR(36) | sì | users.id |
| role | VARCHAR(16) | no |  |
| active | BOOLEAN | no |  |
| merged_into | VARCHAR(36) | sì |  |

## passkeys

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| credential_id | VARCHAR(1400) | no |  |
| user_id | VARCHAR(36) | no | users.id |
| public_key | VARCHAR(3000) | no |  |
| sign_count | BIGINT | no |  |
| name | VARCHAR(100) | no |  |

## payment_methods

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| user_id | VARCHAR(36) | no | users.id |
| payload | VARCHAR(24000) | no |  |
| image | BLOB | sì |  |
| shared | BOOLEAN | no |  |
| version | INTEGER | no |  |

## rate_buckets

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| key | VARCHAR(64) | no |  |
| hits | INTEGER | no |  |
| window | BIGINT | no |  |

## recovery_codes

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| code_hash | VARCHAR(64) | no |  |
| user_id | VARCHAR(36) | no | users.id |

## reveal_jobs

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| group_id | VARCHAR(36) | no | groups.id |
| expense_id | VARCHAR(36) | no | expenses.id |
| user_id | VARCHAR(36) | no | users.id |
| participant_id | VARCHAR(36) | no | participants.id |
| audience | JSON | no |  |
| expense_version | INTEGER | no |  |
| auth_version | INTEGER | no |  |
| run_at | BIGINT | no |  |
| status | VARCHAR(20) | no |  |
| error | VARCHAR(40) | no |  |

## service_heartbeats

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| service | VARCHAR(30) | no |  |
| at | BIGINT | no |  |

## sessions

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| token_hash | VARCHAR(64) | no |  |
| user_id | VARCHAR(36) | no | users.id |
| csrf_hash | VARCHAR(64) | no |  |
| expires | BIGINT | no |  |
| created | BIGINT | no |  |
| verified | BIGINT | no |  |
| gate_version | INTEGER | no |  |
| auth_version | INTEGER | no |  |

## settlement_events

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| settlement_id | VARCHAR(36) | no | settlements.id |
| actor_id | VARCHAR(36) | no | users.id |
| status | VARCHAR(20) | no |  |
| at | BIGINT | no |  |
| reason | VARCHAR(2000) | no |  |
| ordinal | BIGINT | no |  |

## settlements

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| kind | VARCHAR(20) | no |  |
| note | VARCHAR(2000) | no |  |
| id | VARCHAR(36) | no |  |
| group_id | VARCHAR(36) | no | groups.id, participants.group_id, participants.group_id |
| sender | VARCHAR(36) | no | participants.id |
| recipient | VARCHAR(36) | no | participants.id |
| author_id | VARCHAR(36) | no | users.id |
| amount | BIGINT | no |  |
| audience | JSON | sì |  |
| status | VARCHAR(20) | no |  |
| created | BIGINT | no |  |

## telegram_actions

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| token_hash | VARCHAR(64) | no |  |
| user_id | VARCHAR(36) | no | users.id |
| telegram_id | BIGINT | no |  |
| revision | INTEGER | no |  |
| payload | TEXT | no |  |
| expires | BIGINT | no |  |

## telegram_grants

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| token_hash | VARCHAR(64) | no |  |
| user_id | VARCHAR(36) | no | users.id |
| telegram_id | BIGINT | no |  |
| auth_version | INTEGER | no |  |
| gate_version | INTEGER | no |  |
| generation | INTEGER | no |  |
| allow_private | BOOLEAN | no |  |
| notifications | BOOLEAN | no |  |
| expires | BIGINT | no |  |

## telegram_links

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| user_id | VARCHAR(36) | no | users.id |
| telegram_id | BIGINT | no |  |
| auth_version | INTEGER | no |  |
| gate_version | INTEGER | no |  |
| generation | INTEGER | no |  |
| allow_private | BOOLEAN | no |  |
| notifications | BOOLEAN | no |  |
| draft | TEXT | sì |  |
| draft_expires | BIGINT | no |  |
| revision | INTEGER | no |  |
| action_version | INTEGER | no |  |
| created | BIGINT | no |  |

## telegram_outbox

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| method | VARCHAR(24) | no |  |
| sequence | BIGINT | no |  |
| id | VARCHAR(36) | no |  |
| generation | INTEGER | no |  |
| telegram_id | BIGINT | no |  |
| user_id | VARCHAR(36) | sì | users.id |
| auth_version | INTEGER | sì |  |
| gate_version | INTEGER | sì |  |
| link_revision | INTEGER | sì |  |
| payload | TEXT | no |  |
| guard | TEXT | sì |  |
| notification_id | VARCHAR(36) | sì | notifications.id |
| dedup | VARCHAR(200) | sì |  |
| status | VARCHAR(16) | no |  |
| attempts | INTEGER | no |  |
| next_attempt | BIGINT | no |  |
| expires | BIGINT | no |  |

## telegram_state

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | INTEGER | no |  |
| generation | INTEGER | no |  |
| offset | BIGINT | no |  |
| username | VARCHAR(32) | no |  |
| verified_at | BIGINT | no |  |
| error | VARCHAR(40) | no |  |

## telegram_updates

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| generation | INTEGER | no |  |
| update_id | BIGINT | no |  |
| payload | TEXT | no |  |
| created | BIGINT | no |  |
| status | VARCHAR(16) | no |  |
| error | VARCHAR(40) | no |  |

## users

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| email | VARCHAR(254) | no |  |
| name | VARCHAR(100) | no |  |
| password_hash | VARCHAR(256) | no |  |
| status | VARCHAR(20) | no |  |
| admin | BOOLEAN | no |  |
| superadmin | BOOLEAN | no |  |
| admin_permissions | JSON | sì |  |
| requested_role | VARCHAR(16) | no |  |
| avatar | BLOB | sì |  |
| avatar_icon | VARCHAR(16) | no |  |
| avatar_version | INTEGER | no |  |
| theme | VARCHAR(5) | no |  |
| email_verified | BOOLEAN | no |  |
| auth_version | INTEGER | no |  |
| totp_secret | VARCHAR(512) | sì |  |
| totp_pending | VARCHAR(512) | sì |  |
| totp_last_counter | BIGINT | no |  |

## virtual_delegations

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(36) | no |  |
| group_id | VARCHAR(36) | no | groups.id |
| virtual_id | VARCHAR(36) | no | participants.id |
| delegate_id | VARCHAR(36) | no | participants.id |
| pay | BOOLEAN | no |  |
| attest | BOOLEAN | no |  |
| expires | BIGINT | no |  |
| revoked | BOOLEAN | no |  |
| granted_by | VARCHAR(36) | no | users.id |

## webauthn_challenges

| Colonna | Tipo | Nullable | Riferimenti |
|---|---|---|---|
| id | VARCHAR(64) | no |  |
| user_id | VARCHAR(36) | no | users.id |
| purpose | VARCHAR(10) | no |  |
| challenge | VARCHAR(128) | no |  |
| expires | BIGINT | no |  |
