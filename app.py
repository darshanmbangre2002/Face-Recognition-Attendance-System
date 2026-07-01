import os
import base64
import io
import json
from datetime import datetime, date, time
from flask import Flask, request, jsonify, render_template, send_from_directory, Response
from flask_cors import CORS
from PIL import Image
import cv2
import numpy as np

from config import Config
from database import Database
from face_engine import FaceEngine
from utils import generate_token, decode_token, send_email_notification, generate_attendance_csv, generate_attendance_pdf

# Initialize Config & Database
Config.init_app()
Database.initialize_db()

app = Flask(__name__)
app.config.from_object(Config)
CORS(app) # Enable CORS for all domains to support mobile clients

# -------------------------------------------------------------
# Security Middleware / Decorator
# -------------------------------------------------------------
from functools import wraps

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # Support both 'Authorization' header and query parameter (useful for exports)
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        elif 'token' in request.args:
            token = request.args.get('token')
            
        if not token:
            return jsonify({'success': False, 'message': 'Token is missing!'}), 401
            
        payload = decode_token(token)
        if not payload:
            return jsonify({'success': False, 'message': 'Token is invalid or expired!'}), 401
            
        request.user_identity = payload['sub']
        request.user_role = payload['role']
        return f(*args, **kwargs)
    return decorated

# -------------------------------------------------------------
# Helper Helpers for Image Parsing
# -------------------------------------------------------------
def get_image_from_request():
    """Extracts OpenCV BGR image from either base64 JSON payload or multipart form file."""
    # 1. Check if multipart file uploaded
    if 'image' in request.files:
        file = request.files['image']
        if file.filename == '':
            return None
        img_bytes = file.read()
        nparr = np.frombuffer(img_bytes, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
    # 2. Check JSON payload for base64 string
    data = request.get_json(silent=True)
    if data and 'image' in data:
        base64_str = data['image']
        if ',' in base64_str:
            base64_str = base64_str.split(',')[1]
        try:
            img_data = base64.b64decode(base64_str)
            img = Image.open(io.BytesIO(img_data))
            # Convert RGB (PIL) to BGR (OpenCV)
            return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        except Exception as e:
            print(f"Error decoding base64 image: {e}")
            return None
            
    return None

# -------------------------------------------------------------
# Frontend Routes
# -------------------------------------------------------------
@app.route('/')
def home():
    """Serves the Admin Panel Interface."""
    return render_template('dashboard.html')

# Serve uploaded pictures safely
@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    return send_from_directory('uploads', filename)

# -------------------------------------------------------------
# Authentication APIs (Module 1)
# -------------------------------------------------------------
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400
        
    username = data['username']
    password = data['password']
    
    # Secure Mock Login for Administrator
    if username == 'admin' and password == 'admin123':
        token = generate_token(username, role='admin')
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'token': token,
            'user': {'username': username, 'role': 'admin'}
        })
        
    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

@app.route('/api/logout', methods=['POST'])
@token_required
def api_logout():
    # Stateless logout (client discards token)
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/refresh-token', methods=['POST'])
def api_refresh():
    data = request.get_json()
    if not data or 'token' not in data:
        return jsonify({'success': False, 'message': 'Token required'}), 400
        
    payload = decode_token(data['token'])
    if not payload:
        return jsonify({'success': False, 'message': 'Token expired or invalid'}), 401
        
    new_token = generate_token(payload['sub'], payload['role'])
    return jsonify({'success': True, 'token': new_token})

# -------------------------------------------------------------
# Employee Management APIs (Module 2)
# -------------------------------------------------------------
@app.route('/api/employees', methods=['GET'])
@token_required
def get_employees():
    query = "SELECT * FROM employees ORDER BY employee_id DESC"
    employees = Database.execute_query(query, fetch_all=True)
    return jsonify({'success': True, 'employees': employees})

@app.route('/api/employee/<int:emp_id>', methods=['GET'])
@token_required
def get_employee(emp_id):
    query = "SELECT * FROM employees WHERE employee_id = %s"
    employee = Database.execute_query(query, (emp_id,), fetch_one=True)
    if not employee:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404
    return jsonify({'success': True, 'employee': employee})

