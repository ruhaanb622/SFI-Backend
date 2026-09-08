from __init__ import db
from datetime import datetime

class Feedback(db.Model):
    __tablename__ = 'feedbacks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(64), default="Other")
    github_username = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    github_issue_url = db.Column(db.String(512), nullable=True)
    

    def __init__(self, title, body, type="Other", github_username=None):
        self.title = title
        self.body = body
        self.type = type
        self.github_username = github_username


    def create(self):
        db.session.add(self)
        db.session.commit()
        return self

    def read(self):
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "type": self.type,
            "github_username": self.github_username,
            "created_at": self.created_at,
            "github_issue_url": self.github_issue_url
        }
