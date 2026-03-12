"""Repository for requisition operations."""

import hashlib
import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.api.schemas.requisition import RequisitionRequest
from app.db.models.models import RequisitionDetail, RequisitionRequest as RequisitionRequestModel


class RequisitionRepository:
    """Repository for requisition data access."""

    def __init__(self, db: Session):
        self.db = db

    def create_requisition(
        self, request_data: RequisitionRequest, auth_client_id: int
    ) -> tuple[RequisitionRequestModel, str]:
        """
        Create a new requisition request.

        Returns:
            tuple: (requisition_request, correlation_id)
        """
        # Generate correlation ID
        correlation_id = (
            f"CORR-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{request_data.request_id[:8]}"
        )

        # Create requisition request
        req = RequisitionRequestModel(
            request_id=request_data.request_id,
            auth_client_id=auth_client_id,
            status=1,  # RECEIVED status
            client_name=request_data.client_name or request_data.job_description.client_name,
            correlation_id=correlation_id,
            received_at=datetime.utcnow(),
        )
        self.db.add(req)
        self.db.flush()

        # Create requisition detail with payload hash
        payload_dict = request_data.model_dump(mode="json")
        payload_json = json.dumps(payload_dict, sort_keys=True)
        payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()

        detail = RequisitionDetail(
            requisition_request_id=req.id,
            payload_json=payload_dict,
            payload_hash=payload_hash,
        )
        self.db.add(detail)
        self.db.flush()

        return req, correlation_id

    def get_requisition_by_correlation_id(
        self, correlation_id: str
    ) -> Optional[RequisitionRequestModel]:
        """Get requisition by correlation ID."""
        return (
            self.db.query(RequisitionRequestModel)
            .filter(RequisitionRequestModel.correlation_id == correlation_id)
            .first()
        )

    def get_requisition_by_request_id(self, request_id: str) -> Optional[RequisitionRequestModel]:
        """Get requisition by request ID."""
        return (
            self.db.query(RequisitionRequestModel)
            .filter(RequisitionRequestModel.request_id == request_id)
            .first()
        )

    def update_requisition_status(
        self, requisition_id: int, status_id: int, completed_at: Optional[datetime] = None
    ):
        """Update requisition status."""
        req = (
            self.db.query(RequisitionRequestModel)
            .filter(RequisitionRequestModel.id == requisition_id)
            .first()
        )
        if req:
            req.status = status_id
            if completed_at:
                req.completed_at = completed_at
            self.db.flush()

    def save_match_results(self, correlation_id: str, results: list) -> None:
        """Persist match results to DB so all workers can read them."""
        req = (
            self.db.query(RequisitionRequestModel)
            .filter(RequisitionRequestModel.correlation_id == correlation_id)
            .first()
        )
        if req:
            req.match_results = results
            req.processing_status = "COMPLETED"
            req.completed_at = datetime.utcnow()
            self.db.flush()

    def get_match_results(self, correlation_id: str) -> Optional[list]:
        """Retrieve persisted match results from DB."""
        req = (
            self.db.query(RequisitionRequestModel)
            .filter(RequisitionRequestModel.correlation_id == correlation_id)
            .first()
        )
        if req is None:
            return None
        return req.match_results  # None = still processing, list = done
