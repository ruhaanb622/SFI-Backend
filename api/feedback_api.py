import os
import requests
from flask import Blueprint, request, jsonify, session 
from flask_restful import Api, Resource
from model.feedback import Feedback
from __init__ import app, db

feedback_api = Blueprint('feedback_api', __name__, url_prefix='/api/feedback')
api = Api(feedback_api)

GITHUB_REPO = "Open-Coding-Society/pages"  
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

class FeedbackAPI:
    class _Create(Resource):
        def post(self):
            data = request.get_json()
            title = data.get('title')
            body = data.get('body')
            github_username = data.get('uid', 'Anonymous')

            if not title or not body:
                return {"message": "Title and body are required."}, 400
            
            type = data.get('type', 'Other')  # default to 'Other' if not provided

            # Ensure type is a valid GitHub label
            valid_types = ['Bug', 'Feature Request', 'Inquiry', 'Other']
            label = type if type in valid_types else 'Other'
            author_note = f"_Submitted by @{github_username}_" if github_username != 'Anonymous' else "_Submitted by [Anonymous]_"

            feedback = Feedback(title, body, type, github_username).create()

            # Attempt to create GitHub issue
            headers = {
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github+json"
            }

            payload = {
                "title": f"[User Feedback] {title}",
                "body": f"{body}\n\n{author_note}",
                "labels": ["User Input", label]  # add both base label and type-specific
            }

            try:
                response = requests.post(
                    f"https://api.github.com/repos/Open-Coding-Society/pages/issues",
                    headers=headers,
                    json=payload
                )
                if response.status_code == 201:
                    github_url = response.json()["html_url"]
                    feedback.github_issue_url = github_url
                    db.session.commit()
                else:
                    print("GitHub Issue creation failed:", response.json())
            except Exception as e:
                print("GitHub API error:", str(e))

            return jsonify(feedback.read())

    class _ReadAll(Resource):
        def get(self):
            feedbacks = Feedback.query.order_by(Feedback.created_at.desc()).all()
            return jsonify([f.read() for f in feedbacks])
        
    class _UserFeedback(Resource):
        def get(self, uid):
            feedbacks = Feedback.query.filter_by(github_username=uid).order_by(Feedback.created_at.desc()).all()

            headers = {
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github+json"
            }

            result = []
            for fb in feedbacks:
                status = "Unknown"
                try:
                    if fb.github_issue_url:
                        # Extract issue number from the URL
                        parts = fb.github_issue_url.rstrip("/").split("/")
                        issue_number = parts[-1]

                        # Call GitHub API to get issue status
                        response = requests.get(
                            f"https://api.github.com/repos/{GITHUB_REPO}/issues/{issue_number}",
                            headers=headers
                        )
                        if response.status_code == 200:
                            issue_data = response.json()
                            status = issue_data.get("state", "Unknown").capitalize()  # Open or Closed
                        else:
                            print(f"GitHub issue fetch failed for issue {issue_number}: {response.status_code}")
                except Exception as e:
                    print(f"Error checking issue status: {e}")

                result.append({
                    "title": fb.title,
                    "created_at": fb.created_at.isoformat(),
                    "type": fb.type,
                    "github_issue_url": fb.github_issue_url,
                    "status": status
                })

            return jsonify(result)

api.add_resource(FeedbackAPI._Create, '/')
api.add_resource(FeedbackAPI._ReadAll, '/all')
api.add_resource(FeedbackAPI._UserFeedback, '/user/<string:uid>')
