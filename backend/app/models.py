import time
import uuid
from sqlalchemy import LargeBinary, Text, String, Integer, BigInteger, Boolean, ForeignKey, UniqueConstraint, CheckConstraint, JSON, ForeignKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def uid():
    return str(uuid.uuid4())


class Instance(Base):
    __tablename__ = 'instance'
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    gate_hash: Mapped[str] = mapped_column(String(256))
    gate_version: Mapped[int] = mapped_column(default=1)
    gate_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    guest_links_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    superadmin_id: Mapped[str | None] = mapped_column(ForeignKey('users.id',ondelete='RESTRICT',name='fk_instance_superadmin'))
    runtime_policy: Mapped[dict] = mapped_column(JSON,default=dict)
    backup_policy: Mapped[dict] = mapped_column(JSON,default=dict)
    telegram_config: Mapped[str | None] = mapped_column(String(4000))
    smtp_config: Mapped[str | None] = mapped_column(String(16000))
    registration: Mapped[str] = mapped_column(String(20), default='invite')
    __table_args__ = (CheckConstraint("registration in ('open','approval','invite','disabled')"),)


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(20), default='active')
    admin: Mapped[bool] = mapped_column(Boolean, default=False)
    superadmin: Mapped[bool] = mapped_column(Boolean,default=False)
    admin_permissions: Mapped[list | None] = mapped_column(JSON,nullable=True)
    requested_role: Mapped[str] = mapped_column(String(16),default='user')
    avatar: Mapped[bytes | None] = mapped_column(LargeBinary)
    avatar_icon: Mapped[str] = mapped_column(String(16),default='')
    avatar_version: Mapped[int] = mapped_column(default=1)
    theme: Mapped[str] = mapped_column(String(5), default='dark',server_default='dark')
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    auth_version: Mapped[int] = mapped_column(default=1)
    totp_secret: Mapped[str | None] = mapped_column(String(512))
    totp_pending: Mapped[str | None] = mapped_column(String(512))
    totp_last_counter: Mapped[int] = mapped_column(BigInteger, default=-1)
    __table_args__ = (CheckConstraint("not superadmin or (admin and status='active')",name='ck_users_superadmin_active'),CheckConstraint("status in ('active','pending','suspended')"),CheckConstraint("theme in ('light','dark')",name='ck_users_theme'))


class Session(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires: Mapped[int] = mapped_column(BigInteger)
    created: Mapped[int] = mapped_column(BigInteger, default=lambda: int(time.time()))
    verified: Mapped[int] = mapped_column(BigInteger, default=lambda: int(time.time()))
    gate_version: Mapped[int] = mapped_column()
    auth_version: Mapped[int] = mapped_column(default=1)


class GateGrant(Base):
    __tablename__ = 'gate_grants'
    credential_id: Mapped[str | None] = mapped_column(String(1400))
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires: Mapped[int] = mapped_column(BigInteger)
    version: Mapped[int] = mapped_column()


class RecoveryCode(Base):
    __tablename__ = 'recovery_codes'
    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))


class RateBucket(Base):
    __tablename__ = 'rate_buckets'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    hits: Mapped[int] = mapped_column(default=0)
    window: Mapped[int] = mapped_column(BigInteger)


class Audit(Base):
    __tablename__ = 'audit_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor: Mapped[str | None] = mapped_column(String(36))
    event: Mapped[str] = mapped_column(String(60))
    resource: Mapped[str | None] = mapped_column(String(36))
    at: Mapped[int] = mapped_column(BigInteger, default=lambda: int(time.time()))


class Invite(Base):
    __tablename__ = 'invitations'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(254))
    expires: Mapped[int] = mapped_column(BigInteger)
    used: Mapped[bool] = mapped_column(Boolean, default=False)

    id: Mapped[str] = mapped_column(String(36),default=uid,unique=True)
    created: Mapped[int] = mapped_column(BigInteger,default=lambda:int(time.time()))
    revoked: Mapped[bool] = mapped_column(Boolean,default=False)
    version: Mapped[int] = mapped_column(default=1)
    issuer_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    used_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'))

    requested_role: Mapped[str] = mapped_column(String(16),default='user')
    issuer_auth_version: Mapped[int | None] = mapped_column(Integer,nullable=True)


