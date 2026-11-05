from flask import Flask, request, jsonify, session, send_from_directory
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime
from dotenv import load_dotenv
from config import Config
import os
import uuid

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

app.secret_key = app.config.get("SECRET_KEY") or os.getenv("SECRET_KEY")
app.config.setdefault("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[Config.MONGO_DB]

users_collection = db["users"]
assignments_collection = db["assignments"]
projects_collection = db["projects"]
lectures_collection = db["lectures"]
attendance_collection = db["attendance"]

def json_error(message, status=400):
    return jsonify({"success": False, "message": message}), status


def serialize_document(document):
    if isinstance(document, list):
        return [serialize_document(item) for item in document]

    if isinstance(document, dict):
        result = {}

        for key, value in document.items():
            if key == "_id":
                result["id"] = str(value)
            elif isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.strftime("%d-%m-%Y")
            elif isinstance(value, (dict, list)):
                result[key] = serialize_document(value)
            else:
                result[key] = value

        return result

    return document


def get_current_user():
    user_id = session.get("user_id")

    if not user_id or not ObjectId.is_valid(user_id):
        return None

    return users_collection.find_one({"_id": ObjectId(user_id)})


def api_login_required(role=None):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            user = get_current_user()

            if not user:
                session.clear()
                return json_error("Please login first.", 401)

            print("Logged-in user role:", user.get("role"))
            print("Required role:", role)

            if role and user.get("role") != role:
                return json_error("You are not authorized to access this page.", 403)

            return function(*args, **kwargs)

        return wrapper

    return decorator


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in app.config["ALLOWED_EXTENSIONS"]
    )


def save_uploaded_file(file):
    if not file or not file.filename:
        return None

    if not allowed_file(file.filename):
        return None

    original_name = secure_filename(file.filename)
    extension = original_name.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{extension}"

    destination = os.path.join(
        app.config["UPLOAD_FOLDER"],
        unique_name
    )

    file.save(destination)

    return {
        "filename": original_name,
        "file_path": f"/static/uploads/{unique_name}"
    }


def request_data():
    return request.get_json(silent=True) or request.form


def public_user(user):
    if not user:
        return None

    return {
        "id": str(user["_id"]),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "role": user.get("role", ""),
        "phone": user.get("phone", ""),
        "department": user.get("department", "")
    }


@app.route("/")
def index():
    return send_from_directory(
        os.path.join(app.root_path, "templates"),
        "index.html"
    )

@app.route("/pages/<path:filename>")
def plain_page(filename):
    return send_from_directory(
        os.path.join(app.root_path, "templates"),
        filename
    )


@app.route("/api/signup/<role>", methods=["POST"])
def api_signup(role):
    if role not in ["student", "teacher"]:
        return json_error("Invalid account role.")

    data = request_data()

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    confirm_password = data.get("confirm_password", "")

    if not name or not email or not password:
        return json_error("Please fill all required fields.")

    if password != confirm_password:
        return json_error("Passwords do not match.")

    if len(password) < 6:
        return json_error("Password must contain at least 6 characters.")

    if users_collection.find_one({"email": email}):
        return json_error("Email is already registered.", 409)

    user = {
        "name": name,
        "email": email,
        "password": generate_password_hash(password),
        "role": role,
        "created_at": datetime.now()
    }

    users_collection.insert_one(user)

    return jsonify({
        "success": True,
        "message": "Registration successful. Please login."
    }), 201

@app.route("/api/login/<role>", methods=["POST"])
def api_login(role):
    if role not in ["student", "teacher"]:
        return json_error("Invalid account role.")

    data = request_data()

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    user = users_collection.find_one({
        "email": email,
        "role": role
    })

    if not user or not check_password_hash(user.get("password", ""), password):
        return json_error("Invalid email or password.", 401)

    session.clear()
    session["user_id"] = str(user["_id"])
    session["role"] = user["role"]
    session["name"] = user["name"]

    return jsonify({
        "success": True,
        "message": f"Welcome, {user['name']}!",
        "role": user["role"],
        "redirect": "/pages/student/dashboard.html"
        if role == "student"
        else "/pages/teacher/dashboard.html"
    })

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()

    return jsonify({
        "success": True,
        "message": "Logged out successfully."
    })

