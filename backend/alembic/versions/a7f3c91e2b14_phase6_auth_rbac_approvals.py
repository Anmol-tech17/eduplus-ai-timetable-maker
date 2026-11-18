"""phase6_auth_rbac_approvals

Revision ID: a7f3c91e2b14
Revises: 5cc27eb93e43
Create Date: 2026-11-18 12:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7f3c91e2b14'
down_revision: Union[str, None] = '5cc27eb93e43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend user_accounts with full_name, can_approve_timetable, and coordinator role
    op.add_column('user_accounts', sa.Column('full_name', sa.String(length=128), nullable=True))
    op.add_column(
        'user_accounts',
        sa.Column('can_approve_timetable', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.drop_constraint('chk_user_role', 'user_accounts', type_='check')
    op.create_check_constraint(
        'chk_user_role',
        'user_accounts',
        "role IN ('admin', 'coordinator', 'teacher', 'student')",
    )

    # 2. Extend timetable_versions with approval workflow columns & statuses
    op.add_column('timetable_versions', sa.Column('submitted_by', sa.Uuid(), nullable=True))
    op.add_column('timetable_versions', sa.Column('submitted_at', sa.DateTime(), nullable=True))
    op.add_column('timetable_versions', sa.Column('approved_by', sa.Uuid(), nullable=True))
    op.add_column('timetable_versions', sa.Column('approved_at', sa.DateTime(), nullable=True))
    op.add_column('timetable_versions', sa.Column('approval_comment', sa.Text(), nullable=True))
    op.create_foreign_key(
        'fk_tt_submitted_by_user', 'timetable_versions', 'user_accounts',
        ['submitted_by'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_tt_approved_by_user', 'timetable_versions', 'user_accounts',
        ['approved_by'], ['id'], ondelete='SET NULL',
    )
    op.drop_constraint('chk_tt_status', 'timetable_versions', type_='check')
    op.create_check_constraint(
        'chk_tt_status',
        'timetable_versions',
        "status IN ('draft', 'candidate', 'pending_approval', 'approved', 'rejected', 'published', 'archived')",
    )

    # 3. Create teacher_requests table
    op.create_table(
        'teacher_requests',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('teacher_id', sa.Uuid(), nullable=False),
        sa.Column('department_id', sa.Uuid(), nullable=False),
        sa.Column('submitted_by', sa.Uuid(), nullable=True),
        sa.Column('request_type', sa.String(length=32), nullable=False),
        sa.Column('day_name', sa.String(length=16), nullable=True),
        sa.Column('time_slot_code', sa.String(length=16), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('reviewed_by', sa.Uuid(), nullable=True),
        sa.Column('review_comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "request_type IN ('availability', 'reschedule', 'substitution', 'cancellation')",
            name='chk_teacher_req_type',
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name='chk_teacher_req_status',
        ),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['user_accounts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['submitted_by'], ['user_accounts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_teacher_requests_teacher_id', 'teacher_requests', ['teacher_id'], unique=False)
    op.create_index('ix_teacher_requests_department_id', 'teacher_requests', ['department_id'], unique=False)
    op.create_index('idx_teacher_req_dept_status', 'teacher_requests', ['department_id', 'status'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_teacher_req_dept_status', table_name='teacher_requests')
    op.drop_index('ix_teacher_requests_department_id', table_name='teacher_requests')
    op.drop_index('ix_teacher_requests_teacher_id', table_name='teacher_requests')
    op.drop_table('teacher_requests')

    op.drop_constraint('chk_tt_status', 'timetable_versions', type_='check')
    op.create_check_constraint(
        'chk_tt_status',
        'timetable_versions',
        "status IN ('draft', 'candidate', 'published', 'archived')",
    )
    op.drop_constraint('fk_tt_approved_by_user', 'timetable_versions', type_='foreignkey')
    op.drop_constraint('fk_tt_submitted_by_user', 'timetable_versions', type_='foreignkey')
    op.drop_column('timetable_versions', 'approval_comment')
    op.drop_column('timetable_versions', 'approved_at')
    op.drop_column('timetable_versions', 'approved_by')
    op.drop_column('timetable_versions', 'submitted_at')
    op.drop_column('timetable_versions', 'submitted_by')

    op.drop_constraint('chk_user_role', 'user_accounts', type_='check')
    op.create_check_constraint(
        'chk_user_role',
        'user_accounts',
        "role IN ('admin', 'teacher', 'student')",
    )
    op.drop_column('user_accounts', 'can_approve_timetable')
    op.drop_column('user_accounts', 'full_name')