class Group(Base):
    __tablename__ = 'groups'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3), default='EUR')
    state: Mapped[str] = mapped_column(String(16), default='active')
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    description: Mapped[str] = mapped_column(String(2000), default='')
    icon: Mapped[str] = mapped_column(String(16), default='✳')
    image: Mapped[bytes | None] = mapped_column(LargeBinary)
    metadata_version: Mapped[int] = mapped_column(default=1)
    smart_balances: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (CheckConstraint("state in ('active','frozen','archived')"),)


class Participant(Base):
    __tablename__ = 'participants'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    role: Mapped[str] = mapped_column(String(16), default='member')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    merged_into: Mapped[str | None] = mapped_column(String(36))
    __table_args__ = (UniqueConstraint('id', 'group_id'), UniqueConstraint('group_id', 'user_id'), CheckConstraint("role in ('owner','admin','member','viewer')"))


class Expense(Base):
    __tablename__ = 'expenses'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id'), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(4000), default='')
    date: Mapped[str] = mapped_column(String(10))
    category: Mapped[str] = mapped_column(String(60), default='Altro')
    total: Mapped[int] = mapped_column(BigInteger)
    version: Mapped[int] = mapped_column(default=1)
    # Null = whole group; otherwise exact participant audience.
    audience: Mapped[list | None] = mapped_column(JSON)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    items: Mapped[list] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint('id', 'group_id'), CheckConstraint('total > 0'), CheckConstraint('version > 0'))


class Entry(Base):
    __tablename__ = 'ledger_entries'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    group_id: Mapped[str] = mapped_column(String(36))
    expense_id: Mapped[str] = mapped_column(String(36))
    participant_id: Mapped[str] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(default=1)
    paid: Mapped[int] = mapped_column(BigInteger)
    owed: Mapped[int] = mapped_column(BigInteger)
    __table_args__ = (
        ForeignKeyConstraint(['expense_id', 'group_id'], ['expenses.id', 'expenses.group_id']),
        ForeignKeyConstraint(['participant_id', 'group_id'], ['participants.id', 'participants.group_id']),
        UniqueConstraint('expense_id', 'revision', 'participant_id', name='uq_ledger_expense_revision_person'), CheckConstraint('paid >= 0 and owed >= 0'),
    )


class Idempotency(Base):
    __tablename__ = 'idempotency_records'
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)


class WebChallenge(Base):
    __tablename__ = 'webauthn_challenges'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    purpose: Mapped[str] = mapped_column(String(10))
    challenge: Mapped[str] = mapped_column(String(128))
    expires: Mapped[int] = mapped_column(BigInteger)


class Passkey(Base):
    __tablename__ = 'passkeys'
    credential_id: Mapped[str] = mapped_column(String(1400), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    public_key: Mapped[str] = mapped_column(String(3000))
    sign_count: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(100), default='Passkey')


class Settlement(Base):
    __tablename__ = 'settlements'
    kind: Mapped[str] = mapped_column(String(20), default='reimbursement')
    note: Mapped[str] = mapped_column(String(2000), default='')
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id'), index=True)
    sender: Mapped[str] = mapped_column(String(36))
    recipient: Mapped[str] = mapped_column(String(36))
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    amount: Mapped[int] = mapped_column(BigInteger)
    audience: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    created: Mapped[int] = mapped_column(BigInteger, default=lambda: int(time.time()))
    __table_args__ = (ForeignKeyConstraint(['sender','group_id'], ['participants.id','participants.group_id']), ForeignKeyConstraint(['recipient','group_id'], ['participants.id','participants.group_id']), CheckConstraint('amount > 0'), CheckConstraint('sender != recipient'), CheckConstraint("status in ('pending','confirmed','disputed','cancelled')"))


class SettlementEvent(Base):
    __tablename__ = 'settlement_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    settlement_id: Mapped[str] = mapped_column(ForeignKey('settlements.id'))
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    status: Mapped[str] = mapped_column(String(20))
    at: Mapped[int] = mapped_column(BigInteger, default=lambda: int(time.time()))
    reason: Mapped[str] = mapped_column(String(2000), default='')
    ordinal: Mapped[int] = mapped_column(BigInteger, default=time.time_ns)


