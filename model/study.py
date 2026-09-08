from sqlalchemy import Column, String, Boolean, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import json

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from __init__ import db
from model.user import User

class Study(db.Model):
    __tablename__ = 'study'

    # Define the study tracker table schema
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    topic = Column(String(255), nullable=False)
    subtopic = Column(String(255), nullable=False)
    studied = Column(Boolean, default=False)
    timestamp = Column(String(50), nullable=False)
    
    # Constructor
    def __init__(self, user_id, topic, subtopic, studied, timestamp):
        self.user_id = user_id
        self.topic = topic
        self.subtopic = subtopic
        self.studied = studied
        self.timestamp = timestamp

    # JSON conversion method for API responses
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "topic": self.topic,
            "subtopic": self.subtopic,
            "studied": self.studied,
            "timestamp": self.timestamp
        }
    
    # Create method - returns the created study record
    def create(self):
        try:
            db.session.add(self)
            db.session.commit()
            return self
        except Exception as e:
            db.session.rollback()
            return None
    
    # Update method for existing study records
    def update(self, data):
        try:
            for key, value in data.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            db.session.commit()
            return self
        except Exception as e:
            db.session.rollback()
            return None
    
    # Delete method
    def delete(self):
        try:
            db.session.delete(self)
            db.session.commit()
            return True
        except:
            db.session.rollback()
            return False
    
    # String representation
    def __repr__(self):
        return f'Study: {self.topic} - {self.subtopic}'


# Function to initialize sample study data
def initStudies():
    with db.session.no_autoflush:
        # Only create sample data if no records exist
        if not db.session.query(Study).first():
            # Create sample study records
            studies = [
                Study(
                    user_id=1,
                    topic="Big Idea 1: Creative Development",
                    subtopic="1.1 Collaboration",
                    studied=True,
                    timestamp=datetime.now().isoformat()
                ),
                Study(
                    user_id=1,
                    topic="Big Idea 2: Data",
                    subtopic="2.1 Binary Numbers",
                    studied=True,
                    timestamp=datetime.now().isoformat()
                ),
                Study(
                    user_id=2,
                    topic="Big Idea 3: Algorithms and Programming",
                    subtopic="3.1 Variables and Assignments",
                    studied=True,
                    timestamp=datetime.now().isoformat()
                )
            ]
            
            # Add all study records to database
            for study in studies:
                try:
                    study.create()
                except Exception as e:
                    print(f"Error creating study record: {e}")
                    db.session.rollback()
