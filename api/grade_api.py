from flask import Blueprint, request, jsonify, g
from flask_restful import Api, Resource
from api.authorize import token_required
from model.user import User
from model.grade_model import GradePredictionModel

# Set up blueprint and API
grade_api = Blueprint('grade_api', __name__, url_prefix='/api/grade')
api = Api(grade_api)

# Create model instance
model_instance = GradePredictionModel()

# Define the resource classes at the top level
class Predict(Resource):
    def post(self):
        data = request.get_json()

        if not data or 'inputs' not in data:
            return {"error": "Missing 'inputs' field in JSON payload. Expected a list of 11 numbers (1-5)."}, 400

        user_input = data['inputs']

        if len(user_input) != 11:
            return {"error": f"Expected 11 input values, received {len(user_input)}."}, 400

        try:
            user_input = [int(val) for val in user_input]
        except ValueError:
            return {"error": "All input values must be numbers between 1 and 5."}, 400

        if not all(1 <= val <= 5 for val in user_input):
            return {"error": "Input values should be between 1 and 5."}, 400

        percent, letter = model_instance.predict(user_input)

        return jsonify({
            'predicted_percent': percent,
            'predicted_grade': letter
        })

    @token_required()
    def get(self):
        user = g.current_user
        # Return only the grade_data JSON as stored in the table
        return jsonify(user.grade_data)


# Register the resource routes
api.add_resource(Predict, '/predict')
