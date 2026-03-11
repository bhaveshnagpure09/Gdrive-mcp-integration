"""Availability evaluation logic for team members."""

from datetime import date, datetime, timedelta
from typing import Optional, Union

from sqlalchemy.orm import Session

from app.db.models import TeamMemberAllocation


def _parse_date(value: Union[str, date, None]) -> Optional[date]:
    """Coerce a string or date to a date object."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    # Try ISO format "YYYY-MM-DD"
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def calculate_requisition_window(
    expected_start_date: Optional[Union[str, date]],
    requisition_duration_month: Optional[int],
) -> tuple[date, date]:
    """Calculate requisition start and end dates.
    
    Args:
        expected_start_date: Expected start date or None (defaults to today)
        requisition_duration_month: Duration in months or None (defaults to 6)
    
    Returns:
        Tuple of (start_date, end_date)
    """
    start_date = _parse_date(expected_start_date) or date.today()
    duration = requisition_duration_month or 6
    
    # Calculate end date (approximately duration * 30 days)
    end_date = start_date + timedelta(days=duration * 30)
    
    return start_date, end_date


def get_overlapping_allocations(
    db: Session,
    team_member_id: str,
    start_date: date,
    end_date: date,
) -> list[TeamMemberAllocation]:
    """Retrieve overlapping allocations for a team member.
    
    Args:
        db: Database session
        team_member_id: Team member ID
        start_date: Requisition start date
        end_date: Requisition end date
    
    Returns:
        List of overlapping allocations
    """
    allocations = (
        db.query(TeamMemberAllocation)
        .filter(
            TeamMemberAllocation.team_member_id == team_member_id,
            TeamMemberAllocation.is_deleted == False,
            # Overlap condition: start_date < end_date AND end_date > start_date
            TeamMemberAllocation.start_date < end_date,
            TeamMemberAllocation.end_date > start_date,
        )
        .all()
    )
    
    return allocations


def calculate_availability(
    db: Session,
    team_member_id: str,
    start_date: date,
    end_date: date,
    threshold_percentage: float = 80.0,
) -> tuple[bool, float, float]:
    """Calculate team member availability for a requisition window.
    
    Args:
        db: Database session
        team_member_id: Team member ID
        start_date: Requisition start date
        end_date: Requisition end date
        threshold_percentage: Maximum allocation threshold (default 80%)
    
    Returns:
        Tuple of (is_available, available_capacity, total_allocation)
        - is_available: True if member has sufficient capacity
        - available_capacity: Percentage capacity available (0-100)
        - total_allocation: Total allocation percentage during window
    """
    allocations = get_overlapping_allocations(db, team_member_id, start_date, end_date)
    
    # Sum allocation percentages for overlapping projects (convert Decimal to float)
    total_allocation = sum(float(alloc.allocation_percentage or 0) for alloc in allocations)
    
    # Calculate available capacity
    available_capacity = max(0.0, 100.0 - total_allocation)
    
    # Determine availability based on threshold
    is_available = total_allocation < threshold_percentage
    
    return is_available, available_capacity, total_allocation


def evaluate_availability(
    db: Session,
    team_member_id: str,
    expected_start_date: Optional[date],
    requisition_duration_month: Optional[int],
    threshold_percentage: float = 80.0,
) -> dict:
    """Evaluate team member availability for a requisition.
    
    Main entry point for availability evaluation.
    
    Args:
        db: Database session
        team_member_id: Team member ID
        expected_start_date: Expected requisition start date
        requisition_duration_month: Requisition duration in months
        threshold_percentage: Maximum allocation threshold
    
    Returns:
        Dictionary with availability details:
        - is_available: bool
        - available_capacity: float
        - total_allocation: float
        - requisition_window: tuple[date, date]
    """
    start_date, end_date = calculate_requisition_window(
        expected_start_date, requisition_duration_month
    )
    
    is_available, available_capacity, total_allocation = calculate_availability(
        db, team_member_id, start_date, end_date, threshold_percentage
    )
    
    return {
        "is_available": is_available,
        "available_capacity": available_capacity,
        "total_allocation": total_allocation,
        "requisition_window": (start_date, end_date),
    }
