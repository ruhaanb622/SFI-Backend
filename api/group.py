"""
SFI Group API — CRUD for permission groups + membership.

Endpoints:
    GET    /api/sfi/groups                         — list all groups (requires can_manage_groups OR can_view_all_gear)
    POST   /api/sfi/groups                         — create a group (requires can_manage_groups)
    GET    /api/sfi/groups/<id>                    — detail incl. members (same gate as list)
    PATCH  /api/sfi/groups/<id>                    — rename / change permissions (requires can_manage_groups)
    DELETE /api/sfi/groups/<id>                    — delete (requires can_manage_groups; can't delete 'administrators')
    POST   /api/sfi/groups/<id>/members            — add member {userId or uid} (requires can_manage_users)
    DELETE /api/sfi/groups/<id>/members/<user_id>  — remove member (requires can_manage_users)
    GET    /api/sfi/me                             — current user + their permission summary
    GET    /api/sfi/users                          — list users (requires can_manage_users)
"""

from flask import Blueprint, request, jsonify, g
from flask_restful import Api, Resource

from api.authorize import token_required
from model.user import User
from model.group import SfiGroup, user_has_permission, user_is_admin

group_api = Blueprint('sfi_group_api', __name__, url_prefix='/api/sfi')
api = Api(group_api)


PERM_FIELDS = (
    'can_approve_gear',
    'can_view_all_gear',
    'can_manage_groups',
    'can_manage_users',
)


def _apply_perms(group, perms):
    if not isinstance(perms, dict):
        return
    for key in PERM_FIELDS:
        if key in perms:
            setattr(group, key, bool(perms[key]))


def _require_any(user, *perms):
    return any(user_has_permission(user, p) for p in perms)


class GroupAPI:

    class _GroupCollection(Resource):
        @token_required()
        def get(self):
            if not _require_any(g.current_user, 'can_manage_groups', 'can_view_all_gear', 'can_manage_users'):
                return {'error': 'forbidden'}, 403
            groups = SfiGroup.query.order_by(SfiGroup.name).all()
            return jsonify([grp.to_dict(include_members=False) for grp in groups])

        @token_required()
        def post(self):
            if not user_has_permission(g.current_user, 'can_manage_groups'):
                return {'error': 'forbidden'}, 403
            body = request.get_json(silent=True) or {}
            name = (body.get('name') or '').strip()
            if not name:
                return {'error': 'name is required'}, 400
            if SfiGroup.by_name(name) is not None:
                return {'error': 'a group with that name already exists'}, 409
            grp = SfiGroup(
                name=name,
                description=(body.get('description') or '').strip()[:255],
            )
            _apply_perms(grp, body.get('permissions') or {})
            from __init__ import db
            db.session.add(grp)
            db.session.commit()
            return jsonify(grp.to_dict(include_members=True))

    class _GroupItem(Resource):
        @token_required()
        def get(self, group_id):
            if not _require_any(g.current_user, 'can_manage_groups', 'can_view_all_gear', 'can_manage_users'):
                return {'error': 'forbidden'}, 403
            grp = SfiGroup.query.get(group_id)
            if not grp:
                return {'error': 'not found'}, 404
            return jsonify(grp.to_dict(include_members=True))

        @token_required()
        def patch(self, group_id):
            if not user_has_permission(g.current_user, 'can_manage_groups'):
                return {'error': 'forbidden'}, 403
            grp = SfiGroup.query.get(group_id)
            if not grp:
                return {'error': 'not found'}, 404
            body = request.get_json(silent=True) or {}
            if 'name' in body:
                new_name = (body['name'] or '').strip()
                if not new_name:
                    return {'error': 'name cannot be empty'}, 400
                existing = SfiGroup.by_name(new_name)
                if existing and existing.id != grp.id:
                    return {'error': 'a group with that name already exists'}, 409
                if grp.name == 'administrators' and new_name != 'administrators':
                    return {'error': "cannot rename the 'administrators' group"}, 400
                grp.name = new_name
            if 'description' in body:
                grp.description = (body['description'] or '')[:255]
            _apply_perms(grp, body.get('permissions') or {})
            from __init__ import db
            db.session.commit()
            return jsonify(grp.to_dict(include_members=True))

        @token_required()
        def delete(self, group_id):
            if not user_has_permission(g.current_user, 'can_manage_groups'):
                return {'error': 'forbidden'}, 403
            grp = SfiGroup.query.get(group_id)
            if not grp:
                return {'error': 'not found'}, 404
            if grp.name == 'administrators':
                return {'error': "cannot delete the 'administrators' group"}, 400
            from __init__ import db
            db.session.delete(grp)
            db.session.commit()
            return jsonify({'message': 'deleted'})

    class _GroupMembers(Resource):
        @token_required()
        def post(self, group_id):
            if not user_has_permission(g.current_user, 'can_manage_users'):
                return {'error': 'forbidden'}, 403
            grp = SfiGroup.query.get(group_id)
            if not grp:
                return {'error': 'not found'}, 404
            body = request.get_json(silent=True) or {}
            user = None
            if body.get('userId'):
                user = User.query.get(body['userId'])
            elif body.get('uid'):
                user = User.query.filter_by(_uid=body['uid']).first()
            if user is None:
                return {'error': 'user not found'}, 404
            if user in grp.members.all():
                return jsonify(grp.to_dict(include_members=True))
            grp.members.append(user)
            from __init__ import db
            db.session.commit()
            return jsonify(grp.to_dict(include_members=True))

    class _GroupMember(Resource):
        @token_required()
        def delete(self, group_id, user_id):
            if not user_has_permission(g.current_user, 'can_manage_users'):
                return {'error': 'forbidden'}, 403
            grp = SfiGroup.query.get(group_id)
            if not grp:
                return {'error': 'not found'}, 404
            user = User.query.get(user_id)
            if user is None:
                return {'error': 'user not found'}, 404
            if grp.name == 'administrators' and user._uid == 'admin':
                return {'error': "cannot remove 'admin' from the administrators group"}, 400
            if user in grp.members.all():
                grp.members.remove(user)
                from __init__ import db
                db.session.commit()
            return jsonify(grp.to_dict(include_members=True))

    class _Me(Resource):
        @token_required()
        def get(self):
            u = g.current_user
            groups = list(u.sfi_groups.all())
            perms = {
                p: any(getattr(grp, p) for grp in groups) for p in PERM_FIELDS
            }
            return jsonify({
                'id': u.id,
                'uid': u._uid,
                'name': u._name,
                'role': getattr(u, '_role', 'User'),
                'isAdmin': user_is_admin(u),
                'groups': [{'id': grp.id, 'name': grp.name} for grp in groups],
                'permissions': perms,
            })

    class _Users(Resource):
        @token_required()
        def get(self):
            if not user_has_permission(g.current_user, 'can_manage_users'):
                return {'error': 'forbidden'}, 403
            users = User.query.order_by(User._uid).all()
            return jsonify([
                {
                    'id': u.id,
                    'uid': u._uid,
                    'name': u._name,
                    'role': getattr(u, '_role', 'User'),
                    'groups': [{'id': grp.id, 'name': grp.name} for grp in u.sfi_groups.all()],
                }
                for u in users
            ])

    api.add_resource(_GroupCollection, '/groups')
    api.add_resource(_GroupItem, '/groups/<int:group_id>')
    api.add_resource(_GroupMembers, '/groups/<int:group_id>/members')
    api.add_resource(_GroupMember, '/groups/<int:group_id>/members/<int:user_id>')
    api.add_resource(_Me, '/me')
    api.add_resource(_Users, '/users')
