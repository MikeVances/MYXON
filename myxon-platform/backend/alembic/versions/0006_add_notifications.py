"""Add notification_contacts, notification_rules tables and alarms.sms_sent_at

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-19

Добавляет систему маршрутизации уведомлений:
  - notification_contacts — справочник контактов (телефон + email)
  - notification_rules    — правила: кто получает уведомления о каких устройствах
  - alarms.sms_sent_at    — отметка что SMS уже включён в heartbeat response
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── notification_contacts ─────────────────────────────────────────────────
    op.create_table(
        "notification_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("channels", postgresql.JSON(), nullable=False, server_default='["sms","email"]'),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_contacts_tenant_id", "notification_contacts", ["tenant_id"])

    # ── notification_rules ────────────────────────────────────────────────────
    op.create_table(
        "notification_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notification_contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope_type", sa.String(20), nullable=False),   # tenant | site | device
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("min_severity", sa.String(20), nullable=False, server_default="alarm"),
        sa.Column("categories", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_rules_tenant_id", "notification_rules", ["tenant_id"])
    op.create_index("ix_notification_rules_contact_id", "notification_rules", ["contact_id"])
    op.create_index("ix_notification_rules_scope_id",   "notification_rules", ["scope_id"])

    # ── alarms: add sms_sent_at ───────────────────────────────────────────────
    op.add_column(
        "alarms",
        sa.Column("sms_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("alarms", "sms_sent_at")
    op.drop_table("notification_rules")
    op.drop_table("notification_contacts")
