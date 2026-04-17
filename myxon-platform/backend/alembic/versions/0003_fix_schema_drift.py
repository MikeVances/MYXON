"""Fix schema drift: sites.location→address, alarms.code VARCHAR→Integer

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-17

Исправляет два расхождения между моделями и исходными миграциями:
1. sites.location переименовывается в address (модель изменилась, миграция не обновлялась)
2. alarms.code VARCHAR→INTEGER (модель всегда был int, в миграции ошибочно VARCHAR)
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── sites: location → address ──────────────────────────────────────────
    # Переименовываем колонку — данных нет, поэтому безопасно
    op.alter_column("sites", "location", new_column_name="address")

    # ── alarms: code VARCHAR → INTEGER ─────────────────────────────────────
    # Требует явного USING для приведения типа в PostgreSQL
    op.alter_column(
        "alarms",
        "code",
        type_=sa.Integer(),
        postgresql_using="code::integer",
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column("alarms", "code", type_=sa.String(100), existing_nullable=False)
    op.alter_column("sites", "address", new_column_name="location")
