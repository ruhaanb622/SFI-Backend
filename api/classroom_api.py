from flask import Blueprint, request, jsonify, g
from __init__ import db
from model.classroom import Classroom
from model.user import User
from api.authorize import token_required

classroom_api = Blueprint('classroom_api', __name__, url_prefix='/api/classrooms')


@token_required()
def get_all_classrooms():
    current_user = g.current_user
    if current_user.role == 'Admin':
        classrooms = Classroom.query.all()
    else:
        user_school = current_user.school.strip()
        # Fetch all classrooms, then filter in Python (only for debugging)
        all_classrooms = Classroom.query.all()
        classrooms = [c for c in all_classrooms if c.school_name.strip() == user_school]
    return jsonify([c.to_dict() for c in classrooms])



@token_required()
def get_classroom_by_id(id):
    classroom = Classroom.query.get_or_404(id)
    current_user = g.current_user
    if current_user.role != 'Admin' and classroom.school_name != current_user.school:
        return {"message": "Access denied"}, 403
    return jsonify(classroom.to_dict())


@token_required()
def create_new_classroom():
    current_user = g.current_user
    if current_user.role not in ['Admin', 'Teacher']:
        return {"message": "Permission denied"}, 403

    data = request.get_json()
    name = data.get('name')
    if not name:
        return {"message": "Classroom name is required"}, 400

    classroom = Classroom(
        name=name,
        school_name=current_user.school,
        owner_teacher_id=current_user.id
    )
    classroom.create()
    return jsonify(classroom.to_dict()), 201


@token_required()
def delete_classroom_by_id(id):
    classroom = Classroom.query.get_or_404(id)
    current_user = g.current_user
    if current_user.role not in ['Admin', 'Teacher']:
        return {"message": "Permission denied"}, 403
    if current_user.role != 'Admin' and classroom.school_name != current_user.school:
        return {"message": "Access denied"}, 403

    classroom.delete()
    return {"message": "Classroom deleted"}, 200


@token_required()
def update_classroom(id):
    classroom = Classroom.query.get_or_404(id)
    current_user = g.current_user
    if current_user.role not in ['Admin', 'Teacher']:
        return {"message": "Permission denied"}, 403
    if current_user.role != 'Admin' and classroom.school_name != current_user.school:
        return {"message": "Access denied"}, 403

    data = request.get_json()
    name = data.get('name')
    if name:
        classroom.name = name
        db.session.commit()
        return jsonify(classroom.to_dict())
    return {"message": "No valid fields to update"}, 400


@token_required()
def list_students_in_classroom(id):
    classroom = Classroom.query.get_or_404(id)
    current_user = g.current_user
    if current_user.role != 'Admin' and classroom.school_name != current_user.school:
        return {"message": "Access denied"}, 403

    students = []
    for s in classroom.students:
        try:
            students.append(s.to_dict())
        except AttributeError:
            students.append({"id": s.id, "name": getattr(s, "name", None)})
    return jsonify(students)


@token_required()
def get_student_in_classroom(id, student_id):
    classroom = Classroom.query.get_or_404(id)
    current_user = g.current_user
    if current_user.role != 'Admin' and classroom.school_name != current_user.school:
        return {"message": "Access denied"}, 403

    student = User.query.get_or_404(student_id)
    if not classroom.students.filter_by(id=student.id).first():
        return {"message": "Student not in this classroom"}, 404

    try:
        return jsonify(student.to_dict())
    except AttributeError:
        return jsonify({"id": student.id, "name": getattr(student, "name", None)})


@token_required()
def add_student_to_classroom(id, student_id):
    classroom = Classroom.query.get_or_404(id)
    current_user = g.current_user
    if current_user.role not in ['Admin', 'Teacher']:
        return {"message": "Permission denied"}, 403
    if current_user.role != 'Admin' and classroom.school_name != current_user.school:
        return {"message": "Access denied"}, 403

    student = User.query.get_or_404(student_id)
    if classroom.students.filter_by(id=student.id).first():
        return {"message": "Student already in classroom"}, 400

    classroom.students.append(student)
    db.session.commit()

    student_name = getattr(student, "username", None) or getattr(student, "_name", None) or f"ID {student.id}"
    classroom_name = getattr(classroom, "name", f"ID {classroom.id}")
    return {"message": f"Student {student_name} added to classroom {classroom_name}"}, 201


@token_required()
def remove_student_from_classroom(id, student_id):
    classroom = Classroom.query.get_or_404(id)
    current_user = g.current_user
    if current_user.role not in ['Admin', 'Teacher']:
        return {"message": "Permission denied"}, 403
    if current_user.role != 'Admin' and classroom.school_name != current_user.school:
        return {"message": "Access denied"}, 403

    student = User.query.get_or_404(student_id)
    if not classroom.students.filter_by(id=student.id).first():
        return {"message": "Student not in this classroom"}, 404

    classroom.students.remove(student)
    db.session.commit()

    student_name = getattr(student, "username", None) or getattr(student, "_name", None) or f"ID {student.id}"
    classroom_name = getattr(classroom, "name", f"ID {classroom.id}")
    return {"message": f"Student {student_name} removed from classroom {classroom_name}"}, 200


# ROUTES

classroom_api.route('/', methods=['GET'])(get_all_classrooms)
classroom_api.route('/<int:id>', methods=['GET'])(get_classroom_by_id)
classroom_api.route('/', methods=['POST'])(create_new_classroom)
classroom_api.route('/<int:id>', methods=['DELETE'])(delete_classroom_by_id)
classroom_api.route('/<int:id>', methods=['PUT'])(update_classroom)

classroom_api.route('/<int:id>/students', methods=['GET'])(list_students_in_classroom)
classroom_api.route('/<int:id>/students/<int:student_id>', methods=['GET'])(get_student_in_classroom)
classroom_api.route('/<int:id>/students/<int:student_id>', methods=['POST'])(add_student_to_classroom)
classroom_api.route('/<int:id>/students/<int:student_id>', methods=['DELETE'])(remove_student_from_classroom)
