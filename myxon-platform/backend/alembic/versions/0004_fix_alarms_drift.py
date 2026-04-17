"""Fix alarms schema drift: add missing details and triggered_at columns

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-17

Расхождения между Alarm-моделью и миграцией 0001:
1. alarms.details    — JSON поле для дополнительных данных аларма, не попало в 0001
2. alarms.triggered_at — TIMESTAMP поле «когда сработал аларм»,
                          в 0001 его нет (вместо него был created_at как суррогат);
                          добавляем с server_default=now() чтобы не нарушить NOT NULL

Поле raw_payload (в 0001, но не в модели) оставляем — лишний столбец не ломает ORM.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── alarms: добавить details (JSON, nullable) ──────────────────────────
    op.add_column(
        "alarms",
        sa.Column("details", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )

    # ── alarms: добавить triggered_at (TIMESTAMPTZ, NOT NULL) ─────────────
    # server_default=now() нужен чтобы безопасно добавить NOT NULL к существующим строкам.
    # После добавления колонки default можно убрать вручную если нужна строгость,
    # но для dev-окружения это не критично.
    op.add_column(
        "alarms",
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_column("alarms", "triggered_at")
    op.drop_column("alarms", "details")
