"""User Gear API — per-user racing equipment tracking + moderation.

Endpoints:
    GET    /api/sfi/gear                — current user's gear
    POST   /api/sfi/gear                — record a gear item (status=pending unless auto-approved)
    DELETE /api/sfi/gear/<id>           — remove a gear item (owner or admin)
    GET    /api/sfi/gear/all            — all gear (requires can_view_all_gear)
    GET    /api/sfi/gear/pending        — all pending gear (requires can_approve_gear)
    PATCH  /api/sfi/gear/<id>/status    — approve/reject (requires can_approve_gear)
"""

from datetime import date

from flask import Blueprint, g, jsonify, request
from flask_restful import Api, Resource

from api.authorize import token_required
from model.group import user_has_permission, user_is_admin
from model.user import User
from model.user_gear import ALLOWED_STATUSES, UserGear


user_gear_api = Blueprint('user_gear_api', __name__, url_prefix='/api/sfi')
api = Api(user_gear_api)

MAX_COLLECTION_ROWS = 500
ALLOWED_SOURCES = ('manual', 'ai-detection', 'search', 'compass')


def _clean(value, max_len):
    return str(value or '').strip()[:max_len]


def _normalize_submission(body):
    name = _clean(body.get('name'), 255)
    if not name:
        return None, {'error': 'name is required'}, 400

    cert_date = _clean(body.get('certDate'), 20)
    if cert_date:
        try:
            date.fromisoformat(cert_date)
        except ValueError:
            return None, {'error': 'certDate must use YYYY-MM-DD'}, 400

    source = _clean(body.get('source') or 'manual', 40).lower()
    if source not in ALLOWED_SOURCES:
        return None, {'error': f'source must be one of {ALLOWED_SOURCES}'}, 400

    return {
        'name': name,
        'spec': _clean(body.get('spec') or 'Unknown', 50) or 'Unknown',
        'certDate': cert_date,
        'category': _clean(body.get('category'), 100),
        'productName': _clean(body.get('productName'), 255),
        'source': source,
    }, None, None


def _dict_with_owner(gear):
    owner = User.query.get(gear.user_id)
    return gear.to_dict(owner=owner)


def _bounded(items):
    return items[:MAX_COLLECTION_ROWS]


class UserGearAPI:

    class _GearCollection(Resource):
        @token_required()
        def get(self):
            items = _bounded(UserGear.get_by_user(g.current_user.id))
            return jsonify([item.to_dict() for item in items])

        @token_required()
        def post(self):
            body = request.get_json(silent=True) or {}
            normalized, error, status = _normalize_submission(body)
            if error:
                return error, status

            auto_approve = user_has_permission(g.current_user, 'can_approve_gear')
            gear = UserGear.create(
                user_id=g.current_user.id,
                data=normalized,
                auto_approve=auto_approve,
                reviewer_id=g.current_user.id if auto_approve else None,
            )
            return gear.to_dict(), 201

    class _GearItem(Resource):
        @token_required()
        def delete(self, gear_id):
            gear = UserGear.query.get(gear_id)
            if not gear:
                return {'error': 'not found'}, 404
            is_owner = gear.user_id == g.current_user.id
            is_admin = user_is_admin(g.current_user)
            if not (is_owner or is_admin):
                return {'error': 'forbidden'}, 403
            gear.delete()
            return jsonify({'message': 'deleted'})

    class _GearAll(Resource):
        @token_required()
        def get(self):
            if not user_has_permission(g.current_user, 'can_view_all_gear'):
                return {'error': 'forbidden'}, 403
            items = _bounded(UserGear.get_all())
            return jsonify([_dict_with_owner(item) for item in items])

    class _GearPending(Resource):
        @token_required()
        def get(self):
            if not user_has_permission(g.current_user, 'can_approve_gear'):
                return {'error': 'forbidden'}, 403
            items = _bounded(UserGear.get_pending())
            return jsonify([_dict_with_owner(item) for item in items])

    class _GearStatus(Resource):
        @token_required()
        def patch(self, gear_id):
            if not user_has_permission(g.current_user, 'can_approve_gear'):
                return {'error': 'forbidden'}, 403
            gear = UserGear.query.get(gear_id)
            if not gear:
                return {'error': 'not found'}, 404

            body = request.get_json(silent=True) or {}
            new_status = _clean(body.get('status'), 20).lower()
            if new_status not in ALLOWED_STATUSES:
                return {'error': f'status must be one of {ALLOWED_STATUSES}'}, 400

            gear.set_status(new_status, g.current_user.id, _clean(body.get('note'), 500))
            return jsonify(_dict_with_owner(gear))

    api.add_resource(_GearCollection, '/gear')
    api.add_resource(_GearItem, '/gear/<int:gear_id>')
    api.add_resource(_GearAll, '/gear/all')
    api.add_resource(_GearPending, '/gear/pending')
    api.add_resource(_GearStatus, '/gear/<int:gear_id>/status')
