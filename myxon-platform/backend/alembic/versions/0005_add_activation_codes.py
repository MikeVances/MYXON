"""Add activation_codes table

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-17

Добавляет таблицу activation_codes — одноразовые коды для само-регистрации устройств.
Дилер создаёт код заранее, устройство при первом запуске активируется по нему.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activation_codes",
        # Primary key
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),

        # The one-time code in XXXX-XXXX-XXXX-XXXX format
        sa.Column("code", sa.String(36), nullable=False, unique=True),

        # Dealer tenant that owns this code
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),

        # User who generated the code
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),

        # Optional label for the intended device (e.g. "Farm Noord unit #3")
        sa.Column("device_name", sa.String(255), nullable=True),

        # Expiry — set by dealer, default 7 days from creation
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),

        # Filled after device self-registers (NULL = unused)
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("devices.id"),
            nullable=True,
        ),

        # When code was consumed (NULL = still valid)
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),

        # Audit timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Index on tenant_id for fast dealer dashboard queries
    op.create_index("ix_activation_codes_tenant_id", "activation_codes", ["tenant_id"])
    # Index on code for fast lookup during agent activation
    op.create_index("ix_activation_codes_code", "activation_codes", ["code"])


def downgrade() -> None:
    op.drop_index("ix_activation_codes_code", table_name="activation_codes")
    op.drop_index("ix_activation_codes_tenant_id", table_name="activation_codes")
    op.drop_table("activation_codes")