class GuestLink(Base):
    __tablename__ = 'guest_links'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id'))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(256))
    expires: Mapped[int] = mapped_column(BigInteger)
    revoked: Mapped[bool] = mapped_column(default=False)
    uses: Mapped[int] = mapped_column(default=0)
    max_uses: Mapped[int | None] = mapped_column()
    show_names: Mapped[bool] = mapped_column(default=True)
    show_details: Mapped[bool] = mapped_column(default=True)
    show_attachments: Mapped[bool] = mapped_column(default=False)
    show_exports: Mapped[bool] = mapped_column(default=False)


class GroupInvite(Base):
    __tablename__ = 'group_invitations'
    id: Mapped[str] = mapped_column(String(36),default=uid,unique=True)
    issuer_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    accepted_user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id'))
    role: Mapped[str] = mapped_column(String(16))
    email: Mapped[str | None] = mapped_column(String(254))
    expires: Mapped[int] = mapped_column(BigInteger)
    used: Mapped[bool] = mapped_column(default=False)
    participant_id: Mapped[str | None] = mapped_column(String(36))
    __table_args__ = (ForeignKeyConstraint(['participant_id', 'group_id'], ['participants.id', 'participants.group_id'], name='fk_group_invitation_participant'),)


class ExpenseRevision(Base):
    __tablename__ = 'expense_versions'
    expense_id: Mapped[str] = mapped_column(ForeignKey('expenses.id'), primary_key=True)
    version: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    snapshot: Mapped[dict] = mapped_column(JSON)
    created: Mapped[int] = mapped_column(BigInteger, default=lambda: int(time.time()))


class ParticipantClaim(Base):
    __tablename__ = 'participant_claims'
    issuer_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey('participants.id'))
    email: Mapped[str] = mapped_column(String(254))
    expires: Mapped[int] = mapped_column(BigInteger)
    used: Mapped[bool] = mapped_column(default=False)


class Category(Base):
    __tablename__ = 'categories'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(60))
    name_key: Mapped[str] = mapped_column(String(180))
    __table_args__ = (UniqueConstraint('group_id', 'name_key', name='uq_category_group_name'),)


class CurrencyChange(Base):
    __tablename__ = 'currency_changes'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id'), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    snapshot: Mapped[dict] = mapped_column(JSON)
    created: Mapped[int] = mapped_column(BigInteger, default=lambda: int(time.time()))


class Attachment(Base):
    __tablename__ = 'attachments'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id'), index=True)
    expense_id: Mapped[str | None] = mapped_column(String(36), index=True)
    settlement_id: Mapped[str | None] = mapped_column(ForeignKey('settlements.id'), index=True)
    expense_revision: Mapped[int | None] = mapped_column()
    uploader_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    storage_key: Mapped[str] = mapped_column(String(40), unique=True)
    filename: Mapped[str] = mapped_column(String(180))
    media_type: Mapped[str] = mapped_column(String(60))
    size: Mapped[int] = mapped_column(BigInteger)
    preview_size: Mapped[int] = mapped_column(BigInteger, default=0)
    sha256: Mapped[str] = mapped_column(String(64))
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created: Mapped[int] = mapped_column(BigInteger, default=lambda: int(time.time()))
    __table_args__ = (ForeignKeyConstraint(['expense_id','expense_revision'],['expense_versions.expense_id','expense_versions.version']),CheckConstraint('(expense_id IS NOT NULL AND settlement_id IS NULL AND expense_revision IS NOT NULL) OR (expense_id IS NULL AND settlement_id IS NOT NULL AND expense_revision IS NULL)',name='ck_attachment_parent'),CheckConstraint('size > 0 AND preview_size >= 0',name='ck_attachment_size'))


class ExpenseDispute(Base):
    __tablename__ = 'expense_disputes'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    expense_id: Mapped[str] = mapped_column(ForeignKey('expenses.id'), index=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey('participants.id'))
    version: Mapped[int] = mapped_column()
    reason: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(16), default='open')
    resolution: Mapped[str] = mapped_column(String(2000), default='')
    resolver_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    created: Mapped[int] = mapped_column(BigInteger, default=lambda: int(time.time()))
    resolved_at: Mapped[int | None] = mapped_column(BigInteger)
    __table_args__ = (CheckConstraint("status in ('open','resolved','rejected','withdrawn')",name='ck_expense_dispute_status'),)


