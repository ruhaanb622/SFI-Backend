"""
UserGear model — stores per-user racing safety equipment with SFI spec tracking.

Submissions start in status='pending' by default. Administrators (or any
member of a group with `can_approve_gear`) can approve or reject them.
"""

from __init__ import db
from datetime import datetime


STATUS_PENDING = 'pending'
STATUS_APPROVED = 'approved'
STATUS_REJECTED = 'rejected'
ALLOWED_STATUSES = (STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED)


class UserGear(db.Model):
    __tablename__ = 'user_gear'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    spec = db.Column(db.String(50), default='Unknown')
    cert_date = db.Column(db.String(20), default='')       # YYYY-MM-DD or empty
    category = db.Column(db.String(100), default='')
    product_name = db.Column(db.String(255), default='')
    source = db.Column(db.String(40), default='manual')    # 'manual' | 'ai-detection' | 'search'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    status = db.Column(db.String(20), default=STATUS_PENDING, nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_note = db.Column(db.String(500), default='')

    def to_dict(self, owner=None):
        data = {
            'id': self.id,
            'name': self.name,
            'spec': self.spec,
            'certDate': self.cert_date,
            'category': self.category,
            'productName': self.product_name,
            'source': self.source,
            'status': self.status,
            'reviewerId': self.reviewer_id,
            'reviewedAt': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'reviewNote': self.review_note,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'userId': self.user_id,
        }
        if owner is not None:
            data['owner'] = {'id': owner.id, 'uid': owner._uid, 'name': owner._name}
        return data

    @staticmethod
    def create(user_id, data, auto_approve=False, reviewer_id=None):
        gear = UserGear(
            user_id=user_id,
            name=(data.get('name') or '').strip(),
            spec=(data.get('spec') or 'Unknown').strip(),
            cert_date=data.get('certDate') or '',
            category=data.get('category') or '',
            product_name=data.get('productName') or '',
            source=(data.get('source') or 'manual').strip()[:40],
        )
        if auto_approve:
            gear.status = STATUS_APPROVED
            gear.reviewer_id = reviewer_id or user_id
            gear.reviewed_at = datetime.utcnow()
        db.session.add(gear)
        db.session.commit()
        return gear

    @staticmethod
    def get_by_user(user_id):
        return (UserGear.query
                .filter_by(user_id=user_id)
                .order_by(UserGear.created_at.desc())
                .all())

    @staticmethod
    def get_all():
        return UserGear.query.order_by(UserGear.created_at.desc()).all()

    @staticmethod
    def get_pending():
        return (UserGear.query
                .filter_by(status=STATUS_PENDING)
                .order_by(UserGear.created_at.asc())
                .all())

    def set_status(self, new_status, reviewer_id, note=''):
        if new_status not in ALLOWED_STATUSES:
            raise ValueError(f'invalid status: {new_status}')
        self.status = new_status
        self.reviewer_id = reviewer_id
        self.reviewed_at = datetime.utcnow()
        self.review_note = (note or '')[:500]
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()
