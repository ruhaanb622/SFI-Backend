"""Integrated API for the six SFI safety-hub ideations.

Features:
- Spec Compass: intent-based, explainable specification matching.
- QR Participation Checker: signed event/gear participation credentials.
- Mobile Trackside Inspector Mode: fast checklist + inspection records.
- Inspection/Recertification Timeline: one chronological gear lifecycle view.
- Manufacturer Review Portal: submit and review product evidence.
- Motorsports Safety Learning Hub: curated modules + per-user progress.

The module builds on the existing SfiSpec/UserGear data and permission system.
"""

from datetime import date, datetime, timedelta, timezone
import json
import os
import re
import secrets

import jwt
from flask import Blueprint, g, jsonify, request
from flask_restful import Api, Resource
from sqlalchemy import or_

from __init__ import db
from api.authorize import token_required
from model.group import user_has_permission
from model.sfi_safety import (
    INSPECTION_OUTCOMES,
    REVIEW_STATUSES,
    ManufacturerReview,
    SafetyLearningProgress,
    TracksideInspection,
)
from model.sfi_spec import SfiSpec
from model.user_gear import UserGear


sfi_safety_api = Blueprint("sfi_safety_api", __name__, url_prefix="/api/sfi")
api = Api(sfi_safety_api)

MAX_COMPASS_RESULTS = 20
MAX_QR_HOURS = 24

LEARNING_MODULES = [
    {
        "id": "labels-and-specs",
        "title": "Read an SFI Label",
        "minutes": 5,
        "level": "essential",
        "summary": "Identify specification numbers, certification markings, and the information to verify before an event.",
        "checks": [
            "Find the specification number on the label.",
            "Match the label to the equipment type.",
            "Verify current requirements with the official specification or sanctioning body.",
        ],
    },
    {
        "id": "pre-event-gear-check",
        "title": "Pre-Event Gear Check",
        "minutes": 7,
        "level": "essential",
        "summary": "Build a repeatable inspection routine for visible damage, fit, labels, and documentation.",
        "checks": [
            "Inspect for cuts, fraying, cracks, heat damage, or contamination.",
            "Confirm the item and label match your event requirements.",
            "Escalate uncertain equipment to a qualified inspector rather than guessing.",
        ],
    },
    {
        "id": "trackside-inspection",
        "title": "Trackside Inspection Basics",
        "minutes": 8,
        "level": "inspector",
        "summary": "Use a consistent mobile checklist and leave an auditable inspection note.",
        "checks": [
            "Confirm the participant and equipment record.",
            "Record each checklist result before choosing an outcome.",
            "Use attention/fail when the evidence is incomplete or a condition needs resolution.",
        ],
    },
    {
        "id": "recertification-planning",
        "title": "Recertification Planning",
        "minutes": 6,
        "level": "owner",
        "summary": "Track certification and inspection dates without treating planning reminders as official validity decisions.",
        "checks": [
            "Keep certification and inspection dates with the gear record.",
            "Follow the official specification/manufacturer process for recertification intervals.",
            "Treat timeline reminders as planning aids, not proof of compliance.",
        ],
    },
]


def _clean_text(value, max_len=255):
    return str(value or "").strip()[:max_len]


def _parse_iso_date(value):
    value = _clean_text(value, 20)
    if not value:
        return ""
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD") from exc
    return value


def _tokenize(value):
    return [token for token in re.findall(r"[a-z0-9.]+", (value or "").lower()) if len(token) > 1]


def _qr_secret():
    secret = os.getenv("SFI_QR_SECRET", "").strip()
    if len(secret) < 24:
        return None
    return secret


def _can_review():
    return user_has_permission(g.current_user, "can_approve_gear")


def _gear_for_user(gear_id, allow_reviewer=False):
    gear = UserGear.query.get(gear_id)
    if not gear:
        return None, ({"error": "gear not found"}, 404)
    if gear.user_id != g.current_user.id and not (allow_reviewer and _can_review()):
        return None, ({"error": "forbidden"}, 403)
    return gear, None


