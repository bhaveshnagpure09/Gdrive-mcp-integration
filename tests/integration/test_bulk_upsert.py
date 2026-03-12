"""Integration tests for bulk upsert endpoint."""

from datetime import datetime, timezone


def test_bulk_upsert_success(client, db):
    """Test successful bulk upsert of team member data."""
    payload = {
        "metadata": {
            "batch_id": "BATCH-001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_records": 1,
            "batch_number": 1,
            "total_batches": 1,
            "records_in_batch": 1,
            "source_system": "TEST_SYSTEM",
            "schema_version": "v1",
            "status": {"code": 200, "key": "SUCCESS", "message": "Batch created"},
        },
        "team_members": [
            {
                "team_member_id": "TM001",
                "team_member_status": "active",
                "experience_in_months": 36,
                "full_name": "John Doe",
                "designation": "Senior Developer",
                "profile_type": "Technical",
                "base_location": "Bangalore",
                "work_type": "hybrid",
                "skills": [
                    {
                        "skill_id": "PYTHON",
                        "skill_name": "Python",
                        "rating": 8,
                        "experience_in_months": 30,
                        "category": "Programming",
                        "is_deleted": False,
                    },
                    {
                        "skill_id": "FASTAPI",
                        "skill_name": "FastAPI",
                        "rating": 7,
                        "experience_in_months": 12,
                        "category": "Framework",
                        "is_deleted": False,
                    },
                ],
                "allocations": [
                    {
                        "project_id": "PROJ001",
                        "allocation_percentage": 80.0,
                        "billable": True,
                        "is_deleted": False,
                    }
                ],
            }
        ],
    }

    response = client.post("/api/v1/team-members/skill-availability/bulk-upsert", json=payload)

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "ACCEPTED"
    assert data["summary"]["records_received"] == 1
    assert data["summary"]["team_members_inserted"] == 1
    assert data["summary"]["skills_inserted"] == 2
    assert data["summary"]["allocations_inserted"] == 1


def test_bulk_upsert_update_existing(client, db):
    """Test updating existing team member data."""
    # First insert
    payload = {
        "metadata": {
            "batch_id": "BATCH-002",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_records": 1,
            "batch_number": 1,
            "total_batches": 1,
            "records_in_batch": 1,
            "source_system": "TEST_SYSTEM",
            "schema_version": "v1",
            "status": {"code": 200, "key": "SUCCESS", "message": "Batch created"},
        },
        "team_members": [
            {
                "team_member_id": "TM002",
                "team_member_status": "active",
                "experience_in_months": 24,
                "full_name": "Jane Smith",
                "skills": [
                    {
                        "skill_id": "JAVA",
                        "skill_name": "Java",
                        "rating": 7,
                        "experience_in_months": 20,
                        "is_deleted": False,
                    }
                ],
            }
        ],
    }

    response1 = client.post("/api/v1/team-members/skill-availability/bulk-upsert", json=payload)
    assert response1.status_code == 202

    # Update with new data
    payload["metadata"]["batch_id"] = "BATCH-003"
    payload["team_members"][0]["experience_in_months"] = 30
    payload["team_members"][0]["skills"][0]["rating"] = 9

    response2 = client.post("/api/v1/team-members/skill-availability/bulk-upsert", json=payload)
    assert response2.status_code == 202
    data = response2.json()
    assert data["summary"]["team_members_updated"] == 1
    assert data["summary"]["skills_updated"] == 1


def test_bulk_upsert_validation_error(client, db):
    """Test validation error with invalid payload."""
    invalid_payload = {
        "metadata": {
            "batch_id": "BATCH-004",
            "timestamp": "invalid-date",
            # Missing required fields
        },
        "team_members": [],
    }

    response = client.post(
        "/api/v1/team-members/skill-availability/bulk-upsert", json=invalid_payload
    )
    assert response.status_code == 422  # Validation error
