from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
from model.study import Study
from __init__ import db
import json
from datetime import datetime

# Create a Blueprint for the study API
study_api = Blueprint('study_api', __name__, url_prefix='/api/study')

# Route to add a new study record or update an existing one
@study_api.route('', methods=['POST'])
def add_study_record():
    try:
        # Get data from the request
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['topic', 'subtopic', 'studied', 'timestamp']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Check if a user is logged in (optional, can be adjusted based on requirements)
        user_id = current_user.id if current_user.is_authenticated else None
        
        # Check if the study record already exists for this topic and subtopic
        existing_record = Study.query.filter_by(
            user_id=user_id,
            topic=data['topic'],
            subtopic=data['subtopic']
        ).first()
        
        if existing_record:
            # Update the existing record
            existing_record.studied = data['studied']
            existing_record.timestamp = data['timestamp']
            db.session.commit()
            return jsonify({'success': True, 'message': 'Study record updated', 'data': existing_record.to_dict()}), 200
        else:
            # Create a new study record
            new_record = Study(
                user_id=user_id,
                topic=data['topic'],
                subtopic=data['subtopic'],
                studied=data['studied'],
                timestamp=data['timestamp']
            )
            
            result = new_record.create()
            if result:
                return jsonify({'success': True, 'message': 'Study record created', 'data': result.to_dict()}), 201
            else:
                return jsonify({'error': 'Failed to create study record'}), 500
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route to get all study records for the current user
@study_api.route('', methods=['GET'])
def get_study_records():
    try:
        # Check if a user is logged in (optional)
        user_id = current_user.id if current_user.is_authenticated else None
        
        # Determine whether to filter by user or get all records
        if user_id and request.args.get('all') != 'true':
            records = Study.query.filter_by(user_id=user_id).all()
        else:
            records = Study.query.all()
        
        # Convert to dictionary for JSON response
        result = [record.to_dict() for record in records]
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route to get study progress statistics
@study_api.route('/stats', methods=['GET'])
def get_study_stats():
    try:
        # Check if a user is logged in (optional)
        user_id = current_user.id if current_user.is_authenticated else None
        
        # Base query depending on whether we're filtering by user
        if user_id and request.args.get('all') != 'true':
            total_count = Study.query.filter_by(user_id=user_id).count()
            completed_count = Study.query.filter_by(user_id=user_id, studied=True).count()
        else:
            total_count = Study.query.count()
            completed_count = Study.query.filter_by(studied=True).count()
        
        # Calculate completion percentage
        completion_percentage = (completed_count / total_count * 100) if total_count > 0 else 0
        
        # Get topic-specific stats
        topic_stats = {}
        if user_id and request.args.get('all') != 'true':
            topics = db.session.query(Study.topic).filter_by(user_id=user_id).distinct().all()
        else:
            topics = db.session.query(Study.topic).distinct().all()
        
        for topic_tuple in topics:
            topic = topic_tuple[0]
            if user_id and request.args.get('all') != 'true':
                topic_total = Study.query.filter_by(user_id=user_id, topic=topic).count()
                topic_completed = Study.query.filter_by(user_id=user_id, topic=topic, studied=True).count()
            else:
                topic_total = Study.query.filter_by(topic=topic).count()
                topic_completed = Study.query.filter_by(topic=topic, studied=True).count()
            
            topic_stats[topic] = {
                'total': topic_total,
                'completed': topic_completed,
                'percentage': (topic_completed / topic_total * 100) if topic_total > 0 else 0
            }
        
        # Return the statistics
        return jsonify({
            'total_topics': total_count,
            'completed_topics': completed_count,
            'completion_percentage': completion_percentage,
            'topic_stats': topic_stats
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route to delete a study record
@study_api.route('/<int:record_id>', methods=['DELETE'])
@login_required
def delete_study_record(record_id):
    try:
        record = Study.query.get(record_id)
        
        if not record:
            return jsonify({'error': 'Study record not found'}), 404
        
        # Check if the record belongs to the current user (optional security check)
        if record.user_id and record.user_id != current_user.id and current_user.role != 'Admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        if record.delete():
            return jsonify({'success': True, 'message': 'Study record deleted'}), 200
        else:
            return jsonify({'error': 'Failed to delete study record'}), 500
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
