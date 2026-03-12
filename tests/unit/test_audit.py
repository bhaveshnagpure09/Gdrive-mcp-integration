"""Tests for AI audit trail functionality."""

import pytest
from datetime import datetime, timezone

from app.ai.audit import save_checkpoint, get_checkpoints_for_request, calculate_total_tokens
from app.db.models.models import LangGraphCheckpoint, RequisitionRequest


def test_save_checkpoint_creates_record(db):
    """Test that save_checkpoint creates a database record."""
    # Create a requisition first
    requisition = RequisitionRequest(
        request_id="test-audit-req-001",
        auth_client_id=1,
        status=1,
        client_name="TestClient",
        correlation_id="test-audit-corr-001",
        received_at=datetime.now(timezone.utc),
    )
    db.add(requisition)
    db.commit()
    
    # Save a checkpoint
    test_state = {
        "parsed_jd": {"mandatory_skills": ["Python"], "preferred_skills": []},
        "correlation_id": "test-audit-corr-001",
    }
    
    save_checkpoint(
        db=db,
        request_id="test-audit-req-001",
        node_name="jd_parsing",
        state=test_state,
        token_count=500,
    )
    
    # Verify checkpoint was created
    checkpoints = db.query(LangGraphCheckpoint).filter_by(request_id="test-audit-req-001").all()
    assert len(checkpoints) == 1
    assert checkpoints[0].node_name == "jd_parsing"
    assert checkpoints[0].token_count == 500
    assert checkpoints[0].state_json == test_state


def test_get_checkpoints_for_request(db):
    """Test retrieving checkpoints for a request."""
    # Create requisition
    requisition = RequisitionRequest(
        request_id="test-audit-req-002",
        auth_client_id=1,
        status=1,
        client_name="TestClient",
        correlation_id="test-audit-corr-002",
        received_at=datetime.now(timezone.utc),
    )
    db.add(requisition)
    db.commit()
    
    # Save multiple checkpoints
    for i, node in enumerate(["jd_parsing", "skill_normalization", "matching_scoring"]):
        save_checkpoint(
            db=db,
            request_id="test-audit-req-002",
            node_name=node,
            state={"step": i + 1},
            token_count=100 * (i + 1),
        )
    
    # Retrieve checkpoints
    checkpoints = get_checkpoints_for_request(db, "test-audit-req-002")
    
    assert len(checkpoints) == 3
    assert checkpoints[0].node_name == "jd_parsing"
    assert checkpoints[1].node_name == "skill_normalization"
    assert checkpoints[2].node_name == "matching_scoring"


def test_calculate_total_tokens(db):
    """Test calculating total token usage."""
    # Create requisition
    requisition = RequisitionRequest(
        request_id="test-audit-req-003",
        auth_client_id=1,
        status=1,
        client_name="TestClient",
        correlation_id="test-audit-corr-003",
        received_at=datetime.now(timezone.utc),
    )
    db.add(requisition)
    db.commit()
    
    # Save checkpoints with different token counts
    save_checkpoint(db, "test-audit-req-003", "node1", {"data": "1"}, token_count=500)
    save_checkpoint(db, "test-audit-req-003", "node2", {"data": "2"}, token_count=300)
    save_checkpoint(db, "test-audit-req-003", "node3", {"data": "3"}, token_count=800)
    
    # Calculate total
    total = calculate_total_tokens(db, "test-audit-req-003")
    assert total == 1600


def test_checkpoint_ordering(db):
    """Test that checkpoints are returned in creation order."""
    # Create requisition
    requisition = RequisitionRequest(
        request_id="test-audit-req-004",
        auth_client_id=1,
        status=1,
        client_name="TestClient",
        correlation_id="test-audit-corr-004",
        received_at=datetime.now(timezone.utc),
    )
    db.add(requisition)
    db.commit()
    
    # Save checkpoints
    nodes = ["start", "middle", "end"]
    for node in nodes:
        save_checkpoint(db, "test-audit-req-004", node, {"node": node}, token_count=100)
    
    # Retrieve and verify order
    checkpoints = get_checkpoints_for_request(db, "test-audit-req-004")
    retrieved_nodes = [cp.node_name for cp in checkpoints]
    
    assert retrieved_nodes == nodes


def test_save_checkpoint_with_null_token_count(db):
    """Test saving checkpoint without token count (non-LLM nodes)."""
    # Create requisition
    requisition = RequisitionRequest(
        request_id="test-audit-req-005",
        auth_client_id=1,
        status=1,
        client_name="TestClient",
        correlation_id="test-audit-corr-005",
        received_at=datetime.now(timezone.utc),
    )
    db.add(requisition)
    db.commit()
    
    # Save checkpoint without token count
    save_checkpoint(
        db=db,
        request_id="test-audit-req-005",
        node_name="deterministic_node",
        state={"data": "no LLM used"},
        token_count=None,
    )
    
    # Verify
    checkpoints = get_checkpoints_for_request(db, "test-audit-req-005")
    assert len(checkpoints) == 1
    assert checkpoints[0].token_count is None
    
    # Calculate total should handle None values
    total = calculate_total_tokens(db, "test-audit-req-005")
    assert total == 0
