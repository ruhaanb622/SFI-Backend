"""Persistence models for SFI safety-hub workflows.

These tables intentionally build on the existing ``SfiSpec`` and ``UserGear``
models instead of duplicating specification or equipment data.
"""

from datetime import datetime

from __init__ import db


INSPECTION_OUTCOMES = ("pass", "attention", "fail")
REVIEW_STATUSES = ("pending", "approved", "changes_requested", "rejected")


class TracksideInspection(db.Model):
    __tablename__ = "sfi_trackside_inspections"

    id = db.Column(db.Integer, primary_key=True)
    gear_id = db.Column(
        db.Integer,
        db.ForeignKey("user_gear.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    inspector_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    outcome = db.Column(db.String(20), nullable=False, default="attention")
    checklist_json = db.Column(db.Text, nullable=False, default="{}")
    notes = db.Column(db.String(1000), nullable=False, default="")
    next_due_on = db.Column(db.String(20), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    def to_dict(self):
        import json

        try:
            checklist = json.loads(self.checklist_json or "{}")
        except (TypeError, ValueError):
            checklist = {}
        return {
            "id": self.id,
            "gearId": self.gear_id,
            "inspectorId": self.inspector_id,
            "outcome": self.outcome,
            "checklist": checklist,
            "notes": self.notes,
            "nextDueOn": self.next_due_on,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class ManufacturerReview(db.Model):
    __tablename__ = "sfi_manufacturer_reviews"

    id = db.Column(db.Integer, primary_key=True)
    submitted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    manufacturer_name = db.Column(db.String(255), nullable=False)
    product_name = db.Column(db.String(255), nullable=False)
    spec_number = db.Column(db.String(80), nullable=False, index=True)
    evidence_url = db.Column(db.String(1000), nullable=False, default="")
    submission_note = db.Column(db.String(2000), nullable=False, default="")
    status = db.Column(db.String(30), nullable=False, default="pending", index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    review_note = db.Column(db.String(2000), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "submittedBy": self.submitted_by,
            "manufacturerName": self.manufacturer_name,
            "productName": self.product_name,
            "specNumber": self.spec_number,
            "evidenceUrl": self.evidence_url,
            "submissionNote": self.submission_note,
            "status": self.status,
            "reviewerId": self.reviewer_id,
            "reviewNote": self.review_note,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "reviewedAt": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }


class SafetyLearningProgress(db.Model):
    __tablename__ = "sfi_learning_progress"
    __table_args__ = (
        db.UniqueConstraint("user_id", "module_id", name="uq_sfi_learning_user_module"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    module_id = db.Column(db.String(80), nullable=False)
    completed = db.Column(db.Boolean, nullable=False, default=False)
    score = db.Column(db.Integer, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "moduleId": self.module_id,
            "completed": bool(self.completed),
            "score": self.score,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