def _compass_matches(query, category="", limit=8):
    terms = _tokenize(query)
    if not terms and not category:
        return []

    filters = []
    for term in terms:
        like = f"%{term}%"
        filters.extend([
            SfiSpec.product_name.ilike(like),
            SfiSpec.spec_number.ilike(like),
            SfiSpec.category.ilike(like),
            SfiSpec.subcategory.ilike(like),
        ])

    q = SfiSpec.query
    if filters:
        q = q.filter(or_(*filters))
    if category:
        q = q.filter(SfiSpec.category.ilike(f"%{category}%"))

    candidates = q.limit(200).all()
    query_lower = (query or "").lower().strip()
    scored = []
    for spec in candidates:
        product = (spec.product_name or "").lower()
        spec_number = (spec.spec_number or "").lower()
        cat = (spec.category or "").lower()
        subcat = (spec.subcategory or "").lower()
        score = 0
        reasons = []

        if query_lower and query_lower == spec_number:
            score += 18
            reasons.append("exact specification number")
        if query_lower and query_lower in product:
            score += 8
            reasons.append("product-name match")
        for term in terms:
            if term in spec_number:
                score += 6
            if term in product:
                score += 4
            if term in cat:
                score += 3
            if term in subcat:
                score += 2
        if category and category.lower() in cat:
            score += 4
            reasons.append("requested category")

        if score:
            scored.append((score, spec, reasons or ["related keywords"]))

    scored.sort(key=lambda row: (-row[0], (row[1].spec_number or ""), (row[1].product_name or "")))
    output = []
    for score, spec, reasons in scored[:limit]:
        item = spec.to_dict()
        item["matchScore"] = score
        item["matchReasons"] = reasons
        output.append(item)
    return output


def _timeline_for_gear(gear):
    events = []
    if gear.created_at:
        events.append({
            "type": "gear_added",
            "date": gear.created_at.date().isoformat(),
            "title": "Gear added",
            "detail": gear.name,
            "status": gear.status,
        })
    if gear.cert_date:
        events.append({
            "type": "certification",
            "date": gear.cert_date,
            "title": "Certification date",
            "detail": gear.spec or "SFI specification not recorded",
            "status": "recorded",
        })

    inspections = (TracksideInspection.query
                   .filter_by(gear_id=gear.id)
                   .order_by(TracksideInspection.created_at.asc())
                   .all())
    for inspection in inspections:
        events.append({
            "type": "inspection",
            "date": inspection.created_at.date().isoformat(),
            "title": f"Trackside inspection: {inspection.outcome}",
            "detail": inspection.notes or "Checklist recorded",
            "status": inspection.outcome,
            "inspectionId": inspection.id,
        })
        if inspection.next_due_on:
            events.append({
                "type": "planning_reminder",
                "date": inspection.next_due_on,
                "title": "Inspector-entered follow-up date",
                "detail": "Planning reminder only — verify official SFI/manufacturer requirements.",
                "status": "planned",
                "inspectionId": inspection.id,
            })

    events.sort(key=lambda event: event.get("date") or "")
    return events


class _Compass(Resource):
    def post(self):
        body = request.get_json(silent=True) or {}
        query = _clean_text(body.get("query"), 300)
        category = _clean_text(body.get("category"), 120)
        try:
            limit = max(1, min(int(body.get("limit", 8)), MAX_COMPASS_RESULTS))
        except (TypeError, ValueError):
            return {"error": "limit must be a number"}, 400
        if not query and not category:
            return {"error": "query or category is required"}, 400
        matches = _compass_matches(query, category, limit)
        return jsonify({
            "query": query,
            "category": category,
            "count": len(matches),
            "matches": matches,
            "disclaimer": "Use these matches to find likely specifications; confirm applicability with the official SFI specification and event rules.",
        })


