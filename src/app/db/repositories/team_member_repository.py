"""Repository for team member operations."""

from datetime import datetime
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.schemas.team_member import (
    AllocationDetails,
    SkillDetails,
    TeamMemberData,
    TeamMemberStatus,
)
from app.db.models.models import (
    CategoryMaster,
    SkillCertification,
    SkillMaster,
    TeamMember,
    TeamMemberAllocation,
    TeamMemberSkill,
    WorkTypeEnum,
)


class TeamMemberRepository:
    """Repository for team member data access."""

    def __init__(self, db: Session):
        self.db = db

    def upsert_team_member(self, member_data: TeamMemberData) -> tuple[bool, TeamMember]:
        """
        Upsert a team member.

        Returns:
            tuple: (was_created, team_member)
        """
        existing = (
            self.db.query(TeamMember)
            .filter(TeamMember.team_member_id == member_data.team_member_id)
            .first()
        )

        # Map work_type string to enum
        work_type = None
        if member_data.work_type:
            work_type_lower = member_data.work_type.lower()
            if work_type_lower in ["wfo", "wfh", "hybrid"]:
                work_type = WorkTypeEnum[work_type_lower]

        if existing:
            # Update existing member
            existing.full_name = member_data.full_name
            existing.designation = member_data.designation
            existing.profile_type = member_data.profile_type
            existing.is_active = member_data.team_member_status == TeamMemberStatus.active
            existing.experience_in_months = member_data.experience_in_months
            existing.base_location = member_data.base_location
            existing.work_type = work_type
            existing.profile_url = member_data.profile_url
            self.db.flush()
            return False, existing
        else:
            # Create new member
            new_member = TeamMember(
                team_member_id=member_data.team_member_id,
                full_name=member_data.full_name,
                designation=member_data.designation,
                profile_type=member_data.profile_type,
                is_active=member_data.team_member_status == TeamMemberStatus.active,
                experience_in_months=member_data.experience_in_months,
                base_location=member_data.base_location,
                work_type=work_type,
                profile_url=member_data.profile_url,
                created_at=datetime.utcnow(),
            )
            self.db.add(new_member)
            self.db.flush()
            return True, new_member

    def upsert_skills(self, team_member_id: str, skills: List[SkillDetails]) -> tuple[int, int]:
        """
        Upsert skills for a team member.

        Returns:
            tuple: (inserted_count, updated_count)
        """
        inserted = 0
        updated = 0
        # Track canonical skill_ids already processed for this member in this
        # call.  autoflush=False means pending inserts are invisible to queries
        # within the same transaction; tracking seen IDs avoids a PK violation
        # when the same skill name appears more than once in one member's list.
        seen_effective_ids: set = set()

        for skill_data in skills:
            # Ensure skill exists in skill_master.
            # Check by skill_id first, then by skill_name to avoid the
            # unique-constraint violation when different clients use different
            # IDs for the same canonical skill name.
            skill = (
                self.db.query(SkillMaster)
                .filter(SkillMaster.skill_id == skill_data.skill_id)
                .first()
            )

            if not skill:
                # Check by name — skill may already exist with a different ID
                skill = (
                    self.db.query(SkillMaster)
                    .filter(SkillMaster.skill_name == skill_data.skill_name)
                    .first()
                )

            if not skill:
                # Create skill if it doesn't exist
                # First ensure category exists
                category = None
                if skill_data.category:
                    category = (
                        self.db.query(CategoryMaster)
                        .filter(CategoryMaster.category_name == skill_data.category)
                        .first()
                    )
                    if not category:
                        # Get next category_id
                        max_id = self.db.query(func.max(CategoryMaster.category_id)).scalar() or 0
                        category = CategoryMaster(
                            category_id=max_id + 1, category_name=skill_data.category
                        )
                        self.db.add(category)
                        self.db.flush()

                category_id = category.category_id if category else 1  # Default category

                skill = SkillMaster(
                    skill_id=skill_data.skill_id,
                    skill_name=skill_data.skill_name,
                    category_id=category_id,
                )
                self.db.add(skill)
                self.db.flush()

            # Use the canonical skill_id from DB (may differ from submitted ID)
            effective_skill_id = skill.skill_id

            # Skip duplicate canonical skills within this member's list.
            # autoflush=False means in-session pending INSERTs are not visible
            # to subsequent queries, so deduplicate in Python instead.
            if effective_skill_id in seen_effective_ids:
                continue
            seen_effective_ids.add(effective_skill_id)

            # Upsert team_member_skill
            existing_skill = (
                self.db.query(TeamMemberSkill)
                .filter(
                    TeamMemberSkill.team_member_id == team_member_id,
                    TeamMemberSkill.skill_id == effective_skill_id,
                )
                .first()
            )

            if existing_skill:
                existing_skill.rating = skill_data.rating
                existing_skill.experience_in_months = skill_data.experience_in_months
                existing_skill.is_deleted = skill_data.is_deleted
                updated += 1
            else:
                new_skill = TeamMemberSkill(
                    team_member_id=team_member_id,
                    skill_id=effective_skill_id,
                    rating=skill_data.rating,
                    experience_in_months=skill_data.experience_in_months,
                    is_deleted=skill_data.is_deleted,
                )
                self.db.add(new_skill)
                inserted += 1

            # Handle certifications if provided
            if skill_data.certifications:
                for cert in skill_data.certifications:
                    existing_cert = None
                    if cert.certification_id:
                        existing_cert = (
                            self.db.query(SkillCertification)
                            .filter(SkillCertification.certification_id == cert.certification_id)
                            .first()
                        )

                    if existing_cert:
                        existing_cert.certificate = cert.certificate
                        existing_cert.issuer = cert.issuer
                        existing_cert.issued_date = cert.issued_date
                        existing_cert.valid_till = cert.valid_till
                    else:
                        new_cert = SkillCertification(
                            certification_id=cert.certification_id,
                            team_member_id=team_member_id,
                            skill_id=skill_data.skill_id,
                            certificate=cert.certificate,
                            issuer=cert.issuer,
                            issued_date=cert.issued_date,
                            valid_till=cert.valid_till,
                        )
                        self.db.add(new_cert)

        self.db.flush()
        return inserted, updated

    def upsert_allocations(
        self, team_member_id: str, allocations: List[AllocationDetails]
    ) -> tuple[int, int]:
        """
        Upsert allocations for a team member.

        Returns:
            tuple: (inserted_count, updated_count)
        """
        inserted = 0
        updated = 0
        # autoflush=False means pending INSERTs are invisible to subsequent queries in same tx.
        # Track project_ids already processed to avoid duplicate key violations.
        seen_project_ids: set = set()

        for alloc_data in allocations:
            # Skip duplicate project allocations within the same member's list
            if alloc_data.project_id in seen_project_ids:
                continue
            seen_project_ids.add(alloc_data.project_id)

            existing = (
                self.db.query(TeamMemberAllocation)
                .filter(
                    TeamMemberAllocation.team_member_id == team_member_id,
                    TeamMemberAllocation.project_id == alloc_data.project_id,
                )
                .first()
            )

            if existing:
                existing.allocation_percentage = alloc_data.allocation_percentage
                existing.start_date = alloc_data.start_date
                existing.end_date = alloc_data.end_date
                existing.billable = alloc_data.billable
                existing.is_deleted = alloc_data.is_deleted
                updated += 1
            else:
                new_alloc = TeamMemberAllocation(
                    team_member_id=team_member_id,
                    project_id=alloc_data.project_id,
                    allocation_percentage=alloc_data.allocation_percentage,
                    start_date=alloc_data.start_date,
                    end_date=alloc_data.end_date,
                    billable=alloc_data.billable,
                    is_deleted=alloc_data.is_deleted,
                )
                self.db.add(new_alloc)
                inserted += 1

        self.db.flush()
        return inserted, updated

    def ensure_default_category(self) -> CategoryMaster:
        """Ensure a default category exists."""
        category = (
            self.db.query(CategoryMaster).filter(CategoryMaster.category_name == "General").first()
        )
        if not category:
            # Use category_id=1 for the default category
            category = CategoryMaster(category_id=1, category_name="General")
            self.db.add(category)
            self.db.commit()
        return category
