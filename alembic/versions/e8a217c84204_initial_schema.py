"""initial_schema

Revision ID: e8a217c84204
Revises:
Create Date: 2026-02-03 01:12:39.532253

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "e8a217c84204"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create auth_clients table
    op.create_table(
        "auth_clients",
        sa.Column("id", sa.SmallInteger(), autoincrement=True, nullable=False),
        sa.Column("client_name", sa.String(length=100), nullable=False),
        sa.Column("client_code", sa.String(length=50), nullable=False),
        sa.Column("client_secret_hash", sa.String(length=255), nullable=False),
        sa.Column("auth_type", sa.String(length=10), nullable=False, server_default="OAUTH"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_code"),
    )

    # Create auth_access_tokens table
    op.create_table(
        "auth_access_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("auth_client_id", sa.SmallInteger(), nullable=False),
        sa.Column("access_token", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column(
            "issued_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["auth_client_id"], ["auth_clients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("access_token"),
    )

    # Create requisition_status_master table
    op.create_table(
        "requisition_status_master",
        sa.Column("status_id", sa.SmallInteger(), nullable=False),
        sa.Column("status_key", sa.String(length=40), nullable=False),
        sa.Column("status_message", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("status_id"),
        sa.UniqueConstraint("status_key"),
    )

    # Create requisition_requests table
    op.create_table(
        "requisition_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("auth_client_id", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.SmallInteger(), nullable=False),
        sa.Column("client_name", sa.String(length=100), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["auth_client_id"], ["auth_clients.id"]),
        sa.ForeignKeyConstraint(["status"], ["requisition_status_master.status_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )

    # Create requisition_detail table
    op.create_table(
        "requisition_detail",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("requisition_request_id", sa.Integer(), nullable=False),
        sa.Column("payload_json", JSONB, nullable=False),
        sa.Column("payload_hash", sa.CHAR(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["requisition_request_id"], ["requisition_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("requisition_request_id"),
        sa.UniqueConstraint("payload_hash"),
    )

    # Create category_master table
    op.create_table(
        "category_master",
        sa.Column("category_id", sa.SmallInteger(), autoincrement=True, nullable=False),
        sa.Column("category_name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("category_id"),
        sa.UniqueConstraint("category_name"),
    )

    # Create skill_master table
    op.create_table(
        "skill_master",
        sa.Column("skill_id", sa.String(length=50), nullable=False),
        sa.Column("skill_name", sa.String(length=100), nullable=False),
        sa.Column("category_id", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["category_id"], ["category_master.category_id"]),
        sa.PrimaryKeyConstraint("skill_id"),
        sa.UniqueConstraint("skill_name"),
    )

    # Create team_member table
    op.create_table(
        "team_member",
        sa.Column("team_member_id", sa.String(length=50), nullable=False),
        sa.Column("designation", sa.String(length=100), nullable=True),
        sa.Column("profile_type", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("experience_in_months", sa.Integer(), nullable=True),
        sa.Column("base_location", sa.String(length=100), nullable=True),
        sa.Column(
            "work_type",
            sa.Enum("wfo", "wfh", "hybrid", name="work_type_enum"),
            nullable=True,
        ),
        sa.Column("profile_url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("team_member_id"),
    )

    # Create team_member_allocation table
    op.create_table(
        "team_member_allocation",
        sa.Column("team_member_id", sa.String(length=50), nullable=False),
        sa.Column("project_id", sa.String(length=50), nullable=False),
        sa.Column("allocation_percentage", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("billable", sa.Boolean(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.ForeignKeyConstraint(["team_member_id"], ["team_member.team_member_id"]),
        sa.PrimaryKeyConstraint("team_member_id", "project_id"),
    )

    # Create team_member_skill table
    op.create_table(
        "team_member_skill",
        sa.Column("team_member_id", sa.String(length=50), nullable=False),
        sa.Column("skill_id", sa.String(length=50), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("experience_in_months", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.ForeignKeyConstraint(["team_member_id"], ["team_member.team_member_id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["skill_master.skill_id"]),
        sa.PrimaryKeyConstraint("team_member_id", "skill_id"),
    )

    # Create skill_certification table
    op.create_table(
        "skill_certification",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("certification_id", sa.String(length=100), nullable=True),
        sa.Column("team_member_id", sa.String(length=50), nullable=False),
        sa.Column("skill_id", sa.String(length=50), nullable=False),
        sa.Column("certificate", sa.String(length=150), nullable=True),
        sa.Column("issuer", sa.String(length=100), nullable=True),
        sa.Column("issued_date", sa.Date(), nullable=True),
        sa.Column("valid_till", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["team_member_id", "skill_id"],
            ["team_member_skill.team_member_id", "team_member_skill.skill_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create langgraph_checkpoints table
    op.create_table(
        "langgraph_checkpoints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("node_name", sa.String(length=50), nullable=False),
        sa.Column("state_json", JSONB, nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["request_id"], ["requisition_requests.request_id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Insert initial requisition status master data
    op.execute("""
        INSERT INTO requisition_status_master (status_id, status_key, status_message) VALUES
        (1, 'RECEIVED', 'Request received and queued for processing'),
        (2, 'PROCESSING', 'AI pipeline is processing the request'),
        (3, 'COMPLETED', 'Request processed successfully'),
        (4, 'FAILED', 'Request processing failed'),
        (5, 'CANCELLED', 'Request was cancelled')
        """)


def downgrade() -> None:
    op.drop_table("langgraph_checkpoints")
    op.drop_table("skill_certification")
    op.drop_table("team_member_skill")
    op.drop_table("team_member_allocation")
    op.drop_table("team_member")
    op.drop_table("skill_master")
    op.drop_table("category_master")
    op.drop_table("requisition_detail")
    op.drop_table("requisition_requests")
    op.drop_table("requisition_status_master")
    op.drop_table("auth_access_tokens")
    op.drop_table("auth_clients")
    op.execute("DROP TYPE work_type_enum")