class GroupOperation(Base):
    __tablename__ = 'group_operations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id'), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    kind: Mapped[str] = mapped_column(String(30))
    snapshot: Mapped[dict] = mapped_column(JSON)
    created: Mapped[int] = mapped_column(BigInteger, default=lambda: int(time.time()))


class VirtualDelegation(Base):
    __tablename__ = 'virtual_delegations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id'), index=True)
    virtual_id: Mapped[str] = mapped_column(ForeignKey('participants.id'))
    delegate_id: Mapped[str] = mapped_column(ForeignKey('participants.id'))
    pay: Mapped[bool] = mapped_column(Boolean, default=False)
    attest: Mapped[bool] = mapped_column(Boolean, default=False)
    expires: Mapped[int] = mapped_column(BigInteger)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    granted_by: Mapped[str] = mapped_column(ForeignKey('users.id'))


class AccountToken(Base):
    __tablename__ = 'account_tokens'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    purpose: Mapped[str] = mapped_column(String(16))
    email: Mapped[str] = mapped_column(String(254))
    auth_version: Mapped[int] = mapped_column()
    expires: Mapped[int] = mapped_column(BigInteger)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class MailMessage(Base):
    __tablename__ = 'mail_messages'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    payload: Mapped[str] = mapped_column(String(24000))
    token_hash: Mapped[str | None] = mapped_column(String(64))
    expires: Mapped[int] = mapped_column(BigInteger)
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(16), default='pending')


class PaymentMethod(Base):
    __tablename__ = 'payment_methods'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    payload: Mapped[str] = mapped_column(String(24000))
    image: Mapped[bytes | None] = mapped_column(LargeBinary)
    shared: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(default=1)


class ExpensePlan(Base):
    __tablename__ = 'expense_plans'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id'), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    participant_id: Mapped[str] = mapped_column(ForeignKey('participants.id'))
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))
    draft: Mapped[dict] = mapped_column(JSON)
    audience: Mapped[list | None] = mapped_column(JSON)
    currency: Mapped[str] = mapped_column(String(3))
    frequency: Mapped[str] = mapped_column(String(12), default='monthly')
    interval: Mapped[int] = mapped_column(default=1)
    start: Mapped[str] = mapped_column(String(10))
    until: Mapped[str | None] = mapped_column(String(10))
    cursor: Mapped[int] = mapped_column(default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_fx: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(default=1)
    error: Mapped[str] = mapped_column(String(40), default='')


class ExpenseJob(Base):
    __tablename__ = 'expense_jobs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    plan_id: Mapped[str] = mapped_column(ForeignKey('expense_plans.id'), index=True)
    date: Mapped[str] = mapped_column(String(10))
    audience: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default='pending')
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt: Mapped[int] = mapped_column(BigInteger, default=0)
    error: Mapped[str] = mapped_column(String(40), default='')
    expense_id: Mapped[str | None] = mapped_column(ForeignKey('expenses.id'))
    __table_args__ = (UniqueConstraint('plan_id','date',name='uq_expense_job_date'),)


class Budget(Base):
    __tablename__='budgets'
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id'),index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    participant_id: Mapped[str] = mapped_column(ForeignKey('participants.id'))
    name: Mapped[str] = mapped_column(String(100))
    scope: Mapped[str] = mapped_column(String(12))
    currency: Mapped[str] = mapped_column(String(3))
    amount: Mapped[int] = mapped_column(BigInteger)
    threshold: Mapped[int] = mapped_column(default=80)
    start: Mapped[str] = mapped_column(String(10))
    end: Mapped[str] = mapped_column(String(10))
    category: Mapped[str] = mapped_column(String(60),default='')
    tag: Mapped[str] = mapped_column(String(40),default='')
    version: Mapped[int] = mapped_column(default=1)


class FinalReport(Base):
    __tablename__='final_reports'
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id'),index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    participant_id: Mapped[str] = mapped_column(ForeignKey('participants.id'))
    snapshot: Mapped[dict] = mapped_column(JSON)
    created: Mapped[int] = mapped_column(BigInteger,default=lambda:int(time.time()))


