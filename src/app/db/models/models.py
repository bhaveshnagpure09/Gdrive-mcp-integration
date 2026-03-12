"""Database models for the job skill mapping system."""

import enum
from datetime import datetime
from sqlalchemy import (
    Boolean,
    CHAR,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    JSON,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class WorkTypeEnum(enum.Enum):
    """Work type enumeration."""

    wfo = "wfo"
    wfh = "wfh"
    hybrid = "hybrid"


class AuthClient(Base):
    """Client applications authorized to access the system."""

    __tablename__ = "auth_clients"

    id = Column(SmallInteger, primary_key=True, autoincrement=True)
    client_name = Column(String(100), nullable=False)
    client_code = Column(String(50), nullable=False, unique=True)
    client_secret_hash = Column(String(255), nullable=False)
    auth_type = Column(String(10), nullable=False, default="OAUTH")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    access_tokens = relationship("AuthAccessToken", back_populates="client")
    requisition_requests = relationship("RequisitionRequest", back_populates="client")


class AuthAccessToken(Base):
    """Access tokens issued to clients."""

    __tablename__ = "auth_access_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    auth_client_id = Column(SmallInteger, ForeignKey("auth_clients.id"), nullable=False)
    access_token = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, nullable=False, default=False)
    issued_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    client = relationship("AuthClient", back_populates="access_tokens")


class RequisitionStatusMaster(Base):
    """Master table for requisition request statuses."""

    __tablename__ = "requisition_status_master"

    status_id = Column(SmallInteger, primary_key=True)
    status_key = Column(String(40), nullable=False, unique=True)
    status_message = Column(String(255), nullable=False)

    # Relationships
    requisition_requests = relationship("RequisitionRequest", back_populates="status_ref")


class RequisitionRequest(Base):
    """Metadata for each incoming requisition request."""

    __tablename__ = "requisition_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(64), nullable=False, unique=True)
    auth_client_id = Column(SmallInteger, ForeignKey("auth_clients.id"), nullable=False)
    status = Column(SmallInteger, ForeignKey("requisition_status_master.status_id"), nullable=False)
    client_name = Column(String(100), nullable=False)
    correlation_id = Column(String(100), nullable=True)
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    match_results = Column(JSON, nullable=True)
    processing_status = Column(String(20), nullable=True, default="QUEUED")

    # Relationships
    client = relationship("AuthClient", back_populates="requisition_requests")
    status_ref = relationship("RequisitionStatusMaster", back_populates="requisition_requests")
    detail = relationship("RequisitionDetail", back_populates="request", uselist=False)
    checkpoints = relationship("LangGraphCheckpoint", back_populates="request")


class RequisitionDetail(Base):
    """Raw JSON payload of each requisition request."""

    __tablename__ = "requisition_detail"

    id = Column(Integer, primary_key=True, autoincrement=True)
    requisition_request_id = Column(
        Integer, ForeignKey("requisition_requests.id"), nullable=False, unique=True
    )
    payload_json = Column(JSON, nullable=False)
    payload_hash = Column(CHAR(64), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    request = relationship("RequisitionRequest", back_populates="detail")


class CategoryMaster(Base):
    """Master table for skill categories."""

    __tablename__ = "category_master"

    category_id = Column(SmallInteger, primary_key=True, autoincrement=True)
    category_name = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    skills = relationship("SkillMaster", back_populates="category")


class SkillMaster(Base):
    """Canonical dictionary of all skills."""

    __tablename__ = "skill_master"

    skill_id = Column(String(50), primary_key=True)
    skill_name = Column(String(100), nullable=False, unique=True)
    category_id = Column(SmallInteger, ForeignKey("category_master.category_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    category = relationship("CategoryMaster", back_populates="skills")
    team_member_skills = relationship("TeamMemberSkill", back_populates="skill")


class TeamMember(Base):
    """Core profile information for each team member."""

    __tablename__ = "team_member"

    team_member_id = Column(String(50), primary_key=True)
    full_name = Column(String(200), nullable=True)
    designation = Column(String(100), nullable=True)
    profile_type = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    experience_in_months = Column(Integer, nullable=True)
    base_location = Column(String(100), nullable=True)
    work_type = Column(Enum(WorkTypeEnum), nullable=True)
    profile_url = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    skills = relationship("TeamMemberSkill", back_populates="team_member")
    allocations = relationship("TeamMemberAllocation", back_populates="team_member")


class TeamMemberAllocation(Base):
    """Project allocation details for each team member."""

    __tablename__ = "team_member_allocation"

    team_member_id = Column(String(50), ForeignKey("team_member.team_member_id"), primary_key=True)
    project_id = Column(String(50), primary_key=True)
    allocation_percentage = Column(Numeric(5, 2), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    billable = Column(Boolean, nullable=True)
    is_deleted = Column(Boolean, default=False)

    # Relationships
    team_member = relationship("TeamMember", back_populates="allocations")


class TeamMemberSkill(Base):
    """Links team members to skills with proficiency details."""

    __tablename__ = "team_member_skill"

    team_member_id = Column(String(50), ForeignKey("team_member.team_member_id"), primary_key=True)
    skill_id = Column(String(50), ForeignKey("skill_master.skill_id"), primary_key=True)
    rating = Column(Integer, nullable=True)
    experience_in_months = Column(Integer, nullable=True)
    is_deleted = Column(Boolean, default=False)

    # Relationships
    team_member = relationship("TeamMember", back_populates="skills")
    skill = relationship("SkillMaster", back_populates="team_member_skills")
    certifications = relationship("SkillCertification", back_populates="team_member_skill")


class SkillCertification(Base):
    """Certification details for a specific team member's skill."""

    __tablename__ = "skill_certification"

    id = Column(Integer, primary_key=True, autoincrement=True)
    certification_id = Column(String(100), nullable=True)
    team_member_id = Column(String(50), nullable=False)
    skill_id = Column(String(50), nullable=False)
    certificate = Column(String(150), nullable=True)
    issuer = Column(String(100), nullable=True)
    issued_date = Column(Date, nullable=True)
    valid_till = Column(Date, nullable=True)

    # Composite foreign key
    __table_args__ = (
        ForeignKeyConstraint(
            ["team_member_id", "skill_id"],
            ["team_member_skill.team_member_id", "team_member_skill.skill_id"],
        ),
    )

    # Relationships
    team_member_skill = relationship("TeamMemberSkill", back_populates="certifications")


class LangGraphCheckpoint(Base):
    """State of the AI agent graph for auditing and debugging."""

    __tablename__ = "langgraph_checkpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(64), ForeignKey("requisition_requests.request_id"), nullable=False)
    node_name = Column(String(50), nullable=False)
    state_json = Column(JSON, nullable=False)
    token_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    request = relationship("RequisitionRequest", back_populates="checkpoints")


class TeamMemberEmbedding(Base):
    """Vector embeddings for team member profiles, used for AI-based candidate matching."""

    __tablename__ = "team_member_embeddings"

    team_member_id = Column(
        String(50),
        ForeignKey("team_member.team_member_id"),
        primary_key=True,
    )
    # Stored as a JSON-encoded float array; the Alembic migration creates the actual vector column
    embedding = Column(String, nullable=False)
    profile_text = Column(String, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    team_member = relationship("TeamMember", backref="embeddings")
