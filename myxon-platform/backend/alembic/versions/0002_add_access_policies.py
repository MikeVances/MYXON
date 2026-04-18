"""Add access_policies table and access_policy_id to user_site_access

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-05

Changes:
- New table: access_policies
  Granular per-device permission set.
  Fields: name, description, tenant_id, allow_hmi, allow_vnc, allow_http,
          allow_alarms_view, allow_alarms_acknowledge, alarm_severity_filter,
          allow_audit_view, is_default

- user_site_access: add access_policy_id (FK → access_policies, nullable,
  ON DELETE SET NULL)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- access_policies ---
    op.create_table(
        "access_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        # HMI / Remote access
        sa.Column("allow_hmi", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("allow_vnc", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("allow_http", sa.Boolean(), nullable=False, server_default="false"),
        # Alarms
        sa.Column("allow_alarms_view", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("allow_alarms_acknowledge", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("alarm_severity_filter", sa.String(20), nullable=False, server_default="all"),
        # Audit
        sa.Column("allow_audit_view", sa.Boolean(), nullable=False, server_default="false"),
        # Flags
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_access_policies_tenant_id", "access_policies", ["tenant_id"])

    # --- user_site_access: add access_policy_id column ---
    op.add_column(
        "user_site_access",
        sa.Column(
            "access_policy_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_user_site_access_policy",
        "user_site_access",
        "access_policies",
        ["access_policy_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_user_site_access_policy_id",
        "user_site_access",
        ["access_policy_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_site_access_policy_id", table_name="user_site_access")
    op.drop_constraint("fk_user_site_access_policy", "user_site_access", type_="foreignkey")
    op.drop_column("user_site_access", "access_policy_id")
    op.drop_index("ix_access_policies_tenant_id", table_name="access_policies")
    op.drop_table("access_policies")