class ImportBatch(Base):
    __tablename__='import_batches'
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id'),index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    participant_id: Mapped[str] = mapped_column(ForeignKey('participants.id'))
    currency: Mapped[str] = mapped_column(String(3))
    payload: Mapped[str] = mapped_column(String)
    expires: Mapped[int] = mapped_column(BigInteger)
    applied: Mapped[bool] = mapped_column(default=False)
    response: Mapped[dict | None] = mapped_column(JSON)


class ImportedExpense(Base):
    __tablename__='imported_expenses'
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id'))
    participant_id: Mapped[str] = mapped_column(ForeignKey('participants.id'))
    origin: Mapped[str] = mapped_column(String(64))
    expense_id: Mapped[str] = mapped_column(ForeignKey('expenses.id'))
    __table_args__=(UniqueConstraint('group_id','participant_id','origin',name='uq_import_origin'),)


class RevealJob(Base):
    __tablename__='reveal_jobs'
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id'),index=True)
    expense_id: Mapped[str] = mapped_column(ForeignKey('expenses.id'))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    participant_id: Mapped[str] = mapped_column(ForeignKey('participants.id'))
    audience: Mapped[list] = mapped_column(JSON)
    expense_version: Mapped[int] = mapped_column()
    auth_version: Mapped[int] = mapped_column(default=1)
    run_at: Mapped[int] = mapped_column(BigInteger,index=True)
    status: Mapped[str] = mapped_column(String(20),default='pending')
    error: Mapped[str] = mapped_column(String(40),default='')


class NotificationPreference(Base):
    __tablename__ = 'notification_preferences'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),primary_key=True)
    scope: Mapped[str] = mapped_column(String(36),primary_key=True,default='')
    config: Mapped[dict] = mapped_column(JSON,default=dict)
    started_at: Mapped[int] = mapped_column(BigInteger,default=lambda:int(time.time()))
    # A group ID or empty for account defaults. No FK: account defaults share the table.


class Notification(Base):
    __tablename__ = 'notifications'
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id'),index=True)
    event_key: Mapped[str] = mapped_column(String(180))
    kind: Mapped[str] = mapped_column(String(20))
    resource: Mapped[str] = mapped_column(String(36))
    audience: Mapped[list | None] = mapped_column(JSON)
    participant_id: Mapped[str] = mapped_column(ForeignKey('participants.id'))
    created: Mapped[int] = mapped_column(BigInteger,default=lambda:int(time.time()))
    read_at: Mapped[int | None] = mapped_column(BigInteger)
    email_status: Mapped[str] = mapped_column(String(20),default='none')
    folder: Mapped[str] = mapped_column(String(16),default='inbox')
    __table_args__ = (UniqueConstraint('user_id','event_key',name='uq_notification_event'),CheckConstraint("folder in ('inbox','archived','trash')",name='ck_notification_folder'))


class InstallationPasskey(Base):
    __tablename__='installation_passkeys'
    credential_id: Mapped[str] = mapped_column(String(1400),primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'),index=True)
    public_key: Mapped[str] = mapped_column(String(3000))
    sign_count: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(100),default='Accesso installazione')
    gate_version: Mapped[int] = mapped_column()
    auth_version: Mapped[int] = mapped_column()


class InstallationChallenge(Base):
    __tablename__='installation_challenges'
    id: Mapped[str] = mapped_column(String(64),primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    purpose: Mapped[str] = mapped_column(String(10))
    challenge: Mapped[str] = mapped_column(String(128))
    gate_version: Mapped[int] = mapped_column()
    auth_version: Mapped[int | None] = mapped_column()
    expires: Mapped[int] = mapped_column(BigInteger)


class MaintenanceJob(Base):
    __tablename__='maintenance_jobs'
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=uid)
    slot: Mapped[str] = mapped_column(String(160),unique=True)
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20),default='pending')
    requested_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    created: Mapped[int] = mapped_column(BigInteger,default=lambda:int(time.time()))
    started: Mapped[int | None] = mapped_column(BigInteger)
    finished: Mapped[int | None] = mapped_column(BigInteger)
    error: Mapped[str] = mapped_column(String(40),default='')
    result: Mapped[dict] = mapped_column(JSON,default=dict)