@app.route("/api/me", methods=["GET"])
@api_login_required()
def api_me():
    return jsonify({
        "success": True,
        "user": public_user(get_current_user())
    })

@app.route("/api/student/dashboard", methods=["GET"])
@api_login_required("student")
def api_student_dashboard():
    user_id = session["user_id"]

    total_assignments = assignments_collection.count_documents({
        "student_id": user_id
    })

    total_projects = projects_collection.count_documents({
        "student_id": user_id
    })

    total_lectures = attendance_collection.count_documents({
        "student_id": user_id
    })

    present = attendance_collection.count_documents({
        "student_id": user_id,
        "status": "Present"
    })

    percentage = (
        round(present / total_lectures * 100, 2)
        if total_lectures else 0
    )

    return jsonify({
        "success": True,
        "user": public_user(get_current_user()),
        "total_assignments": total_assignments,
        "total_projects": total_projects,
        "total_lectures": total_lectures,
        "attendance_percentage": percentage
    })

@app.route("/api/student/profile", methods=["GET", "PUT", "POST"])
@api_login_required("student")
def api_student_profile():
    user_id = ObjectId(session["user_id"])

    if request.method in ["PUT", "POST"]:
        data = request_data()

        name = data.get("name", "").strip()
        phone = data.get("phone", "").strip()
        department = data.get("department", "").strip()

        if not name:
            return json_error("Name cannot be empty.")

        users_collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "name": name,
                    "phone": phone,
                    "department": department
                }
            }
        )

        session["name"] = name

        return jsonify({
            "success": True,
            "message": "Profile updated successfully."
        })

    user = users_collection.find_one({"_id": user_id})

    return jsonify({
        "success": True,
        "user": public_user(user)
    })

@app.route("/api/student/assignments", methods=["GET", "POST"])
@api_login_required("student")
def api_student_assignments():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        file = request.files.get("file")

        if not title or not file or not file.filename:
            return json_error("Please enter a title and select a file.")

        uploaded = save_uploaded_file(file)

        if not uploaded:
            return json_error("Invalid file type.")

        assignment = {
            "student_id": session["user_id"],
            "student_name": session["name"],
            "title": title,
            "description": description,
            "filename": uploaded["filename"],
            "file_path": uploaded["file_path"],
            "status": "Pending",
            "feedback": "",
            "submitted_at": datetime.now()
        }

        assignments_collection.insert_one(assignment)

        return jsonify({
            "success": True,
            "message": "Assignment uploaded successfully."
        }), 201

    assignments = list(
        assignments_collection.find({
            "student_id": session["user_id"]
        }).sort("submitted_at", -1)
    )

    return jsonify({
        "success": True,
        "assignments": serialize_document(assignments)
    })

@app.route("/api/student/projects", methods=["GET", "POST"])
@api_login_required("student")
def api_student_projects():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        file = request.files.get("file")

        if not title or not file or not file.filename:
            return json_error("Please enter a title and select a project file.")

        uploaded = save_uploaded_file(file)

        if not uploaded:
            return json_error("Invalid file type.")

        project = {
            "student_id": session["user_id"],
            "student_name": session["name"],
            "title": title,
            "description": description,
            "filename": uploaded["filename"],
            "file_path": uploaded["file_path"],
            "status": "Pending",
            "feedback": "",
            "submitted_at": datetime.now()
        }

        projects_collection.insert_one(project)

        return jsonify({
            "success": True,
            "message": "Project uploaded successfully."
        }), 201

    projects = list(
        projects_collection.find({
            "student_id": session["user_id"]
        }).sort("submitted_at", -1)
    )

    return jsonify({
        "success": True,
        "projects": serialize_document(projects)
    })

