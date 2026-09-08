"""
User Gear API — per-user racing equipment tracking + moderation.

Endpoints:
    GET    /api/sfi/gear                — current user's gear
    POST   /api/sfi/gear                — record a gear item (status=pending unless auto-approved)
    DELETE /api/sfi/gear/<id>           — remove a gear item (owner or admin)
    GET    /api/sfi/gear/all            — all gear (requires can_view_all_gear)
    GET    /api/sfi/gear/pending        — all pending gear (requires can_approve_gear)
    PATCH  /api/sfi/gear/<id>/status    — approve/reject (requires can_approve_gear)
"""

from flask import Blueprint, request, jsonify, g
from flask_restful import Api, Resource

from api.authorize import token_required
from model.user import User
from model.user_gear import UserGear, ALLOWED_STATUSES, STATUS_APPROVED, STATUS_REJECTED
from model.group import user_has_permission, user_is_admin

user_gear_api = Blueprint('user_gear_api', __name__, url_prefix='/api/sfi')
api = Api(user_gear_api)


def _dict_with_owner(gear):
    owner = User.query.get(gear.user_id)
    return gear.to_dict(owner=owner)


class UserGearAPI:

    class _GearCollection(Resource):
        @token_required()
        def get(self):
            items = UserGear.get_by_user(g.current_user.id)
            return jsonify([item.to_dict() for item in items])

        @token_required()
        def post(self):
            body = request.get_json(silent=True) or {}
            if not (body.get('name') or '').strip():
                return {'error': 'name is required'}, 400

            auto_approve = user_has_permission(g.current_user, 'can_approve_gear')
            gear = UserGear.create(
                user_id=g.current_user.id,
                data=body,
                auto_approve=auto_approve,
                reviewer_id=g.current_user.id if auto_approve else None,
            )
            return jsonify(gear.to_dict())

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
            items = UserGear.get_all()
            return jsonify([_dict_with_owner(i) for i in items])

    class _GearPending(Resource):
        @token_required()
        def get(self):
            if not user_has_permission(g.current_user, 'can_approve_gear'):
                return {'error': 'forbidden'}, 403
            items = UserGear.get_pending()
            return jsonify([_dict_with_owner(i) for i in items])

    class _GearStatus(Resource):
        @token_required()
        def patch(self, gear_id):
            if not user_has_permission(g.current_user, 'can_approve_gear'):
                return {'error': 'forbidden'}, 403
            gear = UserGear.query.get(gear_id)
            if not gear:
                return {'error': 'not found'}, 404
            body = request.get_json(silent=True) or {}
            new_status = (body.get('status') or '').strip().lower()
            if new_status not in ALLOWED_STATUSES:
                return {'error': f'status must be one of {ALLOWED_STATUSES}'}, 400
            gear.set_status(new_status, g.current_user.id, body.get('note', ''))
            return jsonify(_dict_with_owner(gear))

    api.add_resource(_GearCollection, '/gear')
    api.add_resource(_GearItem, '/gear/<int:gear_id>')
    api.add_resource(_GearAll, '/gear/all')
    api.add_resource(_GearPending, '/gear/pending')
    api.add_resource(_GearStatus, '/gear/<int:gear_id>/status')