class ServiceHeartbeat(Base):
    __tablename__='service_heartbeats'
    service: Mapped[str] = mapped_column(String(30),primary_key=True)
    at: Mapped[int] = mapped_column(BigInteger)


class TelegramState(Base):
    __tablename__='telegram_state'
    id: Mapped[int] = mapped_column(primary_key=True,default=1)
    generation: Mapped[int] = mapped_column(default=0)
    offset: Mapped[int] = mapped_column(BigInteger,default=0)
    username: Mapped[str] = mapped_column(String(32),default='')
    verified_at: Mapped[int] = mapped_column(BigInteger,default=0)
    error: Mapped[str] = mapped_column(String(40),default='')

class TelegramLink(Base):
    __tablename__='telegram_links'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger,unique=True)
    auth_version: Mapped[int] = mapped_column()
    gate_version: Mapped[int] = mapped_column()
    generation: Mapped[int] = mapped_column()
    allow_private: Mapped[bool] = mapped_column(Boolean,default=False)
    notifications: Mapped[bool] = mapped_column(Boolean,default=False)
    draft: Mapped[str | None] = mapped_column(Text)
    draft_expires: Mapped[int] = mapped_column(BigInteger,default=0)
    revision: Mapped[int] = mapped_column(default=1)
    action_version: Mapped[int] = mapped_column(default=1)
    created: Mapped[int] = mapped_column(BigInteger,default=lambda:int(time.time()))

class TelegramGrant(Base):
    __tablename__='telegram_grants'
    token_hash: Mapped[str] = mapped_column(String(64),primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger)
    auth_version: Mapped[int] = mapped_column()
    gate_version: Mapped[int] = mapped_column()
    generation: Mapped[int] = mapped_column()
    allow_private: Mapped[bool] = mapped_column(Boolean,default=False)
    notifications: Mapped[bool] = mapped_column(Boolean,default=False)
    expires: Mapped[int] = mapped_column(BigInteger)

class TelegramUpdate(Base):
    __tablename__='telegram_updates'
    generation: Mapped[int] = mapped_column(primary_key=True)
    update_id: Mapped[int] = mapped_column(BigInteger,primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    created: Mapped[int] = mapped_column(BigInteger,default=lambda:int(time.time()))
    status: Mapped[str] = mapped_column(String(16),default='pending')
    error: Mapped[str] = mapped_column(String(40),default='')

class TelegramAction(Base):
    __tablename__='telegram_actions'
    token_hash: Mapped[str] = mapped_column(String(64),primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger)
    revision: Mapped[int] = mapped_column()
    payload: Mapped[str] = mapped_column(Text)
    expires: Mapped[int] = mapped_column(BigInteger)

class TelegramOutbox(Base):
    __tablename__='telegram_outbox'
    method: Mapped[str] = mapped_column(String(24),default='sendMessage')
    sequence: Mapped[int] = mapped_column(BigInteger,default=time.time_ns)
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=uid)
    generation: Mapped[int] = mapped_column()
    telegram_id: Mapped[int] = mapped_column(BigInteger,index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'))
    auth_version: Mapped[int | None] = mapped_column()
    gate_version: Mapped[int | None] = mapped_column()
    link_revision: Mapped[int | None] = mapped_column()
    payload: Mapped[str] = mapped_column(Text)
    guard: Mapped[str | None] = mapped_column(Text)
    notification_id: Mapped[str | None] = mapped_column(ForeignKey('notifications.id',ondelete='SET NULL'))
    dedup: Mapped[str | None] = mapped_column(String(200),unique=True)
    status: Mapped[str] = mapped_column(String(16),default='pending')
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt: Mapped[int] = mapped_column(BigInteger,default=0)
    expires: Mapped[int] = mapped_column(BigInteger)


class GroupJoinCode(Base):
    __tablename__ = 'group_join_codes'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id', ondelete='CASCADE'), index=True)
    role: Mapped[str] = mapped_column(String(16))
    secret: Mapped[bytes] = mapped_column(LargeBinary)
    __table_args__ = (UniqueConstraint('group_id', 'role'), CheckConstraint("role in ('admin','member','viewer')"))