@app.route("/api/student/attendance", methods=["GET"])
@api_login_required("student")
def api_student_attendance():
    records = list(
        attendance_collection.find({
            "student_id": session["user_id"]
        }).sort("date", -1)
    )

    for record in records:
        lecture_id = record.get("lecture_id", "")
        lecture = None

        if ObjectId.is_valid(lecture_id):
            lecture = lectures_collection.find_one({
                "_id": ObjectId(lecture_id)
            })

        record["lecture_title"] = (
            lecture.get("title", "Unknown Lecture")
            if lecture else "Unknown Lecture"
        )

    total = len(records)

    present = sum(
        1 for record in records
        if record.get("status") == "Present"
    )

    percentage = round(present / total * 100, 2) if total else 0

    return jsonify({
        "success": True,
        "records": serialize_document(records),
        "total": total,
        "present": present,
        "absent": total - present,
        "percentage": percentage
    })


@app.route("/api/teacher/dashboard", methods=["GET"])
@api_login_required("teacher")
def api_teacher_dashboard():
    return jsonify({
        "success": True,
        "user": public_user(get_current_user()),
        "total_students": users_collection.count_documents({"role": "student"}),
        "total_assignments": assignments_collection.count_documents({}),
        "pending_assignments": assignments_collection.count_documents({"status": "Pending"}),
        "total_projects": projects_collection.count_documents({}),
        "pending_projects": projects_collection.count_documents({"status": "Pending"}),
        "total_lectures": lectures_collection.count_documents({
            "teacher_id": session["user_id"]
        })
    })


@app.route("/api/teacher/students", methods=["GET"])
@api_login_required("teacher")
def api_teacher_students():
    students = list(
        users_collection.find({"role": "student"}).sort("name", 1)
    )

    result = []

    for student in students:
        user = public_user(student)
        created_at = student.get("created_at")
        user["created_at"] = created_at.strftime("%d-%m-%Y") if created_at else "Not Available"
        result.append(user)

    return jsonify({
        "success": True,
        "students": result
    })

@app.route("/api/teacher/assignments", methods=["GET"])
@api_login_required("teacher")
def api_teacher_assignments():
    assignments = list(
        assignments_collection.find().sort("submitted_at", -1)
    )

    for assignment in assignments:
        student_id = assignment.get("student_id", "")
        student = None

        if ObjectId.is_valid(student_id):
            student = users_collection.find_one({
                "_id": ObjectId(student_id)
            })

        assignment["student_name"] = (
            assignment.get("student_name")
            or (student.get("name") if student else "Unknown")
        )

        assignment["student_email"] = (
            student.get("email", "") if student else ""
        )

    return jsonify({
        "success": True,
        "assignments": serialize_document(assignments)
    })

@app.route("/api/teacher/assignment/update/<assignment_id>", methods=["POST", "PUT"])
@api_login_required("teacher")
def api_update_assignment(assignment_id):
    if not ObjectId.is_valid(assignment_id):
        return json_error("Invalid assignment.")

    data = request_data()
    status = data.get("status", "")
    feedback = data.get("feedback", "").strip()

    if status not in ["Pending", "Checked", "Approved", "Rejected"]:
        return json_error("Invalid assignment status.")

    result = assignments_collection.update_one(
        {"_id": ObjectId(assignment_id)},
        {
            "$set": {
                "status": status,
                "feedback": feedback,
                "reviewed_by": session["user_id"],
                "reviewed_at": datetime.now()
            }
        }
    )

    if result.matched_count == 0:
        return json_error("Assignment not found.", 404)

    return jsonify({
        "success": True,
        "message": "Assignment updated successfully."
    })

@app.route("/api/teacher/projects", methods=["GET"])
@api_login_required("teacher")
def api_teacher_projects():
    projects = list(
        projects_collection.find().sort("submitted_at", -1)
    )

    for project in projects:
        student_id = project.get("student_id", "")
        student = None

        if ObjectId.is_valid(student_id):
            student = users_collection.find_one({
                "_id": ObjectId(student_id)
            })

        project["student_name"] = (
            project.get("student_name")
            or (student.get("name") if student else "Unknown")
        )

        project["student_email"] = (
            student.get("email", "") if student else ""
        )

    return jsonify({
        "success": True,
        "projects": serialize_document(projects)
    })

