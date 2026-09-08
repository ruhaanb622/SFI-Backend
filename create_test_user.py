#!/usr/bin/env python3
"""
Create a test user for logging in
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from __init__ import app, db
from model.user import User

def create_test_user():
    with app.app_context():
        # Check if user already exists
        existing_user = User.query.filter_by(_uid='testuser').first()
        if existing_user:
            print("❌ Test user 'testuser' already exists!")
            print(f"   Name: {existing_user.name}")
            print(f"   UID: {existing_user.uid}")
            print(f"   Password: 123456")
            return
        
        # Create a new test user
        print("Creating test user...")
        user = User(
            name="Test User",
            uid="testuser",
            password="123456",  # Simple password for testing
            role="Student"
        )
        
        # Save to database
        user.create()
        
        print("\n" + "="*50)
        print("✅ TEST USER CREATED SUCCESSFULLY!")
        print("="*50)
        print(f"Username: testuser")
        print(f"Password: 123456")
        print(f"Name: Test User")
        print(f"Role: Student")
        print("="*50)
        print("\n📌 Use these credentials to log in to your frontend!")

if __name__ == '__main__':
    create_test_user()

