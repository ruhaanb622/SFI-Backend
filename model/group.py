"""
SFI Group model — coarse permission groups for the SFI prototype.

A Group is a named bucket of permissions that can contain many users.
One special group — "administrators" — has every permission turned on and
owns the moderation / approval flow for user-submitted gear.
"""

from __init__ import db
from datetime import datetime
from sqlalchemy.orm import relationship


# Many-to-many association table: users ↔ groups
sfi_user_groups = db.Table(
    'sfi_user_groups',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('sfi_groups.id'), primary_key=True),
)


class SfiGroup(db.Model):
    __tablename__ = 'sfi_groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255), default='')

    can_approve_gear = db.Column(db.Boolean, default=False, nullable=False)
    can_view_all_gear = db.Column(db.Boolean, default=False, nullable=False)
    can_manage_groups = db.Column(db.Boolean, default=False, nullable=False)
    can_manage_users = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = relationship(
        'User',
        secondary=sfi_user_groups,
        backref=db.backref('sfi_groups', lazy='dynamic'),
        lazy='dynamic',
    )

    def to_dict(self, include_members=False):
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'permissions': {
                'can_approve_gear': self.can_approve_gear,
                'can_view_all_gear': self.can_view_all_gear,
                'can_manage_groups': self.can_manage_groups,
                'can_manage_users': self.can_manage_users,
            },
            'memberCount': self.members.count(),
        }
        if include_members:
            data['members'] = [
                {'id': u.id, 'uid': u._uid, 'name': u._name}
                for u in self.members.all()
            ]
        return data

    @staticmethod
    def by_name(name):
        return SfiGroup.query.filter_by(name=name).first()


def user_has_permission(user, perm_name):
    """Return True if any group the user belongs to has the given permission flag set."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    for g in user.sfi_groups.all():
        if getattr(g, perm_name, False):
            return True
    return False


def user_is_admin(user):
    """Convenience: administrators group = all four flags on. Check membership in 'administrators'."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    return any(g.name == 'administrators' for g in user.sfi_groups.all())


def initSfiGroups():
    """Seed the baseline groups. Idempotent — safe to run on every boot."""
    from model.user import User

    defaults = [
        dict(
            name='administrators',
            description='Full moderation + user/group management. Auto-approves gear.',
            can_approve_gear=True,
            can_view_all_gear=True,
            can_manage_groups=True,
            can_manage_users=True,
        ),
        dict(
            name='members',
            description='Default group for logged-in users. Can record gear; submissions need approval.',
            can_approve_gear=False,
            can_view_all_gear=False,
            can_manage_groups=False,
            can_manage_users=False,
        ),
    ]

    for d in defaults:
        g = SfiGroup.by_name(d['name'])
        if g is None:
            g = SfiGroup(**d)
            db.session.add(g)
    db.session.commit()

    admin_group = SfiGroup.by_name('administrators')
    members_group = SfiGroup.by_name('members')

    admin_user = User.query.filter_by(_uid='admin').first()
    if admin_user is not None and admin_group is not None:
        if admin_user not in admin_group.members.all():
            admin_group.members.append(admin_user)

    if members_group is not None:
        for u in User.query.all():
            if u._uid == 'admin':
                continue
            if u not in members_group.members.all() and u not in admin_group.members.all():
                members_group.members.append(u)

    db.session.commit()