@app.route('/api/employee', methods=['POST'])
@token_required
def add_employee():
    data = request.get_json()
    if not data or 'employee_name' not in data:
        return jsonify({'success': False, 'message': 'Employee Name is required'}), 400
        
    query = """
    INSERT INTO employees (employee_name, department, designation, email, mobile, status)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    params = (
        data['employee_name'],
        data.get('department', ''),
        data.get('designation', ''),
        data.get('email', ''),
        data.get('mobile', ''),
        data.get('status', 1)
    )
    
    try:
        new_id = Database.execute_query(query, params, commit=True)
        return jsonify({
            'success': True,
            'message': 'Employee added successfully',
            'employee_id': new_id
        }), 211
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/employee', methods=['PUT'])
@token_required
def update_employee():
    data = request.get_json()
    if not data or 'employee_id' not in data:
        return jsonify({'success': False, 'message': 'Employee ID is required'}), 400
        
    query = """
    UPDATE employees 
    SET employee_name = %s, department = %s, designation = %s, email = %s, mobile = %s, status = %s
    WHERE employee_id = %s
    """
    params = (
        data['employee_name'],
        data.get('department', ''),
        data.get('designation', ''),
        data.get('email', ''),
        data.get('mobile', ''),
        data.get('status', 1),
        data['employee_id']
    )
    
    try:
        Database.execute_query(query, params, commit=True)
        return jsonify({'success': True, 'message': 'Employee updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/employee', methods=['DELETE'])
@token_required
def delete_employee():
    emp_id = request.args.get('employee_id')
    if not emp_id:
        return jsonify({'success': False, 'message': 'Employee ID parameter is required'}), 400
        
    try:
        Database.execute_query("DELETE FROM employees WHERE employee_id = %s", (emp_id,), commit=True)
        return jsonify({'success': True, 'message': 'Employee and face credentials deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# -------------------------------------------------------------
# Face Enrollment & Verification APIs (Modules 3 & 4)
# -------------------------------------------------------------
@app.route('/api/enroll-face', methods=['POST'])
@token_required
def enroll_face():
    # Support multipart/form-data for files, or JSON with base64
    emp_id = request.form.get('employee_id')
    if not emp_id:
        # Check JSON
        data = request.get_json(silent=True)
        if data:
            emp_id = data.get('employee_id')
            
    if not emp_id:
        return jsonify({'success': False, 'message': 'employee_id is required'}), 400
        
    img_np = get_image_from_request()
    if img_np is None:
        return jsonify({'success': False, 'message': 'Valid image file or base64 stream required'}), 400
        
    # Verify Employee exists
    emp = Database.execute_query("SELECT employee_name FROM employees WHERE employee_id = %s", (emp_id,), fetch_one=True)
    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404
        
    # Detect face and compute embedding
    boxes = FaceEngine.detect_faces(img_np)
    if not boxes:
        return jsonify({'success': False, 'message': 'No face detected in the image. Please try again with better lighting.'}), 400
    if len(boxes) > 1:
        return jsonify({'success': False, 'message': 'Multiple faces detected. Please make sure only one face is in the frame.'}), 400
        
    # Compute embeddings
    embeddings = FaceEngine.get_embeddings(img_np, boxes)
    if not embeddings or len(embeddings) == 0:
        return jsonify({'success': False, 'message': 'Could not extract clean facial features.'}), 400
        
    # Save image for audit reference
    filename = f"emp_{emp_id}_{int(datetime.now().timestamp())}.jpg"
    filepath = os.path.join(Config.UPLOAD_FOLDER_PROFILES, filename)
    cv2.imwrite(filepath, img_np)
    
    # Store embedding
    embedding_str = json.dumps(embeddings[0])
    query = """
    INSERT INTO face_embeddings (employee_id, embedding, model_version, created_date)
    VALUES (%s, %s, %s, %s)
    """
    params = (emp_id, embedding_str, 'v1', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    Database.execute_query(query, params, commit=True)
    
    return jsonify({
        'success': True,
        'message': f"Face credentials successfully registered for {emp['employee_name']}.",
        'face_box': boxes[0]
    })

@app.route('/api/enroll-face', methods=['PUT'])
@token_required
def update_enroll_face():
    """
    Overwrites the existing face data for an employee (re-registration/edit).
    """
    emp_id = request.form.get('employee_id')
    if not emp_id:
        data = request.get_json(silent=True)
        if data:
            emp_id = data.get('employee_id')
            
    if not emp_id:
        return jsonify({'success': False, 'message': 'employee_id is required'}), 400
        
    img_np = get_image_from_request()
    if img_np is None:
        return jsonify({'success': False, 'message': 'Valid image file or base64 stream required'}), 400
        
    emp = Database.execute_query("SELECT employee_name FROM employees WHERE employee_id = %s", (emp_id,), fetch_one=True)
    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404
        
    boxes = FaceEngine.detect_faces(img_np)
    if not boxes:
        return jsonify({'success': False, 'message': 'No face detected in the image. Please try again with better lighting.'}), 400
    if len(boxes) > 1:
        return jsonify({'success': False, 'message': 'Multiple faces detected. Please make sure only one face is in the frame.'}), 400
        
    embeddings = FaceEngine.get_embeddings(img_np, boxes)
    if not embeddings or len(embeddings) == 0:
        return jsonify({'success': False, 'message': 'Could not extract clean facial features.'}), 400
        
    # Overwrite: Delete all existing face records for this employee
    Database.execute_query("DELETE FROM face_embeddings WHERE employee_id = %s", (emp_id,), commit=True)
    
    # Save image for audit reference
    filename = f"emp_{emp_id}_{int(datetime.now().timestamp())}.jpg"
    filepath = os.path.join(Config.UPLOAD_FOLDER_PROFILES, filename)
    cv2.imwrite(filepath, img_np)
    
    # Store embedding
    embedding_str = json.dumps(embeddings[0])
    query = """
    INSERT INTO face_embeddings (employee_id, embedding, model_version, created_date)
    VALUES (%s, %s, %s, %s)
    """
    params = (emp_id, embedding_str, 'v1', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    Database.execute_query(query, params, commit=True)
    
    return jsonify({
        'success': True,
        'message': f"Face credentials successfully updated (overwritten) for {emp['employee_name']}.",
        'face_box': boxes[0]
    })


@app.route('/api/verify-face', methods=['POST'])
def verify_face():
    """
    Compares the uploaded face against the database.
    Does NOT require a JWT token to make mobile client integrations easier, 
    but relies on the facial features comparison matching database entries.
    """
    img_np = get_image_from_request()
    if img_np is None:
        return jsonify({'success': False, 'message': 'Valid image required'}), 400
        
    # Detect faces
    boxes = FaceEngine.detect_faces(img_np)
    if not boxes:
        return jsonify({'success': False, 'message': 'No face detected'}), 200 # Return 200 but success False so client handles it smoothly
    if len(boxes) > 1:
        return jsonify({'success': False, 'message': 'Multiple faces detected'}), 200
        
    # Extract embedding
    embeddings = FaceEngine.get_embeddings(img_np, boxes)
    if not embeddings:
        return jsonify({'success': False, 'message': 'Could not calculate face embedding'}), 200
        
    # Fetch all embeddings from db
    db_embeddings_raw = Database.execute_query(
        "SELECT employee_id, embedding FROM face_embeddings", 
        fetch_all=True
    )
    
    if not db_embeddings_raw:
        return jsonify({'success': False, 'message': 'No enrolled faces found in the database.'}), 200
        
    # Deserialize embeddings
    db_embeddings = []
    for record in db_embeddings_raw:
        try:
            db_embeddings.append({
                'employee_id': record['employee_id'],
                'embedding': json.loads(record['embedding'])
            })
        except Exception:
            continue
            
    # Match face
    emp_id, confidence = FaceEngine.match_face_in_database(
        embeddings[0], 
        db_embeddings, 
        threshold=Config.FACE_MATCH_THRESHOLD
    )
    
    if not emp_id:
        return jsonify({'success': False, 'message': 'Face verification failed. Person not recognized.'}), 200
        
    # Fetch employee details
    emp = Database.execute_query(
        "SELECT employee_id, employee_name, department, designation, email, status FROM employees WHERE employee_id = %s", 
        (emp_id,), 
        fetch_one=True
    )
    
    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 200
        
    if emp.get('status') == 0:
        return jsonify({
            'success': False,
            'message': f"Verification blocked. {emp['employee_name']} is currently Inactive or Suspended."
        }), 200
        
    return jsonify({
        'success': True,
        'message': 'Face recognized successfully!',
        'employee': {
            'employee_id': emp['employee_id'],
            'employee_name': emp['employee_name'],
            'department': emp['department'],
            'designation': emp['designation'],
            'email': emp['email']
        },
        'confidence_score': confidence
    })

@app.route('/api/face-status', methods=['GET'])
@token_required
def face_status():
    emp_id = request.args.get('employee_id')
    if not emp_id:
        return jsonify({'success': False, 'message': 'Employee ID required'}), 400
        
    count_record = Database.execute_query(
        "SELECT COUNT(*) as count FROM face_embeddings WHERE employee_id = %s",
        (emp_id,),
        fetch_one=True
    )
    
    has_face = count_record['count'] > 0 if count_record else False
    return jsonify({
        'success': True,
        'employee_id': int(emp_id),
        'enrolled': has_face,
        'enrollment_count': count_record['count'] if count_record else 0
    })

@app.route('/api/face', methods=['DELETE'])
@token_required
def delete_face():
    emp_id = request.args.get('employee_id')
    if not emp_id:
        return jsonify({'success': False, 'message': 'Employee ID required'}), 400
        
    Database.execute_query("DELETE FROM face_embeddings WHERE employee_id = %s", (emp_id,), commit=True)
    return jsonify({'success': True, 'message': 'Face credentials deleted successfully.'})

# -------------------------------------------------------------
# Attendance APIs (Module 5)
# -------------------------------------------------------------
@app.route('/api/attendance/checkin', methods=['POST'])
def attendance_checkin():
    """
    Records Check-in.
    """
    # Accept fields
    data = request.get_json(silent=True)
    if not data:
        # Check form data (for multipart upload check-in photo)
        data = request.form
        
    emp_id = data.get('employee_id')
    if not emp_id:
        return jsonify({'success': False, 'message': 'employee_id is required'}), 400
        
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    device_id = data.get('device_id')
    confidence_score = float(data.get('confidence_score', 1.0))
    
    today_str = date.today().strftime("%Y-%m-%d")
    now_time_str = datetime.now().strftime("%H:%M:%S")
    
    # 1. Fetch Employee
    emp = Database.execute_query("SELECT employee_name, email, status FROM employees WHERE employee_id = %s", (emp_id,), fetch_one=True)
    if not emp:
        return jsonify({'success': False, 'message': 'Employee not found'}), 404
        
    if emp.get('status') == 0:
        return jsonify({
            'success': False,
            'message': f"Check-in blocked. {emp['employee_name']}'s status is Inactive or Suspended."
        }), 403
        
    # 2. Prevent Duplicate Attendance Check-in
    existing = Database.execute_query(
        "SELECT attendance_id FROM attendance WHERE employee_id = %s AND attendance_date = %s",
        (emp_id, today_str),
        fetch_one=True
    )
    if existing:
        return jsonify({
            'success': False, 
            'message': f"Duplicate check-in blocked. {emp['employee_name']} has already checked in today."
        }), 400
        
    # Save check-in photo if provided
    img_path = None
    img_np = get_image_from_request()
    if img_np is not None:
        filename = f"checkin_{emp_id}_{int(datetime.now().timestamp())}.jpg"
        filepath = os.path.join(Config.UPLOAD_FOLDER_ATTENDANCE, filename)
        cv2.imwrite(filepath, img_np)
        img_path = filepath
        
    # Determine check-in status based on time
    # On-time up to 09:45:00, Late from 09:45:01 to 12:00:00, Half-day from 12:00:01 onwards
    status = 'Present'
    if now_time_str > '12:00:00':
        status = 'Half-Day'
    elif now_time_str > '09:45:00':
        status = 'Late'
        
    # Insert record
    query = """
    INSERT INTO attendance (employee_id, attendance_date, check_in, check_out, latitude, longitude, device_id, confidence_score, image_path, status)
    VALUES (%s, %s, %s, NULL, %s, %s, %s, %s, %s, %s)
    """
    params = (emp_id, today_str, now_time_str, latitude, longitude, device_id, confidence_score, img_path, status)
    
    try:
        attendance_id = Database.execute_query(query, params, commit=True)
    except Exception as e:
        err_msg = str(e).lower()
        if 'unique' in err_msg or 'duplicate' in err_msg:
            return jsonify({
                'success': False,
                'message': f"Duplicate check-in blocked. {emp['employee_name']} has already checked in today."
            }), 400
        raise e
    
    # Send email notification
    if emp['email']:
        subject = f"Attendance Check-In Successful: {emp['employee_name']}"
        body = f"""
        <h3>Attendance Confirmation</h3>
        <p>Hello <b>{emp['employee_name']}</b>,</p>
        <p>Your check-in has been successfully recorded.</p>
        <ul>
            <li><b>Date:</b> {today_str}</li>
            <li><b>Time:</b> {now_time_str}</li>
            <li><b>Status:</b> {status}</li>
            <li><b>Confidence:</b> {confidence_score:.2f}</li>
        </ul>
        <p>Thank you,</p>
        <p><b>HR Team</b></p>
        """
        send_email_notification(emp['email'], subject, body)
        
    return jsonify({
        'success': True,
        'message': f"Check-in successfully recorded for {emp['employee_name']}. Status: {status}",
        'attendance_id': attendance_id,
        'check_in': now_time_str,
        'status': status
    })

@app.route('/api/attendance/checkout', methods=['POST'])
def attendance_checkout():
    """
    Records Check-out.
    """
    data = request.get_json(silent=True)
    if not data:
        data = request.form
        
    emp_id = data.get('employee_id')
    if not emp_id:
        return jsonify({'success': False, 'message': 'employee_id is required'}), 400
        
    today_str = date.today().strftime("%Y-%m-%d")
    now_time_str = datetime.now().strftime("%H:%M:%S")
    
    # Check if they have a check-in record for today
    existing = Database.execute_query(
        "SELECT attendance_id, check_out FROM attendance WHERE employee_id = %s AND attendance_date = %s",
        (emp_id, today_str),
        fetch_one=True
    )
    
    if not existing:
        return jsonify({
            'success': False, 
            'message': "Check-out blocked. No check-in record found for today. Please check in first."
        }), 400
        
    if existing['check_out']:
        return jsonify({
            'success': False, 
            'message': "Attendance already completed. Check-out already logged for today."
        }), 400
        
    # Update record
    query = """
    UPDATE attendance 
    SET check_out = %s, latitude = %s, longitude = %s
    WHERE attendance_id = %s
    """
    params = (now_time_str, data.get('latitude'), data.get('longitude'), existing['attendance_id'])
    Database.execute_query(query, params, commit=True)
    
    # Fetch Employee name
    emp = Database.execute_query("SELECT employee_name, email FROM employees WHERE employee_id = %s", (emp_id,), fetch_one=True)
    
    # Send email notification
    if emp and emp['email']:
        subject = f"Attendance Check-Out Successful: {emp['employee_name']}"
        body = f"""
        <h3>Attendance Confirmation</h3>
        <p>Hello <b>{emp['employee_name']}</b>,</p>
        <p>Your check-out has been successfully recorded.</p>
        <ul>
            <li><b>Date:</b> {today_str}</li>
            <li><b>Time:</b> {now_time_str}</li>
        </ul>
        <p>Thank you,</p>
        <p><b>HR Team</b></p>
        """
        send_email_notification(emp['email'], subject, body)
        
    return jsonify({
        'success': True,
        'message': f"Check-out successfully recorded for {emp['employee_name'] if emp else 'Employee'}.",
        'check_out': now_time_str
    })

@app.route('/api/attendance/history', methods=['GET'])
@token_required
def attendance_history():
    emp_id = request.args.get('employee_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = """
    SELECT a.*, e.employee_name, e.department, e.designation 
    FROM attendance a 
    JOIN employees e ON a.employee_id = e.employee_id
    WHERE 1=1
    """
    params = []
    
    if emp_id:
        query += " AND a.employee_id = %s"
        params.append(emp_id)
    if start_date:
        query += " AND a.attendance_date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND a.attendance_date <= %s"
        params.append(end_date)
        
    query += " ORDER BY a.attendance_date DESC, a.check_in DESC"
    
    records = Database.execute_query(query, tuple(params) if params else None, fetch_all=True)
    return jsonify({'success': True, 'records': records})

@app.route('/api/attendance/today', methods=['GET'])
@token_required
def attendance_today():
    today_str = date.today().strftime("%Y-%m-%d")
    query = """
    SELECT a.*, e.employee_name, e.department, e.designation 
    FROM attendance a 
    JOIN employees e ON a.employee_id = e.employee_id
    WHERE a.attendance_date = %s
    ORDER BY a.check_in DESC
    """
    records = Database.execute_query(query, (today_str,), fetch_all=True)
    return jsonify({'success': True, 'records': records})

# -------------------------------------------------------------
# Reports APIs (Module 6)
# -------------------------------------------------------------
@app.route('/api/reports/daily', methods=['GET'])
@token_required
def report_daily():
    target_date = request.args.get('date', date.today().strftime("%Y-%m-%d"))
    export_type = request.args.get('export')
    
    # Query today's attendance logs
    query = """
    SELECT a.*, e.employee_name, e.department, e.designation 
    FROM attendance a 
    JOIN employees e ON a.employee_id = e.employee_id
    WHERE a.attendance_date = %s
    ORDER BY a.check_in ASC
    """
    records = Database.execute_query(query, (target_date,), fetch_all=True)
    
    if export_type == 'csv':
        csv_data = generate_attendance_csv(records)
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename=attendance_daily_{target_date}.csv"}
        )
    elif export_type == 'pdf':
        pdf_data = generate_attendance_pdf(records, title=f"Daily Attendance Report - {target_date}")
        return Response(
            pdf_data,
            mimetype="application/pdf",
            headers={"Content-disposition": f"attachment; filename=attendance_daily_{target_date}.pdf"}
        )
        
    return jsonify({'success': True, 'records': records})

@app.route('/api/reports/monthly', methods=['GET'])
@token_required
def report_monthly():
    # Expects year-month e.g., '2026-07'
    current_month = request.args.get('month', datetime.now().strftime("%Y-%m"))
    export_type = request.args.get('export')
    
    like_pattern = f"{current_month}%"
    query = """
    SELECT a.*, e.employee_name, e.department, e.designation 
    FROM attendance a 
    JOIN employees e ON a.employee_id = e.employee_id
    WHERE a.attendance_date LIKE %s
    ORDER BY a.attendance_date ASC, a.check_in ASC
    """
    records = Database.execute_query(query, (like_pattern,), fetch_all=True)
    
    if export_type == 'csv':
        csv_data = generate_attendance_csv(records)
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename=attendance_monthly_{current_month}.csv"}
        )
    elif export_type == 'pdf':
        pdf_data = generate_attendance_pdf(records, title=f"Monthly Attendance Report - {current_month}")
        return Response(
            pdf_data,
            mimetype="application/pdf",
            headers={"Content-disposition": f"attachment; filename=attendance_monthly_{current_month}.pdf"}
        )
        
    return jsonify({'success': True, 'records': records})

@app.route('/api/reports/late', methods=['GET'])
@token_required
def report_late():
    # Default filters: find check-ins marked as Late or Half-Day
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    export_type = request.args.get('export')
    
    query = """
    SELECT a.*, e.employee_name, e.department, e.designation 
    FROM attendance a 
    JOIN employees e ON a.employee_id = e.employee_id
    WHERE a.status IN ('Late', 'Half-Day')
    """
    params = []
    
    if start_date:
        query += " AND a.attendance_date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND a.attendance_date <= %s"
        params.append(end_date)
        
    query += " ORDER BY a.attendance_date DESC, a.check_in ASC"
    
    records = Database.execute_query(query, tuple(params) if params else None, fetch_all=True)
    
    if export_type == 'csv':
        csv_data = generate_attendance_csv(records)
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename=late_report.csv"}
        )
    elif export_type == 'pdf':
        pdf_data = generate_attendance_pdf(records, title="Late Arrivals Report (After 09:45 AM / Half-Day)")
        return Response(
            pdf_data,
            mimetype="application/pdf",
            headers={"Content-disposition": f"attachment; filename=late_report.pdf"}
        )
        
    return jsonify({'success': True, 'records': records})

@app.route('/api/reports/employee', methods=['GET'])
@token_required
def report_employee():
    emp_id = request.args.get('employee_id')
    if not emp_id:
        return jsonify({'success': False, 'message': 'employee_id parameter required'}), 400
        
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    export_type = request.args.get('export')
    
    query = """
    SELECT a.*, e.employee_name, e.department, e.designation 
    FROM attendance a 
    JOIN employees e ON a.employee_id = e.employee_id
    WHERE a.employee_id = %s
    """
    params = [emp_id]
    
    if start_date:
        query += " AND a.attendance_date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND a.attendance_date <= %s"
        params.append(end_date)
        
    query += " ORDER BY a.attendance_date DESC"
    
    records = Database.execute_query(query, tuple(params), fetch_all=True)
    
    # Get employee details for header
    emp_details = Database.execute_query(
        "SELECT employee_name FROM employees WHERE employee_id = %s", 
        (emp_id,), 
        fetch_one=True
    )
    emp_name = emp_details['employee_name'] if emp_details else "Employee"
    
    if export_type == 'csv':
        csv_data = generate_attendance_csv(records)
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename=attendance_employee_{emp_id}.csv"}
        )
    elif export_type == 'pdf':
        pdf_data = generate_attendance_pdf(records, title=f"Attendance Report - {emp_name} (ID: {emp_id})")
        return Response(
            pdf_data,
            mimetype="application/pdf",
            headers={"Content-disposition": f"attachment; filename=attendance_employee_{emp_id}.pdf"}
        )
        
    return jsonify({'success': True, 'records': records})

@app.route("/health")
def health():
    return {"status": "ok"}, 200

# Start application server
if __name__ == '__main__':
    # Clean folders check
    Config.init_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