@app.route("/api/teacher/project/update/<project_id>", methods=["POST", "PUT"])
@api_login_required("teacher")
def api_update_project(project_id):
    if not ObjectId.is_valid(project_id):
        return json_error("Invalid project.")

    data = request_data()
    status = data.get("status", "")
    feedback = data.get("feedback", "").strip()

    if status not in ["Pending", "Checked", "Approved", "Rejected"]:
        return json_error("Invalid project status.")

    result = projects_collection.update_one(
        {"_id": ObjectId(project_id)},
        {
            "$set": {
                "status": status,
                "feedback": feedback,
                "reviewed_by": session["user_id"],
                "reviewed_at": datetime.now()
            }
        }
    )

    if result.matched_count == 0:
        return json_error("Project not found.", 404)

    return jsonify({
        "success": True,
        "message": "Project updated successfully."
    })

@app.route("/api/teacher/attendance", methods=["GET", "POST"])
@api_login_required("teacher")
def api_teacher_attendance():
    teacher_id = session["user_id"]

    if request.method == "POST":
        data = request_data()
        action = data.get("action", "")

        if action == "create_lecture":
            title = data.get("title", "").strip()
            lecture_date = data.get("date", "")

            if not title or not lecture_date:
                return json_error("Enter lecture title and date.")

            lectures_collection.insert_one({
                "title": title,
                "date": lecture_date,
                "teacher_id": teacher_id,
                "created_at": datetime.now()
            })

            return jsonify({
                "success": True,
                "message": "Lecture created successfully."
            }), 201

        if action == "save_attendance":
            lecture_id = data.get("lecture_id", "")

            if not ObjectId.is_valid(lecture_id):
                return json_error("Please select a valid lecture.")

            lecture = lectures_collection.find_one({
                "_id": ObjectId(lecture_id),
                "teacher_id": teacher_id
            })

            if not lecture:
                return json_error("Lecture not found.", 404)

            attendance_rows = data.get("attendance", [])

            for item in attendance_rows:
                student_id = item.get("student_id", "")
                status = item.get("status", "Absent")

                if not ObjectId.is_valid(student_id):
                    continue

                if status not in ["Present", "Absent"]:
                    continue

                student = users_collection.find_one({
                    "_id": ObjectId(student_id),
                    "role": "student"
                })

                if not student:
                    continue

                attendance_collection.update_one(
                    {
                        "student_id": student_id,
                        "lecture_id": lecture_id
                    },
                    {
                        "$set": {
                            "student_id": student_id,
                            "student_name": student["name"],
                            "lecture_id": lecture_id,
                            "status": status,
                            "date": lecture["date"],
                            "marked_by": teacher_id,
                            "updated_at": datetime.now()
                        }
                    },
                    upsert=True
                )

            return jsonify({
                "success": True,
                "message": "Attendance saved successfully."
            })

        return json_error("Invalid attendance action.")

    students = list(
        users_collection.find({
            "role": "student"
        }).sort("name", 1)
    )

    lectures = list(
        lectures_collection.find({
            "teacher_id": teacher_id
        }).sort("date", -1)
    )

    return jsonify({
        "success": True,
        "students": [public_user(student) for student in students],
        "lectures": serialize_document(lectures)
    })

@app.route("/api/teacher/lecture-history", methods=["GET"])
@api_login_required("teacher")
def api_lecture_history():
    lectures = list(
        lectures_collection.find({
            "teacher_id": session["user_id"]
        }).sort("date", -1)
    )

    for lecture in lectures:
        lecture_id = str(lecture["_id"])

        records = list(
            attendance_collection.find({
                "lecture_id": lecture_id
            }).sort("student_name", 1)
        )

        lecture["records"] = serialize_document(records)

        lecture["present_count"] = sum(
            1 for record in records
            if record.get("status") == "Present"
        )

        lecture["absent_count"] = sum(
            1 for record in records
            if record.get("status") == "Absent"
        )

    return jsonify({
        "success": True,
        "lectures": serialize_document(lectures)
    })

@app.errorhandler(413)
def file_too_large(error):
    return json_error("File size cannot exceed 16 MB.", 413)


@app.errorhandler(404)
def page_not_found(error):
    if request.path.startswith("/api/"):
        return json_error("API endpoint not found.", 404)

    return "404 - Page Not Found", 404


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)