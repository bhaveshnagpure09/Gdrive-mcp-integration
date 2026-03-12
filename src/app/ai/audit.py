"""Audit trail utilities for LangGraph execution."""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from app.db.models.models import LangGraphCheckpoint

logger = logging.getLogger(__name__)


def save_checkpoint(
    db: Session,
    request_id: str,
    node_name: str,
    state: Dict[str, Any],
    token_count: Optional[int] = None,
) -> None:
    """Save a LangGraph checkpoint to the database for audit trail.
    
    Args:
        db: Database session
        request_id: The originating request ID
        node_name: Name of the graph node that was executed
        state: The graph state after node execution
        token_count: Number of LLM tokens consumed (if applicable)
    """
    try:
        checkpoint = LangGraphCheckpoint(
            request_id=request_id,
            node_name=node_name,
            state_json=state,
            token_count=token_count,
            created_at=datetime.now(timezone.utc),
        )
        db.add(checkpoint)
        db.commit()
        
        logger.info(
            "Saved checkpoint",
            extra={
                "request_id": request_id,
                "node_name": node_name,
                "token_count": token_count,
            },
        )
    except Exception as exc:
        logger.error(
            "Failed to save checkpoint",
            extra={
                "request_id": request_id,
                "node_name": node_name,
                "error": str(exc),
            },
            exc_info=True,
        )
        db.rollback()
        # Don't raise - audit failure shouldn't stop the workflow


def get_checkpoints_for_request(
    db: Session, request_id: str
) -> list[LangGraphCheckpoint]:
    """Retrieve all checkpoints for a request.
    
    Args:
        db: Database session
        request_id: The request ID to query
        
    Returns:
        List of checkpoint records ordered by creation time
    """
    return (
        db.query(LangGraphCheckpoint)
        .filter(LangGraphCheckpoint.request_id == request_id)
        .order_by(LangGraphCheckpoint.created_at)
        .all()
    )


def calculate_total_tokens(db: Session, request_id: str) -> int:
    """Calculate total token usage for a request.
    
    Args:
        db: Database session
        request_id: The request ID to query
        
    Returns:
        Total token count across all checkpoints
    """
    checkpoints = get_checkpoints_for_request(db, request_id)
    return sum(cp.token_count or 0 for cp in checkpoints)