class _ParticipationIssue(Resource):
    @token_required()
    def post(self):
        secret = _qr_secret()
        if not secret:
            return {"error": "SFI_QR_SECRET is not configured securely"}, 503
        body = request.get_json(silent=True) or {}
        event = _clean_text(body.get("event"), 160)
        if not event:
            return {"error": "event is required"}, 400
        gear_ids = body.get("gearIds") or []
        if not isinstance(gear_ids, list) or not gear_ids:
            return {"error": "gearIds must be a non-empty list"}, 400
        try:
            gear_ids = sorted({int(value) for value in gear_ids})
            hours = max(1, min(int(body.get("validHours", 8)), MAX_QR_HOURS))
        except (TypeError, ValueError):
            return {"error": "gearIds and validHours must be numeric"}, 400

        owned = UserGear.query.filter(
            UserGear.id.in_(gear_ids),
            UserGear.user_id == g.current_user.id,
        ).all()
        if len(owned) != len(gear_ids):
            return {"error": "all selected gear must belong to the current user"}, 403

        now = datetime.now(timezone.utc)
        payload = {
            "iss": "sfi-participation-checker",
            "sub": str(g.current_user.id),
            "event": event,
            "gear_ids": gear_ids,
            "nonce": secrets.token_urlsafe(10),
            "iat": now,
            "exp": now + timedelta(hours=hours),
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
        return jsonify({
            "token": token,
            "event": event,
            "gearIds": gear_ids,
            "expiresAt": (now + timedelta(hours=hours)).isoformat(),
        })


class _ParticipationVerify(Resource):
    def post(self):
        secret = _qr_secret()
        if not secret:
            return {"error": "SFI_QR_SECRET is not configured securely"}, 503
        body = request.get_json(silent=True) or {}
        token = _clean_text(body.get("token"), 4096)
        if not token:
            return {"valid": False, "error": "token is required"}, 400
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                issuer="sfi-participation-checker",
            )
        except jwt.ExpiredSignatureError:
            return {"valid": False, "error": "credential expired"}, 401
        except jwt.InvalidTokenError:
            return {"valid": False, "error": "invalid credential"}, 401

        gear_ids = payload.get("gear_ids") or []
        gear = UserGear.query.filter(UserGear.id.in_(gear_ids)).all() if gear_ids else []
        return jsonify({
            "valid": True,
            "participantId": int(payload["sub"]),
            "event": payload.get("event"),
            "gear": [item.to_dict() for item in gear],
            "expiresAt": datetime.fromtimestamp(payload["exp"], tz=timezone.utc).isoformat(),
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "note": "A valid QR signature confirms that the credential was issued by this system; current gear status is shown separately and must still be evaluated against event requirements.",
        })


class _Inspections(Resource):
    @token_required()
    def get(self):
        gear_id = request.args.get("gear_id", type=int)
        if gear_id:
            gear, error = _gear_for_user(gear_id, allow_reviewer=True)
            if error:
                return error
            rows = TracksideInspection.query.filter_by(gear_id=gear.id).order_by(TracksideInspection.created_at.desc()).all()
        elif _can_review() and request.args.get("scope") == "all":
            rows = TracksideInspection.query.order_by(TracksideInspection.created_at.desc()).limit(250).all()
        else:
            owned_ids = [item.id for item in UserGear.get_by_user(g.current_user.id)]
            rows = (TracksideInspection.query
                    .filter(TracksideInspection.gear_id.in_(owned_ids))
                    .order_by(TracksideInspection.created_at.desc())
                    .all()) if owned_ids else []
        return jsonify([row.to_dict() for row in rows])

    @token_required()
    def post(self):
        if not _can_review():
            return {"error": "inspector permission required"}, 403
        body = request.get_json(silent=True) or {}
        try:
            gear_id = int(body.get("gearId"))
        except (TypeError, ValueError):
            return {"error": "gearId is required"}, 400
        gear = UserGear.query.get(gear_id)
        if not gear:
            return {"error": "gear not found"}, 404
        outcome = _clean_text(body.get("outcome"), 20).lower()
        if outcome not in INSPECTION_OUTCOMES:
            return {"error": f"outcome must be one of {INSPECTION_OUTCOMES}"}, 400
        checklist = body.get("checklist") or {}
        if not isinstance(checklist, dict):
            return {"error": "checklist must be an object"}, 400
        normalized_checklist = {str(key)[:80]: bool(value) for key, value in list(checklist.items())[:30]}
        try:
            next_due_on = _parse_iso_date(body.get("nextDueOn"))
        except ValueError as exc:
            return {"error": str(exc)}, 400
        row = TracksideInspection(
            gear_id=gear.id,
            inspector_id=g.current_user.id,
            outcome=outcome,
            checklist_json=json.dumps(normalized_checklist, sort_keys=True),
            notes=_clean_text(body.get("notes"), 1000),
            next_due_on=next_due_on,
        )
        db.session.add(row)
        db.session.commit()
        return row.to_dict(), 201


class _Timeline(Resource):
    @token_required()
    def get(self):
        gear_id = request.args.get("gear_id", type=int)
        if gear_id:
            gear, error = _gear_for_user(gear_id, allow_reviewer=True)
            if error:
                return error
            gear_rows = [gear]
        else:
            gear_rows = UserGear.get_by_user(g.current_user.id)
        return jsonify({
            "gear": [
                {
                    "gear": item.to_dict(),
                    "events": _timeline_for_gear(item),
                }
                for item in gear_rows
            ],
            "disclaimer": "Timeline dates are records and planning reminders, not a determination of SFI compliance or certification validity.",
        })


