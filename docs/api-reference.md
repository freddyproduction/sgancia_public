# Catalogo API generato

Versione 0.2.0-dev. Fonte autorevole: `/api/openapi.json`; interfaccia `/api/docs`.

| Metodo | Percorso | Operazione |
|---|---|---|
| GET | `/api/v1/account/payment-methods` | Methods |
| POST | `/api/v1/account/payment-methods` | Create |
| PUT | `/api/v1/account/payment-methods/{mid}` | Edit |
| DELETE | `/api/v1/account/payment-methods/{mid}` | Remove |
| GET | `/api/v1/account/payment-methods/{mid}/image` | Own Image |
| GET | `/api/v1/admin/access-policy` | Access Policy |
| PUT | `/api/v1/admin/access-policy` | Change Gate |
| PUT | `/api/v1/admin/gate` | Rotate Gate |
| GET | `/api/v1/admin/installation/guest-links` | Admin Policy |
| PUT | `/api/v1/admin/installation/guest-links` | Change Policy |
| GET | `/api/v1/admin/installation/smtp` | Smtp Settings |
| PUT | `/api/v1/admin/installation/smtp` | Save Smtp |
| POST | `/api/v1/admin/installation/smtp/test` | Test Smtp |
| POST | `/api/v1/admin/invitations` | Invite |
| GET | `/api/v1/admin/operations/audit` | Events |
| POST | `/api/v1/admin/operations/backup` | Queue Backup |
| GET | `/api/v1/admin/operations/backups` | Backups |
| PUT | `/api/v1/admin/operations/backups` | Save Backups |
| GET | `/api/v1/admin/operations/policy` | Get Policy |
| PUT | `/api/v1/admin/operations/policy` | Save Policy |
| POST | `/api/v1/admin/operations/revoke-sessions` | Revoke Sessions |
| GET | `/api/v1/admin/operations/status` | Status |
| GET | `/api/v1/admin/operations/telegram` | Telegram |
| PUT | `/api/v1/admin/operations/telegram` | Telegram Save |
| PUT | `/api/v1/admin/registration` | Policy |
| GET | `/api/v1/admin/users` | Users |
| PUT | `/api/v1/admin/users/{user_id}` | Edit User |
| PUT | `/api/v1/admin/users/{user_id}/global-role` | Change Role |
| POST | `/api/v1/admin/users/{user_id}/reset-factors` | Reset Factors |
| PUT | `/api/v1/admin/users/{user_id}/status` | Status |
| PUT | `/api/v1/auth/email` | Email Change |
| POST | `/api/v1/auth/email/send-verification` | Resend |
| GET | `/api/v1/auth/email/status` | Email Status |
| POST | `/api/v1/auth/email/verify` | Confirm Email |
| GET | `/api/v1/auth/entry-policy` | Entry Policy |
| POST | `/api/v1/auth/gate` | Unlock |
| GET | `/api/v1/auth/installation-passkeys` | Keys |
| POST | `/api/v1/auth/installation-passkeys/register/options` | Registration Options |
| POST | `/api/v1/auth/installation-passkeys/register/verify` | Registration Verify |
| POST | `/api/v1/auth/installation-passkeys/unlock/options` | Unlock Options |
| POST | `/api/v1/auth/installation-passkeys/unlock/verify` | Unlock Verify |
| DELETE | `/api/v1/auth/installation-passkeys/{credential_id}` | Remove |
| POST | `/api/v1/auth/login` | Login |
| POST | `/api/v1/auth/logout` | Logout |
| GET | `/api/v1/auth/me` | Me |
| POST | `/api/v1/auth/mfa/disable` | Disable Mfa |
| POST | `/api/v1/auth/mfa/recovery-codes` | Renew Codes |
| POST | `/api/v1/auth/mfa/rotate` | Rotate Mfa |
| POST | `/api/v1/auth/mfa/rotate/confirm` | Confirm Rotation |
| GET | `/api/v1/auth/passkeys` | List Keys |
| POST | `/api/v1/auth/passkeys/login/options` | Login Options |
| POST | `/api/v1/auth/passkeys/login/verify` | Login Verify |
| POST | `/api/v1/auth/passkeys/register/options` | Registration Options |
| POST | `/api/v1/auth/passkeys/register/verify` | Registration Verify |
| DELETE | `/api/v1/auth/passkeys/{credential_id}` | Delete Key |
| PUT | `/api/v1/auth/password` | Change Password |
| POST | `/api/v1/auth/password/forgot` | Forgot |
| POST | `/api/v1/auth/password/reset` | Reset Password |
| GET | `/api/v1/auth/policy` | Policy |
| PUT | `/api/v1/auth/preferences` | Preferences |
| POST | `/api/v1/auth/reauth` | Reauth |
| POST | `/api/v1/auth/register` | Register |
| GET | `/api/v1/auth/sessions` | Sessions |
| DELETE | `/api/v1/auth/sessions/{session_id}` | Revoke |
| POST | `/api/v1/auth/totp/confirm` | Confirm Totp |
| POST | `/api/v1/auth/totp/setup` | Setup Totp |
| POST | `/api/v1/calculator` | Calculator |
| GET | `/api/v1/currencies` | Currencies |
| POST | `/api/v1/currency-conversion` | Convert Amount |
| GET | `/api/v1/exchange-rate` | Exchange Rate |
| POST | `/api/v1/group-access/accept` | Accept |
| POST | `/api/v1/group-access/preview` | Preview |
| GET | `/api/v1/group-trash` | Group Trash |
| GET | `/api/v1/groups` | Groups |
| POST | `/api/v1/groups` | Create Group |
| DELETE | `/api/v1/groups/{gid}` | Remove Group |
| GET | `/api/v1/groups/{gid}/access-invitations` | List Invitations |
| DELETE | `/api/v1/groups/{gid}/access-invitations/{iid}` | Revoke Invitation |
| GET | `/api/v1/groups/{gid}/attachment-limits` | Limits |
| DELETE | `/api/v1/groups/{gid}/attachments/{aid}` | Remove |
| GET | `/api/v1/groups/{gid}/attachments/{aid}/content` | Download |
| GET | `/api/v1/groups/{gid}/attachments/{aid}/preview` | Preview |
| POST | `/api/v1/groups/{gid}/attachments/{aid}/restore` | Restore |
| GET | `/api/v1/groups/{gid}/budgets` | Budgets |
| POST | `/api/v1/groups/{gid}/budgets` | Add Budget |
| PUT | `/api/v1/groups/{gid}/budgets/{bid}` | Edit Budget |
| DELETE | `/api/v1/groups/{gid}/budgets/{bid}` | Delete Budget |
| POST | `/api/v1/groups/{gid}/close` | Close |
| GET | `/api/v1/groups/{gid}/closing` | Closing |
| GET | `/api/v1/groups/{gid}/delegations` | Delegations |
| POST | `/api/v1/groups/{gid}/delegations` | Grant |
| DELETE | `/api/v1/groups/{gid}/delegations/{did}` | Revoke Delegation |
| POST | `/api/v1/groups/{gid}/expenses/{eid}/disputes` | Dispute |
| PUT | `/api/v1/groups/{gid}/expenses/{eid}/disputes/{did}` | Resolve |
| GET | `/api/v1/groups/{gid}/expenses/{eid}/duplicate` | Duplicate |
| GET | `/api/v1/groups/{gid}/expenses/{eid}/history` | Expense History |
| POST | `/api/v1/groups/{gid}/expenses/{eid}/reveal-confirm` | Confirm Reveal |
| GET | `/api/v1/groups/{gid}/expenses/{eid}/reveal-preview` | Preview |
| POST | `/api/v1/groups/{gid}/expenses/{eid}/reveal-schedule` | Schedule |
| DELETE | `/api/v1/groups/{gid}/expenses/{eid}/reveal-schedule/{jid}` | Cancel |
| GET | `/api/v1/groups/{gid}/export` | Export Group |
| POST | `/api/v1/groups/{gid}/imports/preview` | Preview Import |
| POST | `/api/v1/groups/{gid}/imports/{batch_id}/apply` | Apply Import |
| POST | `/api/v1/groups/{gid}/merge` | Merge |
| POST | `/api/v1/groups/{gid}/merge/preview` | Merge Preview |
| GET | `/api/v1/groups/{gid}/operations` | Operations |
| POST | `/api/v1/groups/{gid}/operations/{oid}/undo-merge` | Undo Merge |
| POST | `/api/v1/groups/{gid}/ownership` | Offer Owner |
| POST | `/api/v1/groups/{gid}/ownership/{oid}/accept` | Accept Owner |
| POST | `/api/v1/groups/{gid}/participants/{pid}/depart` | Depart |
| GET | `/api/v1/groups/{gid}/participants/{pid}/departure-preview` | Preview Departure |
| GET | `/api/v1/groups/{gid}/participants/{pid}/payment-methods` | Recipient Methods |
| GET | `/api/v1/groups/{gid}/participants/{pid}/payment-methods/{mid}/image` | Recipient Image |
| POST | `/api/v1/groups/{gid}/participants/{pid}/reactivate` | Reactivate |
| GET | `/api/v1/groups/{gid}/plans` | Plans |
| POST | `/api/v1/groups/{gid}/plans` | Create Plan |
| PUT | `/api/v1/groups/{gid}/plans/{pid}` | Update Plan |
| DELETE | `/api/v1/groups/{gid}/plans/{pid}` | Delete Plan |
| PUT | `/api/v1/groups/{gid}/plans/{pid}/state` | Switch |
| POST | `/api/v1/groups/{gid}/reports` | Save Report |
| GET | `/api/v1/groups/{gid}/reports` | Reports |
| POST | `/api/v1/groups/{gid}/restore` | Restore Group |
| GET | `/api/v1/groups/{gid}/search` | Search |
| GET | `/api/v1/groups/{gid}/settlements/{sid}/history` | Settlement History |
| POST | `/api/v1/groups/{gid}/simulate` | Simulate |
| GET | `/api/v1/groups/{gid}/tags` | Tags |
| GET | `/api/v1/groups/{gid}/{kind}/{target_id}/attachments` | List Attachments |
| POST | `/api/v1/groups/{gid}/{kind}/{target_id}/attachments` | Upload |
| GET | `/api/v1/groups/{group_id}` | Group Detail |
| PUT | `/api/v1/groups/{group_id}` | Update Group |
| GET | `/api/v1/groups/{group_id}/balances` | Balances |
| GET | `/api/v1/groups/{group_id}/categories` | Categories |
| POST | `/api/v1/groups/{group_id}/categories` | Create Category |
| PUT | `/api/v1/groups/{group_id}/currency` | Change Currency |
| POST | `/api/v1/groups/{group_id}/expenses` | Create Expense |
| GET | `/api/v1/groups/{group_id}/expenses` | List Expenses |
| POST | `/api/v1/groups/{group_id}/expenses/preview` | Preview |
| PUT | `/api/v1/groups/{group_id}/expenses/{expense_id}` | Edit |
| GET | `/api/v1/groups/{group_id}/expenses/{expense_id}` | Expense Draft |
| DELETE | `/api/v1/groups/{group_id}/expenses/{expense_id}` | Remove Expense |
| POST | `/api/v1/groups/{group_id}/expenses/{expense_id}/preview` | Edit Preview |
| POST | `/api/v1/groups/{group_id}/expenses/{expense_id}/restore` | Restore Expense |
| POST | `/api/v1/groups/{group_id}/expenses/{expense_id}/reveal` | Reveal |
| GET | `/api/v1/groups/{group_id}/expenses/{expense_id}/versions` | History |
| GET | `/api/v1/groups/{group_id}/finance` | Finance |
| POST | `/api/v1/groups/{group_id}/guest-links` | Create Guest |
| GET | `/api/v1/groups/{group_id}/guest-links` | List Links |
| DELETE | `/api/v1/groups/{group_id}/guest-links/{link_id}` | Revoke |
| GET | `/api/v1/groups/{group_id}/image` | Group Image |
| POST | `/api/v1/groups/{group_id}/invitations` | Invite |
| POST | `/api/v1/groups/{group_id}/participants` | Add Participant |
| PUT | `/api/v1/groups/{group_id}/participants/{participant_id}` | Edit Person |
| POST | `/api/v1/groups/{group_id}/participants/{participant_id}/claim` | Issue Claim |
| GET | `/api/v1/groups/{group_id}/settlements` | Payments |
| POST | `/api/v1/groups/{group_id}/settlements` | Create |
| POST | `/api/v1/groups/{group_id}/settlements/settle-suggestion` | Settle Suggestion |
| POST | `/api/v1/groups/{group_id}/settlements/settle-transfer` | Settle Transfer |
| PUT | `/api/v1/groups/{group_id}/settlements/{settlement_id}` | Transition |
| POST | `/api/v1/groups/{group_id}/settlements/{settlement_id}/undo` | Undo Receipt |
| PUT | `/api/v1/groups/{group_id}/smart-balances` | Update Smart |
| PUT | `/api/v1/groups/{group_id}/state` | State |
| GET | `/api/v1/groups/{group_id}/trash` | Trash |
| GET | `/api/v1/guest-policy` | Read Policy |
| POST | `/api/v1/guest/attachments/{aid}` | Guest Attachment |
| POST | `/api/v1/guest/export` | Export Guest |
| POST | `/api/v1/guest/view` | Guest View |
| GET | `/api/v1/imports/csv-template` | Csv Template |
| POST | `/api/v1/invitations/accept` | Accept |
| GET | `/api/v1/notifications` | Inbox |
| GET | `/api/v1/notifications/options` | Options |
| GET | `/api/v1/notifications/preferences` | Get Preferences |
| PUT | `/api/v1/notifications/preferences` | Set Preferences |
| DELETE | `/api/v1/notifications/preferences` | Reset Preferences |
| POST | `/api/v1/notifications/read-all` | Mark All |
| POST | `/api/v1/notifications/{nid}/read` | Mark Read |
| GET | `/api/v1/overview` | Overview |
| POST | `/api/v1/overview/settle` | Settle Overview |
| POST | `/api/v1/participants/claim` | Claim |
| GET | `/api/v1/project` | Project |
| GET | `/api/v1/statistics` | Personal Stats |
| GET | `/api/v1/telegram/account` | Account |
| DELETE | `/api/v1/telegram/account` | Unlink |
| POST | `/api/v1/telegram/link` | Issue Link |
| POST | `/api/v1/telegram/webhook` | Webhook |
