"""phase7_production_security_reliability

Revision ID: c4e8a12f9b03
Revises: a7f3c91e2b14
Create Date: 2026-11-18 13:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e8a12f9b03'
down_revision: Union[str, None] = 'a7f3c91e2b14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Persistent multi-worker JWT revocation table
    op.create_table(
        'revoked_tokens',
        sa.Column('jti', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('token_type', sa.String(length=16), nullable=False, server_default='access'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('jti'),
    )
    op.create_index('ix_revoked_tokens_user_id', 'revoked_tokens', ['user_id'], unique=False)
    op.create_index('ix_revoked_tokens_expires_at', 'revoked_tokens', ['expires_at'], unique=False)

    # 2. Persistent multi-worker login rate-limiting table
    op.create_table(
        'login_attempts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('rate_key', sa.String(length=255), nullable=False),
        sa.Column('attempted_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_login_attempts_rate_key', 'login_attempts', ['rate_key'], unique=False)
    op.create_index('ix_login_attempts_attempted_at', 'login_attempts', ['attempted_at'], unique=False)
    op.create_index('idx_login_attempts_key_time', 'login_attempts', ['rate_key', 'attempted_at'], unique=False)

    # 3. Production query performance indexes
    op.create_index('idx_audit_logs_action_created', 'audit_logs', ['action', 'created_at'], unique=False)
    op.create_index('idx_gen_runs_status_started', 'generation_runs', ['status', 'started_at'], unique=False)
    op.create_index(
        'idx_tt_ver_dept_ay_sem_status',
        'timetable_versions',
        ['department_id', 'academic_year_code', 'semester', 'status'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('idx_tt_ver_dept_ay_sem_status', table_name='timetable_versions')
    op.drop_index('idx_gen_runs_status_started', table_name='generation_runs')
    op.drop_index('idx_audit_logs_action_created', table_name='audit_logs')

    op.drop_index('idx_login_attempts_key_time', table_name='login_attempts')
    op.drop_index('ix_login_attempts_attempted_at', table_name='login_attempts')
    op.drop_index('ix_login_attempts_rate_key', table_name='login_attempts')
    op.drop_table('login_attempts')

    op.drop_index('ix_revoked_tokens_expires_at', table_name='revoked_tokens')
    op.drop_index('ix_revoked_tokens_user_id', table_name='revoked_tokens')
    op.drop_table('revoked_tokens')