class _ManufacturerReviews(Resource):
    @token_required()
    def get(self):
        if _can_review() and request.args.get("scope") == "all":
            q = ManufacturerReview.query
        else:
            q = ManufacturerReview.query.filter_by(submitted_by=g.current_user.id)
        status = _clean_text(request.args.get("status"), 30).lower()
        if status:
            if status not in REVIEW_STATUSES:
                return {"error": f"status must be one of {REVIEW_STATUSES}"}, 400
            q = q.filter_by(status=status)
        rows = q.order_by(ManufacturerReview.created_at.desc()).limit(250).all()
        return jsonify([row.to_dict() for row in rows])

    @token_required()
    def post(self):
        body = request.get_json(silent=True) or {}
        manufacturer = _clean_text(body.get("manufacturerName"), 255)
        product = _clean_text(body.get("productName"), 255)
        spec_number = _clean_text(body.get("specNumber"), 80)
        if not manufacturer or not product or not spec_number:
            return {"error": "manufacturerName, productName, and specNumber are required"}, 400
        evidence_url = _clean_text(body.get("evidenceUrl"), 1000)
        if evidence_url and not re.match(r"^https?://", evidence_url, flags=re.I):
            return {"error": "evidenceUrl must start with http:// or https://"}, 400
        row = ManufacturerReview(
            submitted_by=g.current_user.id,
            manufacturer_name=manufacturer,
            product_name=product,
            spec_number=spec_number,
            evidence_url=evidence_url,
            submission_note=_clean_text(body.get("submissionNote"), 2000),
        )
        db.session.add(row)
        db.session.commit()
        return row.to_dict(), 201


class _ManufacturerReviewItem(Resource):
    @token_required()
    def patch(self, review_id):
        if not _can_review():
            return {"error": "reviewer permission required"}, 403
        row = ManufacturerReview.query.get(review_id)
        if not row:
            return {"error": "review not found"}, 404
        body = request.get_json(silent=True) or {}
        status = _clean_text(body.get("status"), 30).lower()
        if status not in REVIEW_STATUSES:
            return {"error": f"status must be one of {REVIEW_STATUSES}"}, 400
        row.status = status
        row.reviewer_id = g.current_user.id
        row.review_note = _clean_text(body.get("reviewNote"), 2000)
        row.reviewed_at = datetime.utcnow()
        db.session.commit()
        return jsonify(row.to_dict())


class _LearningModules(Resource):
    def get(self):
        return jsonify(LEARNING_MODULES)


class _LearningProgress(Resource):
    @token_required()
    def get(self):
        rows = SafetyLearningProgress.query.filter_by(user_id=g.current_user.id).all()
        return jsonify([row.to_dict() for row in rows])

    @token_required()
    def post(self):
        body = request.get_json(silent=True) or {}
        module_id = _clean_text(body.get("moduleId"), 80)
        module_ids = {module["id"] for module in LEARNING_MODULES}
        if module_id not in module_ids:
            return {"error": "unknown moduleId"}, 404
        score = body.get("score")
        if score is not None:
            try:
                score = max(0, min(int(score), 100))
            except (TypeError, ValueError):
                return {"error": "score must be between 0 and 100"}, 400
        completed = bool(body.get("completed", True))
        row = SafetyLearningProgress.query.filter_by(
            user_id=g.current_user.id,
            module_id=module_id,
        ).first()
        if not row:
            row = SafetyLearningProgress(user_id=g.current_user.id, module_id=module_id)
            db.session.add(row)
        row.completed = completed
        row.score = score
        row.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify(row.to_dict())


api.add_resource(_Compass, "/compass")
api.add_resource(_ParticipationIssue, "/participation/issue")
api.add_resource(_ParticipationVerify, "/participation/verify")
api.add_resource(_Inspections, "/inspections")
api.add_resource(_Timeline, "/timeline")
api.add_resource(_ManufacturerReviews, "/manufacturer-reviews")
api.add_resource(_ManufacturerReviewItem, "/manufacturer-reviews/<int:review_id>")
api.add_resource(_LearningModules, "/learning/modules")
api.add_resource(_LearningProgress, "/learning/progress")
