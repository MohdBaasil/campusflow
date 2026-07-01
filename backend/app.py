"""
Flask REST API for the Smart Attendance System.
"""
import os
import sys
import cv2
import base64
import hashlib
import numpy as np
import pandas as pd
import csv
import zipfile
import qrcode
import uuid
import socket
from datetime import datetime
from io import BytesIO, StringIO
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import (
    init_db, get_db, Student, Attendance, FaceEmbedding,
    Lecturer, Subject, ClassSession, InternalMarks,
    AttendancePercentageLog, Notification
)
from backend.face_recognition.insightface_detector import InsightFaceDetector
from backend.face_recognition.insightface_recognizer import InsightFaceRecognizer
from backend.database.migration import run_migration
from backend.database.migration_v2 import run_migration_v2
from backend.face_recognition.trainer import train_model
from backend.notification_service import (
    notify_absence, notify_low_attendance,
    build_marks_published_notification, send_email_async
)

ACTIVE_SESSIONS = {}

# ── Auth constants ──
STAFF_CREDENTIALS = {
    'admin': hashlib.sha256('admin123'.encode()).hexdigest()
}
ACTIVE_TOKENS = {}  # token -> { user_type, user_data, created_at }

def get_local_ip():
    """Get the local network IP address of the server."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def get_ngrok_url():
    """Retrieve the active public ngrok tunnel URL if running."""
    try:
        import requests
        res = requests.get('http://127.0.0.1:4040/api/tunnels', timeout=0.5)
        if res.status_code == 200:
            data = res.json()
            tunnels = data.get('tunnels', [])
            for t in tunnels:
                if t.get('proto') == 'https':
                    return t.get('public_url')
                if t.get('public_url'):
                    return t.get('public_url')
    except Exception:
        pass
    return None


FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend')
app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='/static')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB upload limit
CORS(app)


def generate_student_qr(student_id, roll_number):
    """Generate a unique QR code for the student and save to data/qrcodes."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(roll_number)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    qrcodes_dir = os.path.join(BASE_DIR, 'data', 'qrcodes')
    os.makedirs(qrcodes_dir, exist_ok=True)
    img_path = os.path.join(qrcodes_dir, f"{student_id}.png")
    img.save(img_path)
    return img_path


# Initialize components
init_db()
run_migration()
run_migration_v2()
detector = InsightFaceDetector()
recognizer = InsightFaceRecognizer()

# Automatic model retraining at startup if missing on disk (e.g. fresh Render container)
if not recognizer.is_trained:
    print("[Startup] Recognizer model not found on disk. Retraining from database embeddings...")
    try:
        success, msg, _ = train_model()
        print(f"[Startup] Retraining outcome: {msg}")
        if success:
            recognizer._load_model()
    except Exception as startup_err:
        print(f"[Startup] Automatic model retraining failed: {startup_err}")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWN_FACES_DIR = os.path.join(BASE_DIR, 'data', 'known_faces')
os.makedirs(KNOWN_FACES_DIR, exist_ok=True)

# Upload directory for documents
UPLOAD_DIR = os.path.join(BASE_DIR, 'data', 'uploads', 'documents')
os.makedirs(UPLOAD_DIR, exist_ok=True)

SUBJECTS = ['Mathematics', 'Physics', 'Chemistry', 'Computer Science',
            'English', 'History', 'Biology', 'Economics']

# ─────────────────────────────────────────────
# AUTHENTICATION
# ─────────────────────────────────────────────
@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """Handle login for both Staff and Student users."""
    data = request.json or {}
    login_type = data.get('type', '').strip().lower()

    if login_type == 'staff':
        username = data.get('username', '').strip()
        password = data.get('password', '')
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()

        expected = STAFF_CREDENTIALS.get(username)
        if expected and pwd_hash == expected:
            token = str(uuid.uuid4())
            ACTIVE_TOKENS[token] = {
                'user_type': 'staff',
                'user_data': {'username': username},
                'created_at': datetime.now().isoformat()
            }
            return jsonify({
                'success': True,
                'token': token,
                'user_type': 'staff',
                'user_data': {'username': username}
            })
        return jsonify({'success': False, 'error': 'Invalid staff credentials.'}), 401

    elif login_type == 'student':
        roll_number = data.get('roll_number', '').strip().upper()
        password = data.get('password', '')
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()

        db = get_db()
        try:
            student = db.query(Student).filter(Student.roll_number == roll_number).first()
            if not student:
                return jsonify({'success': False, 'error': f'Student with Roll Number "{roll_number}" not found.'}), 404
            
            expected_hash = student.password
            if not expected_hash:
                expected_hash = hashlib.sha256(student.roll_number.strip().upper().encode()).hexdigest()

            if expected_hash != pwd_hash:
                return jsonify({'success': False, 'error': 'Incorrect password.'}), 401

            token = str(uuid.uuid4())
            ACTIVE_TOKENS[token] = {
                'user_type': 'student',
                'user_data': student.to_dict(),
                'created_at': datetime.now().isoformat()
            }
            return jsonify({
                'success': True,
                'token': token,
                'user_type': 'student',
                'user_data': student.to_dict()
            })
        finally:
            db.close()

    return jsonify({'success': False, 'error': 'Invalid login type. Use "staff" or "student".'}), 400


@app.route('/api/auth/login-face', methods=['POST'])
def login_face():
    """Handle student login via face recognition."""
    data = request.json or {}
    roll_number = data.get('roll_number', '').strip().upper()
    image_data = data.get('image')

    if not roll_number:
        return jsonify({'success': False, 'error': 'Roll number is required.'}), 400
    if not image_data:
        return jsonify({'success': False, 'error': 'No face image captured.'}), 400

    db = get_db()
    try:
        student = db.query(Student).filter(Student.roll_number == roll_number).first()
        if not student:
            return jsonify({'success': False, 'error': f'Student with Roll Number "{roll_number}" not found.'}), 404

        frame = decode_image(image_data)
        if frame is None:
            return jsonify({'success': False, 'error': 'Invalid image format.'}), 400

        embedding, bbox = detector.preprocess_for_training(frame)
        if embedding is None:
            return jsonify({'success': False, 'error': 'No face detected. Please ensure clear lighting and try again.'}), 400

        embeddings = db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student.id).all()
        if not embeddings:
            return jsonify({'success': False, 'error': f'No registered face photos found for {student.name}. Please contact admin.'}), 400

        max_similarity = -1.0
        for emb_record in embeddings:
            stored_emb = np.frombuffer(emb_record.embedding, dtype=np.float32)
            dot_product = np.dot(embedding, stored_emb)
            norm_a = np.linalg.norm(embedding)
            norm_b = np.linalg.norm(stored_emb)
            similarity = dot_product / (norm_a * norm_b) if (norm_a > 0 and norm_b > 0) else 0.0
            if similarity > max_similarity:
                max_similarity = similarity

        THRESHOLD = 0.55
        verified = bool(max_similarity >= THRESHOLD)

        if not verified:
            confidence_pct = round(max_similarity * 100, 1)
            return jsonify({'success': False, 'error': f'Face verification failed ({confidence_pct}% match). Please try again.'}), 401

        # Successful login, generate token
        token = str(uuid.uuid4())
        ACTIVE_TOKENS[token] = {
            'user_type': 'student',
            'user_data': student.to_dict(),
            'created_at': datetime.now().isoformat()
        }
        return jsonify({
            'success': True,
            'token': token,
            'user_type': 'student',
            'user_data': student.to_dict()
        })
    finally:
        db.close()



@app.route('/api/auth/verify-smile', methods=['POST'])
def verify_smile():
    """Check if the captured face image contains a smile using Haar cascade."""
    data = request.json or {}
    image_data = data.get('image')
    if not image_data:
        return jsonify({'error': 'No image provided.'}), 400

    frame = decode_image(image_data)
    if frame is None:
        return jsonify({'error': 'Invalid image.'}), 400

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    # Detect face first
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))

    if len(faces) == 0:
        return jsonify({'smile_detected': False, 'message': 'No face detected. Please look at the camera.'})

    # Check for smile in the largest face region
    x, y, w, h = max(faces.tolist(), key=lambda b: b[2] * b[3])
    face_roi = gray[y:y+h, x:x+w]

    smile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_smile.xml')
    smiles = smile_cascade.detectMultiScale(
        face_roi,
        scaleFactor=1.7,
        minNeighbors=22,
        minSize=(25, 25)
    )

    smile_detected = len(smiles) > 0
    return jsonify({
        'smile_detected': smile_detected,
        'message': '😊 Smile detected!' if smile_detected else 'No smile detected. Please smile naturally.'
    })


@app.route('/api/auth/register-portal', methods=['POST'])
def register_portal():
    """
    Unified student self-registration endpoint.
    Accepts JSON body with personal details, 5 face images (base64), and document files.
    """
    db = get_db()
    try:
        # Parse form data (multipart)
        name = request.form.get('name', '').strip()
        roll_number = request.form.get('roll_number', '').strip().upper()
        department = request.form.get('department', '').strip()
        password = request.form.get('password', '')

        if not all([name, roll_number, department, password]):
            return jsonify({'error': 'Name, roll number, department, and password are required.'}), 400

        # Check duplicate
        existing = db.query(Student).filter(Student.roll_number == roll_number).first()
        if existing:
            return jsonify({'error': f'Roll number {roll_number} is already registered.'}), 409

        # Hash password
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()

        # Create student record
        student = Student(
            name=name,
            roll_number=roll_number,
            department=department,
            password=pwd_hash
        )
        db.add(student)
        db.flush()  # get auto ID

        # Save face images directory
        student_dir = os.path.join(KNOWN_FACES_DIR, str(student.id))
        os.makedirs(student_dir, exist_ok=True)
        student.photo_dir = student_dir

        # Process 5 face images (sent as form fields face_0 .. face_4)
        saved_faces = 0
        face_labels = ['front_neutral', 'front_smile', 'left', 'right', 'tilt_up']
        for i in range(5):
            face_data = request.form.get(f'face_{i}')
            if not face_data:
                continue
            try:
                frame = decode_image(face_data)
                if frame is None:
                    continue
                embedding, bbox = detector.preprocess_for_training(frame)
                if embedding is None:
                    continue

                # Save image
                img_path = os.path.join(student_dir, f'face_{face_labels[i]}.jpg')
                cv2.imwrite(img_path, frame)

                # Save embedding
                embedding_bytes = embedding.astype(np.float32).tobytes()
                face_emb = FaceEmbedding(student_id=student.id, embedding=embedding_bytes)
                db.add(face_emb)
                saved_faces += 1
            except Exception as e:
                print(f"[RegisterPortal] Error processing face_{i}: {e}")

        if saved_faces == 0:
            db.rollback()
            import shutil
            shutil.rmtree(student_dir, ignore_errors=True)
            return jsonify({'error': 'No valid face images detected. Please ensure good lighting and try again.'}), 400

        # Process document uploads (marksheet, id_card)
        for doc_field, attr_name in [('marksheet', 'marksheet_path'), ('id_card', 'id_card_path')]:
            doc_file = request.files.get(doc_field)
            if doc_file and doc_file.filename:
                safe_name = f"{student.id}_{doc_field}_{doc_file.filename}"
                doc_path = os.path.join(UPLOAD_DIR, safe_name)
                doc_file.save(doc_path)
                setattr(student, attr_name, doc_path)

        # Generate QR code
        generate_student_qr(student.id, student.roll_number)

        db.commit()
        return jsonify({
            'success': True,
            'message': f'Student {name} registered successfully with {saved_faces} face photo(s).',
            'student': student.to_dict(),
            'saved_faces': saved_faces
        })
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()



def decode_image(data_url):
    """Decode a base64 data URL to an OpenCV BGR frame."""
    header, encoded = data_url.split(',', 1)
    image_bytes = base64.b64decode(encoded)
    nparr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return frame

def encode_image(frame):
    """Encode an OpenCV frame to base64 JPEG data URL."""
    _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    encoded = base64.b64encode(buffer).decode('utf-8')
    return f'data:image/jpeg;base64,{encoded}'


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────
@app.route('/api/dashboard', methods=['GET'])
def dashboard():
    db = get_db()
    try:
        total_students = db.query(Student).count()
        today = datetime.now().strftime('%Y-%m-%d')
        today_records = db.query(Attendance).filter(Attendance.date == today).all()
        present_today = len(set(r.student_id for r in today_records))

        # Last 7 days attendance trend
        from sqlalchemy import func
        trend = db.query(
            Attendance.date,
            func.count(func.distinct(Attendance.student_id)).label('count')
        ).group_by(Attendance.date).order_by(Attendance.date.desc()).limit(7).all()

        trend_data = [{'date': t.date, 'count': t.count} for t in reversed(trend)]

        # Department distribution
        dept_data = {}
        students = db.query(Student).all()
        for s in students:
            dept_data[s.department] = dept_data.get(s.department, 0) + 1

        model_trained = recognizer.is_trained

        return jsonify({
            'total_students': total_students,
            'present_today': present_today,
            'attendance_rate': round((present_today / total_students * 100) if total_students > 0 else 0, 1),
            'model_trained': model_trained,
            'num_classes': recognizer.get_num_classes(),
            'subjects': SUBJECTS,
            'trend': trend_data,
            'departments': dept_data
        })
    finally:
        db.close()


# ─────────────────────────────────────────────
# STUDENTS
# ─────────────────────────────────────────────
@app.route('/api/students', methods=['GET'])
def get_students():
    db = get_db()
    try:
        students = db.query(Student).all()
        return jsonify([s.to_dict() for s in students])
    finally:
        db.close()


@app.route('/api/students/<int:student_id>', methods=['DELETE'])
def delete_student(student_id):
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return jsonify({'error': 'Student not found'}), 404

        # Remove face images folder
        import shutil
        if student.photo_dir and os.path.exists(student.photo_dir):
            shutil.rmtree(student.photo_dir, ignore_errors=True)

        db.delete(student)
        db.commit()
        return jsonify({'message': 'Student deleted successfully'})
    finally:
        db.close()


# ─────────────────────────────────────────────
# REGISTRATION
# ─────────────────────────────────────────────
@app.route('/api/register', methods=['POST'])
def register_student():
    db = get_db()
    try:
        data = request.json
        name = data.get('name', '').strip()
        roll_number = data.get('roll_number', '').strip()
        department = data.get('department', '').strip()
        images = data.get('images', [])  # List of base64 data URLs

        if not all([name, roll_number, department]):
            return jsonify({'error': 'Name, roll number, and department are required.'}), 400

        if len(images) < 3:
            return jsonify({'error': 'At least 3 face photos are required.'}), 400

        # Check duplicate roll number
        existing = db.query(Student).filter(Student.roll_number == roll_number).first()
        if existing:
            return jsonify({'error': f'Roll number {roll_number} already registered.'}), 409

        # Save student to DB first to get ID
        student = Student(name=name, roll_number=roll_number, department=department)
        db.add(student)
        db.flush()  # Get auto-generated ID

        # Save face images
        student_dir = os.path.join(KNOWN_FACES_DIR, str(student.id))
        os.makedirs(student_dir, exist_ok=True)
        student.photo_dir = student_dir

        saved_count = 0
        for idx, img_data in enumerate(images):
            try:
                frame = decode_image(img_data)
                if frame is None:
                    continue
                # Verify a face is detectable and extract embedding
                embedding, bbox = detector.preprocess_for_training(frame)
                if embedding is not None:
                    img_path = os.path.join(student_dir, f'face_{idx+1}.jpg')
                    cv2.imwrite(img_path, frame)

                    # Store face embedding in DB
                    embedding_bytes = embedding.astype(np.float32).tobytes()
                    face_emb = FaceEmbedding(student_id=student.id, embedding=embedding_bytes)
                    db.add(face_emb)

                    saved_count += 1
            except Exception as e:
                print(f"Error saving image {idx}: {e}")

        if saved_count == 0:
            db.rollback()
            import shutil
            shutil.rmtree(student_dir, ignore_errors=True)
            return jsonify({'error': 'No valid face images detected. Please retake photos.'}), 400

        # Generate QR Code
        generate_student_qr(student.id, student.roll_number)

        db.commit()
        return jsonify({
            'message': f'Student {name} registered successfully with {saved_count} face images.',
            'student': student.to_dict(),
            'saved_images': saved_count
        })
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
# ENROLL FACE FOR EXISTING STUDENT
# ─────────────────────────────────────────────
@app.route('/api/students/enroll-face', methods=['POST'])
def enroll_face():
    db = get_db()
    try:
        data = request.json
        roll_number = data.get('roll_number', '').strip().upper()
        images = data.get('images', [])

        if not roll_number:
            return jsonify({'error': 'Roll number is required.'}), 400
        if not images:
            return jsonify({'error': 'At least one face photo is required.'}), 400

        # Find existing student (case-insensitive)
        student = db.query(Student).filter(
            Student.roll_number == roll_number
        ).first()
        if not student:
            return jsonify({'error': f'Student with roll number "{roll_number}" not found. Please register the student first.'}), 404

        # Ensure photo directory exists
        student_dir = os.path.join(KNOWN_FACES_DIR, str(student.id))
        os.makedirs(student_dir, exist_ok=True)
        if not student.photo_dir or not os.path.isdir(student.photo_dir):
            student.photo_dir = student_dir

        # Count existing embeddings to continue numbering
        existing_emb_count = db.query(FaceEmbedding).filter(
            FaceEmbedding.student_id == student.id
        ).count()

        saved_count = 0
        errors = []
        for idx, img_data in enumerate(images):
            try:
                frame = decode_image(img_data)
                if frame is None:
                    errors.append(f'Image {idx+1}: could not decode.')
                    continue

                embedding, bbox = detector.preprocess_for_training(frame)
                if embedding is None:
                    errors.append(f'Image {idx+1}: no face detected.')
                    continue

                img_path = os.path.join(student_dir, f'face_{existing_emb_count + saved_count + 1}.jpg')
                cv2.imwrite(img_path, frame)

                embedding_bytes = embedding.astype(np.float32).tobytes()
                face_emb = FaceEmbedding(student_id=student.id, embedding=embedding_bytes)
                db.add(face_emb)
                saved_count += 1
            except Exception as e:
                errors.append(f'Image {idx+1}: {str(e)}')

        if saved_count == 0:
            db.rollback()
            return jsonify({
                'error': 'No valid face images detected in any of the uploads.',
                'details': errors
            }), 400

        # Generate / refresh QR code
        generate_student_qr(student.id, student.roll_number)

        db.commit()
        total_embeddings = existing_emb_count + saved_count
        return jsonify({
            'message': f'Successfully enrolled {saved_count} face photo(s) for {student.name}. Total embeddings: {total_embeddings}.',
            'student': student.to_dict(),
            'saved_images': saved_count,
            'total_embeddings': total_embeddings,
            'warnings': errors
        })
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
# QR CODE SERVING
# ─────────────────────────────────────────────
@app.route('/api/students/<int:student_id>/qrcode', methods=['GET'])
def get_student_qrcode(student_id):
    qrcodes_dir = os.path.join(BASE_DIR, 'data', 'qrcodes')
    filename = f"{student_id}.png"
    filepath = os.path.join(qrcodes_dir, filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype='image/png')
    
    # Generate it dynamically if missing but student exists
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if student:
            generate_student_qr(student.id, student.roll_number)
            if os.path.exists(filepath):
                return send_file(filepath, mimetype='image/png')
    finally:
        db.close()
    return jsonify({'error': 'QR Code not found'}), 404


# ─────────────────────────────────────────────
# BULK REGISTRATION (GOOGLE FORM)
# ─────────────────────────────────────────────
@app.route('/api/register/bulk', methods=['POST'])
def register_bulk():
    db = get_db()
    try:
        csv_file = request.files.get('csv')
        zip_file = request.files.get('zip')

        if not csv_file:
            return jsonify({'error': 'Google Form CSV file is required.'}), 400

        # Read CSV file
        csv_stream = csv_file.stream.read().decode('utf-8', errors='ignore')
        csv_reader = csv.reader(StringIO(csv_stream))
        header = next(csv_reader, None)

        if not header:
            return jsonify({'error': 'CSV file is empty.'}), 400

        # Case-insensitive header matching
        idx_name = -1
        idx_roll = -1
        idx_dept = -1

        for i, col in enumerate(header):
            col_lower = col.strip().lower()
            if 'name' in col_lower or 'username' in col_lower:
                idx_name = i
            elif 'roll' in col_lower or 'id' in col_lower or 'registration' in col_lower:
                idx_roll = i
            elif 'dept' in col_lower or 'branch' in col_lower or 'course' in col_lower or 'department' in col_lower:
                idx_dept = i

        # Fallback to defaults if not matched by text
        if idx_name == -1 or idx_roll == -1 or idx_dept == -1:
            if len(header) >= 3:
                if idx_name == -1: idx_name = 0
                if idx_roll == -1: idx_roll = 1
                if idx_dept == -1: idx_dept = 2
            else:
                return jsonify({'error': 'Unable to identify Name, Roll Number, or Department columns in CSV.'}), 400

        # Parse ZIP file if present
        zip_archive = None
        if zip_file:
            zip_archive = zipfile.ZipFile(BytesIO(zip_file.read()))

        results = []
        imported_count = 0
        skipped_count = 0

        # Process rows
        for row in csv_reader:
            if not row or len(row) <= max(idx_name, idx_roll, idx_dept):
                continue

            name = row[idx_name].strip()
            roll_number = row[idx_roll].strip()
            department = row[idx_dept].strip()

            if not all([name, roll_number, department]):
                skipped_count += 1
                continue

            # Check duplicate roll number
            existing = db.query(Student).filter(Student.roll_number == roll_number).first()
            if existing:
                skipped_count += 1
                continue

            # Save student to DB to get ID
            student = Student(name=name, roll_number=roll_number, department=department)
            db.add(student)
            db.flush()

            student_dir = os.path.join(KNOWN_FACES_DIR, str(student.id))
            os.makedirs(student_dir, exist_ok=True)
            student.photo_dir = student_dir

            saved_count = 0

            # Find matching photos in zip
            if zip_archive:
                for file_info in zip_archive.infolist():
                    filename = os.path.basename(file_info.filename)
                    if not filename or file_info.is_dir():
                        continue
                    
                    filename_lower = filename.lower()
                    roll_lower = roll_number.lower()
                    
                    # Match filenames containing the roll number (e.g. CS2021001_1.jpg)
                    if roll_lower in filename_lower and filename_lower.endswith(('.jpg', '.jpeg', '.png')):
                        try:
                            img_data = zip_archive.read(file_info)
                            nparr = np.frombuffer(img_data, np.uint8)
                            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                            if frame is not None:
                                embedding, bbox = detector.preprocess_for_training(frame)
                                if embedding is not None:
                                    img_path = os.path.join(student_dir, f'face_{saved_count+1}.jpg')
                                    cv2.imwrite(img_path, frame)

                                    # Save embedding
                                    embedding_bytes = embedding.astype(np.float32).tobytes()
                                    face_emb = FaceEmbedding(student_id=student.id, embedding=embedding_bytes)
                                    db.add(face_emb)

                                    saved_count += 1
                        except Exception as e:
                            print(f"Error processing ZIP image {filename}: {e}")

            # Generate QR Code
            generate_student_qr(student.id, student.roll_number)

            results.append({
                'name': name,
                'roll_number': roll_number,
                'department': department,
                'photos_imported': saved_count
            })
            imported_count += 1

        db.commit()
        return jsonify({
            'message': f'Bulk registration completed successfully. {imported_count} student(s) imported, {skipped_count} skipped.',
            'imported': imported_count,
            'skipped': skipped_count,
            'details': results
        })

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
# 1:1 FACE VERIFICATION & ATTENDANCE MARKING
# ─────────────────────────────────────────────
@app.route('/api/attendance/verify', methods=['POST'])
def verify_attendance():
    db = get_db()
    try:
        data = request.json
        roll_number = data.get('roll_number', '').strip()
        image_data = data.get('image')
        subject = data.get('subject', 'General')

        if not roll_number:
            return jsonify({'error': 'Roll number is required'}), 400

        if not image_data:
            return jsonify({'error': 'No image provided'}), 400

        # Find student by roll number
        student = db.query(Student).filter(Student.roll_number == roll_number).first()
        if not student:
            return jsonify({'error': f'Student with Roll Number "{roll_number}" not found.'}), 404

        # Decode frame
        frame = decode_image(image_data)
        if frame is None:
            return jsonify({'error': 'Invalid image.'}), 400

        # Detect face and extract embedding
        embedding, bbox = detector.preprocess_for_training(frame)
        if embedding is None:
            return jsonify({'error': 'No face detected in camera. Please look directly at the camera.'}), 400

        # Retrieve registered embeddings
        embeddings = db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student.id).all()
        if not embeddings:
            return jsonify({'error': f'No registered face photos found for {student.name}. Please upload photos first.'}), 400

        # Compare embeddings using Cosine Similarity
        max_similarity = -1.0
        for emb_record in embeddings:
            stored_emb = np.frombuffer(emb_record.embedding, dtype=np.float32)
            dot_product = np.dot(embedding, stored_emb)
            norm_a = np.linalg.norm(embedding)
            norm_b = np.linalg.norm(stored_emb)
            similarity = dot_product / (norm_a * norm_b) if (norm_a > 0 and norm_b > 0) else 0.0
            if similarity > max_similarity:
                max_similarity = similarity

        # Verification Threshold (Cosine Similarity threshold)
        THRESHOLD = 0.55
        verified = bool(max_similarity >= THRESHOLD)

        confidence_pct = float(round(max_similarity * 100, 1))

        # Mark attendance if verified
        already_marked = False
        today = datetime.now().strftime('%Y-%m-%d')
        now_time = datetime.now().strftime('%H:%M:%S')

        if verified:
            # Check for duplicate record
            existing = db.query(Attendance).filter(
                Attendance.student_id == student.id,
                Attendance.subject == subject,
                Attendance.date == today
            ).first()

            if not existing:
                record = Attendance(
                    student_id=student.id,
                    subject=subject,
                    date=today,
                    time=now_time,
                    status='Present',
                    confidence=str(confidence_pct)
                )
                db.add(record)
                db.commit()
            else:
                already_marked = True

        # Draw box and label for feedback image
        annotated = frame.copy()
        color = (0, 255, 100) if verified else (0, 60, 255)
        x, y, w, h = bbox
        cv2.rectangle(annotated, (x, y), (x+w, y+h), color, 2)
        label = f"{student.name} ({confidence_pct}%)" if verified else f"Not Verified ({confidence_pct}%)"
        cv2.putText(annotated, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        return jsonify({
            'verified': verified,
            'confidence': confidence_pct,
            'already_marked': already_marked,
            'student': student.to_dict(),
            'annotated_image': encode_image(annotated),
            'subject': subject,
            'time': now_time
        })

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
# DISTRIBUTED QR ATTENDANCE SESSIONS
# ─────────────────────────────────────────────

@app.route('/api/session/start', methods=['POST'])
def start_session():
    try:
        data = request.json
        subject = data.get('subject', '').strip()
        if not subject:
            return jsonify({'error': 'Subject is required'}), 400

        # Generate token
        import time
        token_1 = str(uuid.uuid4())
        token_2 = str(uuid.uuid4())
        today = datetime.now().strftime('%Y-%m-%d')
        ACTIVE_SESSIONS[subject] = {
            'token_1': token_1,
            'token_2': token_2,
            'start_timestamp': time.time(),
            'date': today,
            'expired_and_processed': False
        }
        token = token_1

        # Construct URL for student portal
        ngrok_url = get_ngrok_url()
        import urllib.parse
        if ngrok_url:
            student_url = f"{ngrok_url}/student.html?token={token}&subject={urllib.parse.quote(subject)}"
        else:
            host = request.host
            if "127.0.0.1" in host or "localhost" in host:
                ip = get_local_ip()
                host = host.replace("127.0.0.1", ip).replace("localhost", ip)
            scheme = request.scheme
            student_url = f"{scheme}://{host}/student.html?token={token}&subject={urllib.parse.quote(subject)}"


        
        # Generate QR Code image encoding the URL
        qr = qrcode.QRCode(version=1, box_size=8, border=4)
        qr.add_data(student_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Save to buffer
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        qr_data_url = f"data:image/png;base64,{qr_base64}"

        return jsonify({
            'success': True,
            'token': token,
            'subject': subject,
            'qr_code': qr_data_url,
            'url': student_url
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/session/status', methods=['GET'])
def session_status():
    db = get_db()
    try:
        subject = request.args.get('subject', '').strip()
        if not subject:
            return jsonify({'error': 'Subject is required'}), 400

        # Check if there is an active session
        session_info = ACTIVE_SESSIONS.get(subject)
        if session_info:
            import time
            elapsed = time.time() - session_info.get('start_timestamp', 0)
            if elapsed >= 60:
                # Trigger auto-end if it's a class session
                session_id = session_info.get('session_id')
                if session_id and not session_info.get('expired_and_processed', False):
                    session_info['expired_and_processed'] = True
                    try:
                        auto_end_session_helper(session_id)
                    except Exception as e:
                        print(f"Error auto-ending session: {e}")
                ACTIVE_SESSIONS.pop(subject, None)
                session_info = None

        if not session_info:
            return jsonify({'active': False, 'present': []})

        # Get today's attendance records for this subject
        today = datetime.now().strftime('%Y-%m-%d')
        records = db.query(Attendance).join(Student).filter(
            Attendance.subject == subject,
            Attendance.date == today
        ).order_by(Attendance.time.desc()).all()

        present_list = [{
            'id': r.student.id,
            'name': r.student.name,
            'roll_number': r.student.roll_number,
            'department': r.student.department,
            'time': r.time
        } for r in records]

        return jsonify({
            'active': True,
            'subject': subject,
            'count': len(present_list),
            'present': present_list
        })
    finally:
        db.close()


@app.route('/api/attendance/student/verify', methods=['POST'])
def verify_student_attendance():
    db = get_db()
    try:
        data = request.json
        roll_number = data.get('roll_number', '').strip()
        image_data = data.get('image')
        token = data.get('token', '').strip()
        subject = data.get('subject', '').strip()

        if not all([roll_number, image_data, token, subject]):
            return jsonify({'error': 'Roll number, image, token, and subject are required.'}), 400

        # Validate Session Token
        session_info = ACTIVE_SESSIONS.get(subject)
        if not session_info:
            return jsonify({'error': 'Invalid, expired, or inactive attendance QR Code. Please scan the latest QR Code.'}), 400

        import time
        elapsed = time.time() - session_info.get('start_timestamp', 0)

        valid = False
        if session_info.get('token_1') and session_info.get('token_2'):
            if elapsed < 30:
                if token == session_info.get('token_1'):
                    valid = True
            elif elapsed < 60:
                if token == session_info.get('token_2'):
                    valid = True
        else:
            # Backwards compatibility check
            if token == session_info.get('token'):
                valid = True

        if not valid:
            return jsonify({'error': 'Invalid, expired, or inactive attendance QR Code. Please scan the latest QR Code.'}), 400

        # Lookup Student
        student = db.query(Student).filter(Student.roll_number == roll_number).first()
        if not student:
            return jsonify({'error': f'Student with Roll Number "{roll_number}" is not registered in the database.'}), 404

        # Decode Image
        frame = decode_image(image_data)
        if frame is None:
            return jsonify({'error': 'Invalid image capture.'}), 400

        # Detect Face and extract embedding
        embedding, bbox = detector.preprocess_for_training(frame)
        if embedding is None:
            return jsonify({'error': 'No face detected. Please look straight into your front camera with good lighting.'}), 400

        # Retrieve Registered Embeddings
        embeddings = db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student.id).all()
        if not embeddings:
            return jsonify({'error': f'No registered face photos found in database for {student.name}. Please contact admin to upload photos.'}), 400

        # Compare Embeddings
        max_similarity = -1.0
        for emb_record in embeddings:
            stored_emb = np.frombuffer(emb_record.embedding, dtype=np.float32)
            dot_product = np.dot(embedding, stored_emb)
            norm_a = np.linalg.norm(embedding)
            norm_b = np.linalg.norm(stored_emb)
            similarity = dot_product / (norm_a * norm_b) if (norm_a > 0 and norm_b > 0) else 0.0
            if similarity > max_similarity:
                max_similarity = similarity

        THRESHOLD = 0.55
        verified = bool(max_similarity >= THRESHOLD)
        confidence_pct = float(round(max_similarity * 100, 1))

        if not verified:
            return jsonify({
                'verified': False,
                'error': f'Face verification failed ({confidence_pct}% match). Please ensure you look straight at the camera and try again.'
            }), 400

        # Mark Attendance
        today = datetime.now().strftime('%Y-%m-%d')
        now_time = datetime.now().strftime('%H:%M:%S')

        # Check duplicate
        existing = db.query(Attendance).filter(
            Attendance.student_id == student.id,
            Attendance.subject == subject,
            Attendance.date == today
        ).first()

        already_marked = False
        if not existing:
            class_session_id = session_info.get('session_id')
            record = Attendance(
                student_id=student.id,
                subject=subject,
                date=today,
                time=now_time,
                status='Present',
                confidence=str(confidence_pct),
                class_session_id=class_session_id
            )
            db.add(record)

            # Apply +1% attendance percentage
            old_pct = student.attendance_percentage or 75.0
            new_pct = min(100.0, old_pct + 1.0)
            student.attendance_percentage = new_pct

            # Log the change
            if class_session_id:
                log = AttendancePercentageLog(
                    student_id=student.id,
                    subject_id=session_info.get('subject_id') or 0,
                    old_percentage=old_pct,
                    new_percentage=new_pct,
                    change_type='+1',
                    class_session_id=class_session_id
                )
                db.add(log)
            db.commit()
        else:
            already_marked = True

        return jsonify({
            'verified': True,
            'already_marked': already_marked,
            'student': student.to_dict(),
            'confidence': confidence_pct,
            'subject': subject,
            'time': now_time
        })

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/attendance/student/session-checkin', methods=['POST'])
def session_checkin():
    """Mark attendance immediately for session QR code (since student already authenticated via face login)."""
    db = get_db()
    try:
        data = request.json or {}
        roll_number = data.get('roll_number', '').strip().upper()
        token = data.get('token', '').strip()
        subject = data.get('subject', '').strip()

        if not all([roll_number, token, subject]):
            return jsonify({'error': 'Roll number, session token, and subject are required.'}), 400

        # Validate Session Token
        session_info = ACTIVE_SESSIONS.get(subject)
        if not session_info:
            return jsonify({'error': 'Invalid, expired, or inactive attendance QR Code. Please scan the latest QR Code.'}), 400

        import time
        elapsed = time.time() - session_info.get('start_timestamp', 0)

        valid = False
        if session_info.get('token_1') and session_info.get('token_2'):
            if elapsed < 30:
                if token == session_info.get('token_1'):
                    valid = True
            elif elapsed < 60:
                if token == session_info.get('token_2'):
                    valid = True
        else:
            # Backwards compatibility check
            if token == session_info.get('token'):
                valid = True

        if not valid:
            return jsonify({'error': 'Invalid, expired, or inactive attendance QR Code. Please scan the latest QR Code.'}), 400

        # Lookup Student
        student = db.query(Student).filter(Student.roll_number == roll_number).first()
        if not student:
            return jsonify({'error': f'Student with Roll Number "{roll_number}" is not registered in the database.'}), 404

        # Mark Attendance immediately without face verification
        today = datetime.now().strftime('%Y-%m-%d')
        now_time = datetime.now().strftime('%H:%M:%S')

        # Check duplicate
        existing = db.query(Attendance).filter(
            Attendance.student_id == student.id,
            Attendance.subject == subject,
            Attendance.date == today
        ).first()

        already_marked = False
        if not existing:
            class_session_id = session_info.get('session_id')
            record = Attendance(
                student_id=student.id,
                subject=subject,
                date=today,
                time=now_time,
                status='Present',
                confidence='100.0',
                class_session_id=class_session_id
            )
            db.add(record)

            # Apply +1% attendance percentage
            old_pct = student.attendance_percentage or 75.0
            new_pct = min(100.0, old_pct + 1.0)
            student.attendance_percentage = new_pct

            # Log the change
            if class_session_id:
                log = AttendancePercentageLog(
                    student_id=student.id,
                    subject_id=session_info.get('subject_id') or 0,
                    old_percentage=old_pct,
                    new_percentage=new_pct,
                    change_type='+1',
                    class_session_id=class_session_id
                )
                db.add(log)
            db.commit()
        else:
            already_marked = True

        return jsonify({
            'verified': True,
            'already_marked': already_marked,
            'student': student.to_dict(),
            'confidence': 100.0,
            'subject': subject,
            'time': now_time
        })

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/attendance/mark-by-qr', methods=['POST'])
def mark_by_qr():
    """Mark attendance immediately when teacher scans student's personal QR code (no face verification required)."""
    db = get_db()
    try:
        data = request.json or {}
        roll_number = data.get('roll_number', '').strip().upper()
        subject = data.get('subject', 'General').strip()

        if not roll_number:
            return jsonify({'error': 'Roll number is required.'}), 400

        # Lookup Student
        student = db.query(Student).filter(Student.roll_number == roll_number).first()
        if not student:
            return jsonify({'error': f'Student with Roll Number "{roll_number}" is not registered in the database.'}), 404

        # Mark Attendance
        today = datetime.now().strftime('%Y-%m-%d')
        now_time = datetime.now().strftime('%H:%M:%S')

        # Check duplicate
        existing = db.query(Attendance).filter(
            Attendance.student_id == student.id,
            Attendance.subject == subject,
            Attendance.date == today
        ).first()

        already_marked = False
        if not existing:
            record = Attendance(
                student_id=student.id,
                subject=subject,
                date=today,
                time=now_time,
                status='Present',
                confidence='100.0'
            )
            db.add(record)
            db.commit()
        else:
            already_marked = True

        return jsonify({
            'verified': True,
            'already_marked': already_marked,
            'student': student.to_dict(),
            'confidence': 100.0,
            'subject': subject,
            'time': now_time
        })

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()



# ─────────────────────────────────────────────
# TRAINING
# ─────────────────────────────────────────────
@app.route('/api/train', methods=['POST'])
def train():
    try:
        success, message, details = train_model()
        # Reload recognizer after training
        global recognizer
        recognizer = InsightFaceRecognizer()
        return jsonify({
            'success': success,
            'message': message,
            'details': details
        }), (200 if success else 400)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ─────────────────────────────────────────────
# ATTENDANCE CAPTURE
# ─────────────────────────────────────────────
@app.route('/api/attendance/capture', methods=['POST'])
def capture_attendance():
    db = get_db()
    try:
        data = request.json
        image_data = data.get('image')
        subject = data.get('subject', 'General')

        if not image_data:
            return jsonify({'error': 'No image provided'}), 400

        if not recognizer.is_trained:
            return jsonify({'error': 'Model not trained yet. Please train the model first.'}), 400

        frame = decode_image(image_data)
        if frame is None:
            return jsonify({'error': 'Invalid image'}), 400

        faces = detector.detect_faces(frame)
        results = []

        for bbox in faces:
            x, y, w, h = bbox
            embedding = detector.extract_embedding(frame, bbox)
            if embedding is None:
                results.append({
                    'bbox': bbox,
                    'recognized': False,
                    'name': 'Unknown',
                    'confidence': 0.0
                })
                continue
            student_id_str, confidence = recognizer.predict(embedding)

            if student_id_str is None:
                results.append({
                    'bbox': bbox,
                    'recognized': False,
                    'name': 'Unknown',
                    'confidence': round(confidence * 100, 1)
                })
                continue

            try:
                student_id = int(student_id_str)
            except ValueError:
                continue

            student = db.query(Student).filter(Student.id == student_id).first()
            if not student:
                continue

            today = datetime.now().strftime('%Y-%m-%d')
            now_time = datetime.now().strftime('%H:%M:%S')

            # Avoid duplicate attendance for same student/subject/date
            existing = db.query(Attendance).filter(
                Attendance.student_id == student_id,
                Attendance.subject == subject,
                Attendance.date == today
            ).first()

            if not existing:
                record = Attendance(
                    student_id=student_id,
                    subject=subject,
                    date=today,
                    time=now_time,
                    status='Present',
                    confidence=str(round(confidence * 100, 1))
                )
                db.add(record)
                db.commit()
                already_marked = False
            else:
                already_marked = True

            results.append({
                'bbox': bbox,
                'recognized': True,
                'student_id': student_id,
                'name': student.name,
                'roll_number': student.roll_number,
                'department': student.department,
                'confidence': round(confidence * 100, 1),
                'already_marked': already_marked,
                'subject': subject,
                'time': now_time
            })

        # Draw bounding boxes on frame
        annotated = frame.copy()
        for r in results:
            x, y, w, h = r['bbox']
            color = (0, 255, 100) if r['recognized'] else (0, 60, 255)
            cv2.rectangle(annotated, (x, y), (x+w, y+h), color, 2)
            label = f"{r['name']} ({r['confidence']}%)" if r['recognized'] else 'Unknown'
            cv2.putText(annotated, label, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        return jsonify({
            'faces_detected': len(faces),
            'results': results,
            'annotated_image': encode_image(annotated)
        })
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
# ATTENDANCE RECORDS
# ─────────────────────────────────────────────
@app.route('/api/attendance/records', methods=['GET'])
def get_records():
    db = get_db()
    try:
        date_filter = request.args.get('date')
        subject_filter = request.args.get('subject')
        dept_filter = request.args.get('department')
        student_id_filter = request.args.get('student_id')

        query = db.query(Attendance).join(Student)

        if date_filter:
            query = query.filter(Attendance.date == date_filter)
        if subject_filter and subject_filter != 'All':
            query = query.filter(Attendance.subject == subject_filter)
        if dept_filter and dept_filter != 'All':
            query = query.filter(Student.department == dept_filter)
        if student_id_filter:
            query = query.filter(Attendance.student_id == int(student_id_filter))

        records = query.order_by(Attendance.date.desc(), Attendance.time.desc()).all()
        return jsonify([r.to_dict() for r in records])
    finally:
        db.close()


@app.route('/api/attendance/export', methods=['GET'])
def export_attendance():
    db = get_db()
    try:
        records = db.query(Attendance).join(Student).order_by(
            Attendance.date.desc(), Attendance.time.desc()).all()

        rows = [r.to_dict() for r in records]
        df = pd.DataFrame(rows)
        if df.empty:
            df = pd.DataFrame(columns=['id', 'student_name', 'roll_number',
                                        'department', 'subject', 'date', 'time', 'status', 'confidence'])

        output = StringIO()
        df.to_csv(output, index=False)
        output.seek(0)

        return send_file(
            BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'attendance_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
    finally:
        db.close()


# ─────────────────────────────────────────────
# SUBJECTS (legacy – returns hardcoded list)
# ─────────────────────────────────────────────
@app.route('/api/subjects', methods=['GET'])
def get_subjects():
    return jsonify(SUBJECTS)


# ═════════════════════════════════════════════
#  COLLEGE MANAGEMENT SYSTEM — NEW ROUTES
# ═════════════════════════════════════════════


# ─────────────────────────────────────────────
# LECTURER MANAGEMENT
# ─────────────────────────────────────────────
@app.route('/api/lecturers', methods=['POST'])
def create_lecturer():
    """Create a new lecturer."""
    db = get_db()
    try:
        data = request.json or {}
        name = data.get('name', '').strip()
        employee_id = data.get('employee_id', '').strip().upper()
        department = data.get('department', '').strip()
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')

        if not all([name, employee_id, department]):
            return jsonify({'error': 'Name, employee ID, and department are required.'}), 400

        existing = db.query(Lecturer).filter(Lecturer.employee_id == employee_id).first()
        if existing:
            return jsonify({'error': f'Employee ID {employee_id} already exists.'}), 409

        pwd_hash = hashlib.sha256(password.encode()).hexdigest() if password else hashlib.sha256(employee_id.encode()).hexdigest()

        lecturer = Lecturer(
            name=name,
            employee_id=employee_id,
            department=department,
            phone=phone or None,
            email=email or None,
            password=pwd_hash
        )
        db.add(lecturer)
        db.commit()
        return jsonify({'success': True, 'lecturer': lecturer.to_dict(), 'message': f'Lecturer {name} created successfully.'})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/lecturers', methods=['GET'])
def get_lecturers():
    """List all lecturers."""
    db = get_db()
    try:
        department = request.args.get('department')
        query = db.query(Lecturer)
        if department and department != 'All':
            query = query.filter(Lecturer.department == department)
        lecturers = query.order_by(Lecturer.name).all()
        return jsonify([l.to_dict() for l in lecturers])
    finally:
        db.close()


@app.route('/api/lecturers/<int:lecturer_id>', methods=['PUT'])
def update_lecturer(lecturer_id):
    """Update a lecturer's details."""
    db = get_db()
    try:
        lecturer = db.query(Lecturer).filter(Lecturer.id == lecturer_id).first()
        if not lecturer:
            return jsonify({'error': 'Lecturer not found.'}), 404

        data = request.json or {}
        if 'name' in data: lecturer.name = data['name'].strip()
        if 'department' in data: lecturer.department = data['department'].strip()
        if 'phone' in data: lecturer.phone = data['phone'].strip() or None
        if 'email' in data: lecturer.email = data['email'].strip() or None
        if 'password' in data and data['password']:
            lecturer.password = hashlib.sha256(data['password'].encode()).hexdigest()

        db.commit()
        return jsonify({'success': True, 'lecturer': lecturer.to_dict()})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/lecturers/<int:lecturer_id>', methods=['DELETE'])
def delete_lecturer(lecturer_id):
    """Delete a lecturer."""
    db = get_db()
    try:
        lecturer = db.query(Lecturer).filter(Lecturer.id == lecturer_id).first()
        if not lecturer:
            return jsonify({'error': 'Lecturer not found.'}), 404
        db.delete(lecturer)
        db.commit()
        return jsonify({'message': f'Lecturer {lecturer.name} deleted successfully.'})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/auth/lecturer-login', methods=['POST'])
def lecturer_login():
    """Authenticate a lecturer."""
    db = get_db()
    try:
        data = request.json or {}
        employee_id = data.get('employee_id', '').strip().upper()
        password = data.get('password', '')

        if not employee_id or not password:
            return jsonify({'success': False, 'error': 'Employee ID and password are required.'}), 400

        lecturer = db.query(Lecturer).filter(Lecturer.employee_id == employee_id).first()
        if not lecturer:
            return jsonify({'success': False, 'error': 'Lecturer not found.'}), 404

        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        if lecturer.password != pwd_hash:
            return jsonify({'success': False, 'error': 'Invalid password.'}), 401

        token = str(uuid.uuid4())
        ACTIVE_TOKENS[token] = {
            'user_type': 'lecturer',
            'user_data': lecturer.to_dict(),
            'created_at': datetime.now().isoformat()
        }
        return jsonify({
            'success': True,
            'token': token,
            'user_type': 'lecturer',
            'user_data': lecturer.to_dict()
        })
    finally:
        db.close()


# ─────────────────────────────────────────────
# SUBJECT MANAGEMENT (database-backed)
# ─────────────────────────────────────────────
@app.route('/api/subjects/list', methods=['GET'])
def list_subjects():
    """List all subjects from database."""
    db = get_db()
    try:
        department = request.args.get('department')
        semester = request.args.get('semester')
        query = db.query(Subject)
        if department and department != 'All':
            query = query.filter(Subject.department == department)
        if semester:
            query = query.filter(Subject.semester == int(semester))
        subjects = query.order_by(Subject.code).all()
        return jsonify([s.to_dict() for s in subjects])
    finally:
        db.close()


@app.route('/api/subjects/list', methods=['POST'])
def create_subject():
    """Create a new subject."""
    db = get_db()
    try:
        data = request.json or {}
        code = data.get('code', '').strip().upper()
        name = data.get('name', '').strip()
        department = data.get('department', '').strip()
        semester = data.get('semester', 1)
        credits = data.get('credits', 3)

        if not all([code, name, department]):
            return jsonify({'error': 'Subject code, name, and department are required.'}), 400

        existing = db.query(Subject).filter(Subject.code == code).first()
        if existing:
            return jsonify({'error': f'Subject code {code} already exists.'}), 409

        subject = Subject(
            code=code, name=name, department=department,
            semester=int(semester), credits=int(credits)
        )
        db.add(subject)
        db.commit()
        return jsonify({'success': True, 'subject': subject.to_dict(), 'message': f'Subject {name} ({code}) created.'})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/subjects/list/<int:subject_id>', methods=['PUT'])
def update_subject(subject_id):
    """Update a subject."""
    db = get_db()
    try:
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if not subject:
            return jsonify({'error': 'Subject not found.'}), 404

        data = request.json or {}
        if 'name' in data: subject.name = data['name'].strip()
        if 'department' in data: subject.department = data['department'].strip()
        if 'semester' in data: subject.semester = int(data['semester'])
        if 'credits' in data: subject.credits = int(data['credits'])

        db.commit()
        return jsonify({'success': True, 'subject': subject.to_dict()})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/subjects/list/<int:subject_id>', methods=['DELETE'])
def delete_subject(subject_id):
    """Delete a subject."""
    db = get_db()
    try:
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if not subject:
            return jsonify({'error': 'Subject not found.'}), 404
        db.delete(subject)
        db.commit()
        return jsonify({'message': f'Subject {subject.name} deleted.'})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
# CLASS SESSION MANAGEMENT
# ─────────────────────────────────────────────
@app.route('/api/class-sessions', methods=['POST'])
def create_class_session():
    """Start a new class session."""
    db = get_db()
    try:
        data = request.json or {}
        subject_id = data.get('subject_id')
        lecturer_id = data.get('lecturer_id')
        topic_covered = data.get('topic_covered', '').strip()
        session_type = data.get('session_type', 'Lecture')

        if not subject_id:
            return jsonify({'error': 'Subject is required.'}), 400

        subject = db.query(Subject).filter(Subject.id == int(subject_id)).first()
        if not subject:
            return jsonify({'error': 'Subject not found.'}), 404

        # Lecturer is optional (admin can also start sessions)
        lecturer = None
        if lecturer_id:
            lecturer = db.query(Lecturer).filter(Lecturer.id == int(lecturer_id)).first()

        today = datetime.now().strftime('%Y-%m-%d')
        now_time = datetime.now().strftime('%H:%M')

        session = ClassSession(
            subject_id=subject.id,
            lecturer_id=lecturer.id if lecturer else 0,
            date=today,
            start_time=now_time,
            topic_covered=topic_covered or None,
            session_type=session_type,
            status='active'
        )
        db.add(session)
        db.commit()

        # Generate QR code check-in URL & token
        import time
        token_1 = str(uuid.uuid4())
        token_2 = str(uuid.uuid4())
        ACTIVE_SESSIONS[subject.name] = {
            'token_1': token_1,
            'token_2': token_2,
            'start_timestamp': time.time(),
            'date': today,
            'session_id': session.id,
            'subject_id': subject.id,
            'expired_and_processed': False
        }

        # Start a background timer to auto-end session and notify absentees after 60s
        import threading
        session_id = session.id
        def deferred_auto_end():
            db_timer = get_db()
            try:
                s = db_timer.query(ClassSession).filter(ClassSession.id == session_id).first()
                if s and s.status == 'active':
                    subject_name_key = None
                    for name_key, info in ACTIVE_SESSIONS.items():
                        if info.get('session_id') == session_id:
                            subject_name_key = name_key
                            if info.get('expired_and_processed', False):
                                # Already processed by client polling, skip
                                return
                            info['expired_and_processed'] = True
                            break
                    if subject_name_key:
                        ACTIVE_SESSIONS.pop(subject_name_key, None)
                    auto_end_session_helper(session_id, db=db_timer)
            except Exception as e:
                print(f"[Timer] Error in deferred auto-end: {e}")
            finally:
                db_timer.close()

        timer = threading.Timer(60.0, deferred_auto_end)
        timer.daemon = True
        timer.start()
        token = token_1

        # Construct URL for student portal
        ngrok_url = get_ngrok_url()
        import urllib.parse
        if ngrok_url:
            student_url = f"{ngrok_url}/student.html?token={token}&subject={urllib.parse.quote(subject.name)}"
        else:
            host = request.host
            if "127.0.0.1" in host or "localhost" in host:
                ip = get_local_ip()
                host = host.replace("127.0.0.1", ip).replace("localhost", ip)
            scheme = request.scheme
            student_url = f"{scheme}://{host}/student.html?token={token}&subject={urllib.parse.quote(subject.name)}"

        # Generate QR Code image encoding the URL
        qr = qrcode.QRCode(version=1, box_size=8, border=4)
        qr.add_data(student_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Save to buffer
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        qr_data_url = f"data:image/png;base64,{qr_base64}"

        return jsonify({
            'success': True,
            'session': session.to_dict(),
            'token': token,
            'qr_code': qr_data_url,
            'url': student_url,
            'message': f'Class session started for {subject.name}.'
        })
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/class-sessions', methods=['GET'])
def get_class_sessions():
    """List class sessions with optional filters."""
    db = get_db()
    try:
        date_filter = request.args.get('date')
        subject_id = request.args.get('subject_id')
        lecturer_id = request.args.get('lecturer_id')
        status = request.args.get('status')

        query = db.query(ClassSession)
        if date_filter:
            query = query.filter(ClassSession.date == date_filter)
        if subject_id:
            query = query.filter(ClassSession.subject_id == int(subject_id))
        if lecturer_id:
            query = query.filter(ClassSession.lecturer_id == int(lecturer_id))
        if status:
            query = query.filter(ClassSession.status == status)

        sessions = query.order_by(ClassSession.date.desc(), ClassSession.start_time.desc()).limit(100).all()
        return jsonify([s.to_dict() for s in sessions])
    finally:
        db.close()


@app.route('/api/class-sessions/<int:session_id>', methods=['GET'])
def get_class_session(session_id):
    """Get a specific class session with attendance details."""
    db = get_db()
    try:
        session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
        if not session:
            return jsonify({'error': 'Session not found.'}), 404

        session_dict = session.to_dict()

        # Check for active token in ACTIVE_SESSIONS
        active_token = None
        qr_number = None
        time_remaining = 0

        session_info = None
        subject_name_key = None
        for name_key, info in ACTIVE_SESSIONS.items():
            if info.get('session_id') == session_id:
                session_info = info
                subject_name_key = name_key
                break

        if session_info and session.status == 'active':
            import time
            elapsed = time.time() - session_info.get('start_timestamp', 0)
            if elapsed >= 60:
                # Auto-expire the session and mark remaining students absent
                if not session_info.get('expired_and_processed', False):
                    session_info['expired_and_processed'] = True
                    try:
                        auto_end_session_helper(session_id, db=db)
                    except Exception as e:
                        print(f"Error auto-ending session: {e}")
                    ACTIVE_SESSIONS.pop(subject_name_key, None)
                    session_dict = session.to_dict()
            elif elapsed < 30:
                active_token = session_info.get('token_1')
                qr_number = 1
                time_remaining = int(30.0 - elapsed)
            else:
                active_token = session_info.get('token_2')
                qr_number = 2
                time_remaining = int(60.0 - elapsed)

        # Backwards compatibility check
        if session_info and not active_token and not session_info.get('token_1'):
            active_token = session_info.get('token')

        if active_token and session.subject:
            session_dict['token'] = active_token
            if qr_number is not None:
                session_dict['qr_number'] = qr_number
                session_dict['time_remaining'] = time_remaining
            # Reconstruct URL
            ngrok_url = get_ngrok_url()
            import urllib.parse
            if ngrok_url:
                student_url = f"{ngrok_url}/student.html?token={active_token}&subject={urllib.parse.quote(session.subject.name)}"
            else:
                host = request.host
                if "127.0.0.1" in host or "localhost" in host:
                    ip = get_local_ip()
                    host = host.replace("127.0.0.1", ip).replace("localhost", ip)
                scheme = request.scheme
                student_url = f"{scheme}://{host}/student.html?token={active_token}&subject={urllib.parse.quote(session.subject.name)}"
            session_dict['url'] = student_url

            # Generate QR code
            qr = qrcode.QRCode(version=1, box_size=8, border=4)
            qr.add_data(student_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            qr_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            session_dict['qr_code'] = f"data:image/png;base64,{qr_base64}"

        # Get attendance records for this session
        records = db.query(Attendance).filter(Attendance.class_session_id == session_id).all()
        session_dict['attendance'] = [r.to_dict() for r in records]

        return jsonify(session_dict)
    finally:
        db.close()


@app.route('/api/class-sessions/<int:session_id>/mark-attendance', methods=['POST'])
def mark_session_attendance(session_id):
    """
    Mark attendance for a class session.
    Applies the +1% / -3% attendance percentage formula.
    Sends absence notifications.
    """
    db = get_db()
    try:
        session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
        if not session:
            return jsonify({'error': 'Session not found.'}), 404

        data = request.json or {}
        present_ids = data.get('present_student_ids', [])
        absent_ids = data.get('absent_student_ids', [])

        if not present_ids and not absent_ids:
            return jsonify({'error': 'No student IDs provided.'}), 400

        subject = db.query(Subject).filter(Subject.id == session.subject_id).first()
        subject_name = subject.name if subject else 'Unknown'
        today = datetime.now().strftime('%Y-%m-%d')
        now_time = datetime.now().strftime('%H:%M:%S')

        results = {'present': [], 'absent': [], 'notifications_sent': 0}

        # Mark PRESENT students (+1%)
        for student_id in present_ids:
            student = db.query(Student).filter(Student.id == int(student_id)).first()
            if not student:
                continue

            # Check if already marked for this session
            existing = db.query(Attendance).filter(
                Attendance.student_id == student.id,
                Attendance.class_session_id == session_id
            ).first()
            if existing:
                continue

            # Create attendance record
            record = Attendance(
                student_id=student.id,
                subject=subject_name,
                date=today,
                time=now_time,
                status='Present',
                confidence='100.0',
                class_session_id=session_id
            )
            db.add(record)

            # Update attendance percentage (+1%, cap at 100)
            old_pct = student.attendance_percentage or 75.0
            new_pct = min(100.0, old_pct + 1.0)
            student.attendance_percentage = new_pct

            # Log the change
            log = AttendancePercentageLog(
                student_id=student.id,
                subject_id=session.subject_id,
                old_percentage=old_pct,
                new_percentage=new_pct,
                change_type='+1',
                class_session_id=session_id
            )
            db.add(log)
            results['present'].append({'id': student.id, 'name': student.name, 'new_pct': round(new_pct, 1)})

        # Mark ABSENT students (-3%)
        for student_id in absent_ids:
            student = db.query(Student).filter(Student.id == int(student_id)).first()
            if not student:
                continue

            # Check if already marked for this session
            existing = db.query(Attendance).filter(
                Attendance.student_id == student.id,
                Attendance.class_session_id == session_id
            ).first()
            if existing:
                continue

            # Create attendance record with Absent status
            record = Attendance(
                student_id=student.id,
                subject=subject_name,
                date=today,
                time=now_time,
                status='Absent',
                confidence='0',
                class_session_id=session_id
            )
            db.add(record)

            # Update attendance percentage (-3%, floor at 0)
            old_pct = student.attendance_percentage or 75.0
            new_pct = max(0.0, old_pct - 3.0)
            student.attendance_percentage = new_pct

            # Log the change
            log = AttendancePercentageLog(
                student_id=student.id,
                subject_id=session.subject_id,
                old_percentage=old_pct,
                new_percentage=new_pct,
                change_type='-3',
                class_session_id=session_id
            )
            db.add(log)

            # Send absence notification
            notify_absence(db, student, subject_name, today, new_pct)
            results['notifications_sent'] += 1

            # Check low attendance thresholds
            threshold = notify_low_attendance(db, student, new_pct)
            if threshold:
                results['notifications_sent'] += 1

            results['absent'].append({
                'id': student.id,
                'name': student.name,
                'new_pct': round(new_pct, 1),
                'notification': True
            })

        db.commit()
        return jsonify({
            'success': True,
            'message': f'Attendance marked: {len(results["present"])} present, {len(results["absent"])} absent.',
            'results': results
        })
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


def auto_end_session_helper(session_id, db=None):
    """End a class session and mark remaining students as absent."""
    local_db = False
    if db is None:
        db = get_db()
        local_db = True
    try:
        session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
        if not session:
            raise ValueError('Session not found.')

        if session.status == 'completed':
            return {
                'absent_count': 0,
                'session': session.to_dict()
            }

        session.status = 'completed'
        session.end_time = datetime.now().strftime('%H:%M')

        # Get all students (or students in the subject's department)
        subject = db.query(Subject).filter(Subject.id == session.subject_id).first()
        all_students = db.query(Student).all()
        if subject:
            # Filter to students in the same department
            dept_students = [s for s in all_students if s.department == subject.department]
            if dept_students:
                all_students = dept_students

        # Find students who are NOT marked for this session
        marked_ids = set()
        records = db.query(Attendance).filter(Attendance.class_session_id == session_id).all()
        for r in records:
            marked_ids.add(r.student_id)

        today = datetime.now().strftime('%Y-%m-%d')
        now_time = datetime.now().strftime('%H:%M:%S')
        subject_name = subject.name if subject else 'Unknown'
        absent_count = 0

        for student in all_students:
            if student.id not in marked_ids:
                # Mark as absent
                record = Attendance(
                    student_id=student.id,
                    subject=subject_name,
                    date=today,
                    time=now_time,
                    status='Absent',
                    confidence='0',
                    class_session_id=session_id
                )
                db.add(record)

                # Apply -3% penalty
                old_pct = student.attendance_percentage or 75.0
                new_pct = max(0.0, old_pct - 3.0)
                student.attendance_percentage = new_pct

                log = AttendancePercentageLog(
                    student_id=student.id,
                    subject_id=session.subject_id,
                    old_percentage=old_pct,
                    new_percentage=new_pct,
                    change_type='-3',
                    class_session_id=session_id
                )
                db.add(log)

                # Notify
                notify_absence(db, student, subject_name, today, new_pct)
                notify_low_attendance(db, student, new_pct)
                absent_count += 1

        db.commit()
        return {
            'absent_count': absent_count,
            'session': session.to_dict()
        }
    except Exception as e:
        db.rollback()
        raise e
    finally:
        if local_db:
            db.close()


@app.route('/api/class-sessions/<int:session_id>/end', methods=['POST'])
def end_class_session(session_id):
    """End a class session and mark remaining students as absent."""
    try:
        res = auto_end_session_helper(session_id)
        return jsonify({
            'success': True,
            'message': f'Session ended. {res["absent_count"]} unmarked students marked as absent.',
            'session': res['session']
        })
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────
# ATTENDANCE PERCENTAGE
# ─────────────────────────────────────────────
@app.route('/api/attendance/percentage/<int:student_id>', methods=['GET'])
def get_student_percentage(student_id):
    """Get a student's attendance percentage and history."""
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return jsonify({'error': 'Student not found.'}), 404

        # Get percentage change logs
        logs = db.query(AttendancePercentageLog).filter(
            AttendancePercentageLog.student_id == student_id
        ).order_by(AttendancePercentageLog.timestamp.desc()).limit(50).all()

        # Count total present/absent
        total_present = db.query(Attendance).filter(
            Attendance.student_id == student_id,
            Attendance.status == 'Present'
        ).count()
        total_absent = db.query(Attendance).filter(
            Attendance.student_id == student_id,
            Attendance.status == 'Absent'
        ).count()

        return jsonify({
            'student': student.to_dict(),
            'attendance_percentage': round(student.attendance_percentage or 75.0, 1),
            'total_present': total_present,
            'total_absent': total_absent,
            'total_classes': total_present + total_absent,
            'logs': [l.to_dict() for l in logs]
        })
    finally:
        db.close()


@app.route('/api/attendance/percentage/<int:student_id>/log', methods=['GET'])
def get_percentage_log(student_id):
    """Get detailed percentage change log for a student."""
    db = get_db()
    try:
        logs = db.query(AttendancePercentageLog).filter(
            AttendancePercentageLog.student_id == student_id
        ).order_by(AttendancePercentageLog.timestamp.desc()).limit(100).all()
        return jsonify([l.to_dict() for l in logs])
    finally:
        db.close()


@app.route('/api/attendance/percentage/report', methods=['GET'])
def attendance_percentage_report():
    """Get attendance percentage report for all students."""
    db = get_db()
    try:
        department = request.args.get('department')
        min_pct = request.args.get('min_pct', type=float)
        max_pct = request.args.get('max_pct', type=float)

        query = db.query(Student)
        if department and department != 'All':
            query = query.filter(Student.department == department)

        students = query.order_by(Student.name).all()
        report = []

        for student in students:
            pct = round(student.attendance_percentage or 75.0, 1)

            # Apply percentage range filter
            if min_pct is not None and pct < min_pct:
                continue
            if max_pct is not None and pct > max_pct:
                continue

            total_present = db.query(Attendance).filter(
                Attendance.student_id == student.id,
                Attendance.status == 'Present'
            ).count()
            total_absent = db.query(Attendance).filter(
                Attendance.student_id == student.id,
                Attendance.status == 'Absent'
            ).count()

            # Determine status
            if pct >= 75:
                status = 'good'
            elif pct >= 60:
                status = 'warning'
            elif pct >= 50:
                status = 'danger'
            else:
                status = 'critical'

            report.append({
                'id': student.id,
                'name': student.name,
                'roll_number': student.roll_number,
                'department': student.department,
                'attendance_percentage': pct,
                'total_present': total_present,
                'total_absent': total_absent,
                'total_classes': total_present + total_absent,
                'status': status
            })

        # Summary stats
        percentages = [r['attendance_percentage'] for r in report]
        summary = {
            'total_students': len(report),
            'average_percentage': round(sum(percentages) / len(percentages), 1) if percentages else 0,
            'below_75': sum(1 for p in percentages if p < 75),
            'below_50': sum(1 for p in percentages if p < 50),
        }

        return jsonify({'report': report, 'summary': summary})
    finally:
        db.close()


# ─────────────────────────────────────────────
# INTERNAL MARKS
# ─────────────────────────────────────────────
@app.route('/api/marks', methods=['POST'])
def create_marks():
    """Enter marks for a single student."""
    db = get_db()
    try:
        data = request.json or {}
        student_id = data.get('student_id')
        subject_id = data.get('subject_id')
        exam_type = data.get('exam_type', '').strip()
        max_marks = data.get('max_marks', 100)
        obtained_marks = data.get('obtained_marks', 0)
        semester = data.get('semester')
        date = data.get('date')
        remarks = data.get('remarks', '').strip()

        if not all([student_id, subject_id, exam_type]):
            return jsonify({'error': 'Student, subject, and exam type are required.'}), 400

        # Check for duplicate entry
        existing = db.query(InternalMarks).filter(
            InternalMarks.student_id == int(student_id),
            InternalMarks.subject_id == int(subject_id),
            InternalMarks.exam_type == exam_type
        ).first()

        if existing:
            # Update existing
            existing.max_marks = float(max_marks)
            existing.obtained_marks = float(obtained_marks)
            existing.remarks = remarks or None
            if date: existing.date = date
            db.commit()
            return jsonify({'success': True, 'marks': existing.to_dict(), 'message': 'Marks updated.'})

        marks = InternalMarks(
            student_id=int(student_id),
            subject_id=int(subject_id),
            exam_type=exam_type,
            max_marks=float(max_marks),
            obtained_marks=float(obtained_marks),
            semester=int(semester) if semester else None,
            date=date,
            remarks=remarks or None
        )
        db.add(marks)
        db.commit()
        return jsonify({'success': True, 'marks': marks.to_dict(), 'message': 'Marks saved.'})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/marks/bulk', methods=['POST'])
def create_marks_bulk():
    """Bulk enter marks for multiple students."""
    db = get_db()
    try:
        data = request.json or {}
        subject_id = data.get('subject_id')
        exam_type = data.get('exam_type', '').strip()
        max_marks = data.get('max_marks', 100)
        marks_list = data.get('marks', [])

        if not all([subject_id, exam_type]):
            return jsonify({'error': 'Subject and exam type are required.'}), 400
        if not marks_list:
            return jsonify({'error': 'No marks data provided.'}), 400

        subject = db.query(Subject).filter(Subject.id == int(subject_id)).first()
        if not subject:
            return jsonify({'error': 'Subject not found.'}), 404

        saved_count = 0
        updated_count = 0

        for entry in marks_list:
            student_id = entry.get('student_id')
            obtained = entry.get('obtained_marks', 0)
            remarks = entry.get('remarks', '')

            if not student_id:
                continue

            # Check if entry exists
            existing = db.query(InternalMarks).filter(
                InternalMarks.student_id == int(student_id),
                InternalMarks.subject_id == int(subject_id),
                InternalMarks.exam_type == exam_type
            ).first()

            if existing:
                existing.max_marks = float(max_marks)
                existing.obtained_marks = float(obtained)
                existing.remarks = remarks or None
                updated_count += 1
            else:
                marks = InternalMarks(
                    student_id=int(student_id),
                    subject_id=int(subject_id),
                    exam_type=exam_type,
                    max_marks=float(max_marks),
                    obtained_marks=float(obtained),
                    date=datetime.now().strftime('%Y-%m-%d'),
                    remarks=remarks or None
                )
                db.add(marks)
                saved_count += 1

            # Send marks notification
            student = db.query(Student).filter(Student.id == int(student_id)).first()
            if student and student.email:
                email_subject, html_body, plain_body = build_marks_published_notification(
                    student.name, student.roll_number, subject.name,
                    exam_type, float(obtained), float(max_marks)
                )
                send_email_async(student.email, email_subject, html_body, plain_body)

                notif = Notification(
                    student_id=student.id,
                    type='marks_published',
                    message=f'{exam_type} marks for {subject.name}: {obtained}/{max_marks}',
                    sent_via='email',
                    status='sent'
                )
                db.add(notif)

        db.commit()
        return jsonify({
            'success': True,
            'message': f'Marks processed: {saved_count} new, {updated_count} updated.',
            'saved': saved_count,
            'updated': updated_count
        })
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/marks/<int:student_id>', methods=['GET'])
def get_student_marks(student_id):
    """Get all marks for a specific student."""
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return jsonify({'error': 'Student not found.'}), 404

        subject_id = request.args.get('subject_id')
        exam_type = request.args.get('exam_type')

        query = db.query(InternalMarks).filter(InternalMarks.student_id == student_id)
        if subject_id:
            query = query.filter(InternalMarks.subject_id == int(subject_id))
        if exam_type:
            query = query.filter(InternalMarks.exam_type == exam_type)

        marks = query.order_by(InternalMarks.subject_id, InternalMarks.exam_type).all()
        return jsonify({
            'student': student.to_dict(),
            'marks': [m.to_dict() for m in marks]
        })
    finally:
        db.close()


@app.route('/api/marks/report', methods=['GET'])
def marks_report():
    """Get marks report filtered by subject and exam type."""
    db = get_db()
    try:
        subject_id = request.args.get('subject_id')
        exam_type = request.args.get('exam_type')

        query = db.query(InternalMarks)
        if subject_id:
            query = query.filter(InternalMarks.subject_id == int(subject_id))
        if exam_type:
            query = query.filter(InternalMarks.exam_type == exam_type)

        marks = query.all()
        marks_list = [m.to_dict() for m in marks]

        # Calculate statistics
        if marks_list:
            obtained_list = [m['obtained_marks'] for m in marks_list]
            max_marks_val = marks_list[0]['max_marks'] if marks_list else 100
            stats = {
                'count': len(marks_list),
                'average': round(sum(obtained_list) / len(obtained_list), 1),
                'highest': max(obtained_list),
                'lowest': min(obtained_list),
                'max_marks': max_marks_val,
                'pass_count': sum(1 for m in marks_list if (m['obtained_marks'] / m['max_marks'] * 100) >= 40),
                'pass_percentage': round(sum(1 for m in marks_list if (m['obtained_marks'] / m['max_marks'] * 100) >= 40) / len(marks_list) * 100, 1)
            }
        else:
            stats = {'count': 0, 'average': 0, 'highest': 0, 'lowest': 0, 'max_marks': 100, 'pass_count': 0, 'pass_percentage': 0}

        return jsonify({'marks': marks_list, 'stats': stats})
    finally:
        db.close()


@app.route('/api/marks/<int:mark_id>', methods=['PUT'])
def update_mark(mark_id):
    """Update a specific marks entry."""
    db = get_db()
    try:
        mark = db.query(InternalMarks).filter(InternalMarks.id == mark_id).first()
        if not mark:
            return jsonify({'error': 'Mark entry not found.'}), 404

        data = request.json or {}
        if 'obtained_marks' in data: mark.obtained_marks = float(data['obtained_marks'])
        if 'max_marks' in data: mark.max_marks = float(data['max_marks'])
        if 'remarks' in data: mark.remarks = data['remarks'].strip() or None

        db.commit()
        return jsonify({'success': True, 'marks': mark.to_dict()})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
# NOTIFICATIONS
# ─────────────────────────────────────────────
@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    """List all notifications with filters."""
    db = get_db()
    try:
        notif_type = request.args.get('type')
        status = request.args.get('status')
        student_id = request.args.get('student_id')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')

        query = db.query(Notification)
        if notif_type and notif_type != 'All':
            query = query.filter(Notification.type == notif_type)
        if status and status != 'All':
            query = query.filter(Notification.status == status)
        if student_id:
            query = query.filter(Notification.student_id == int(student_id))

        notifications = query.order_by(Notification.sent_at.desc()).limit(200).all()
        return jsonify([n.to_dict() for n in notifications])
    finally:
        db.close()


@app.route('/api/notifications/<int:student_id>', methods=['GET'])
def get_student_notifications(student_id):
    """Get notification history for a specific student."""
    db = get_db()
    try:
        notifications = db.query(Notification).filter(
            Notification.student_id == student_id
        ).order_by(Notification.sent_at.desc()).limit(50).all()
        return jsonify([n.to_dict() for n in notifications])
    finally:
        db.close()


@app.route('/api/notifications/send', methods=['POST'])
def send_custom_notification():
    """Send a custom notification to selected students."""
    db = get_db()
    try:
        data = request.json or {}
        student_ids = data.get('student_ids', [])
        notif_type = data.get('type', 'custom')
        message = data.get('message', '').strip()

        if not student_ids or not message:
            return jsonify({'error': 'Student IDs and message are required.'}), 400

        sent_count = 0
        for sid in student_ids:
            student = db.query(Student).filter(Student.id == int(sid)).first()
            if not student:
                continue

            notif = Notification(
                student_id=student.id,
                type=notif_type,
                message=message,
                sent_via='email',
                status='sent' if student.email else 'no_email'
            )
            db.add(notif)

            if student.email:
                html_body = f"""
                <html><body style="font-family: 'Segoe UI', sans-serif; padding: 20px;">
                    <div style="background: linear-gradient(135deg, #667eea, #764ba2); padding: 20px; border-radius: 12px 12px 0 0; text-align: center;">
                        <h2 style="color: white;">📋 Notification</h2>
                    </div>
                    <div style="background: white; padding: 20px; border-radius: 0 0 12px 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <p>Dear {student.name},</p>
                        <p>{message}</p>
                        <p style="color: #777; font-size: 13px;">— Smart Attendance System</p>
                    </div>
                </body></html>
                """
                send_email_async(student.email, f'Notification — Smart Attendance', html_body)
                sent_count += 1

        db.commit()
        return jsonify({'success': True, 'message': f'Notification sent to {sent_count} students.', 'sent': sent_count})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/notifications/<int:notif_id>/resend', methods=['POST'])
def resend_notification(notif_id):
    """Resend a failed notification."""
    db = get_db()
    try:
        notif = db.query(Notification).filter(Notification.id == notif_id).first()
        if not notif:
            return jsonify({'error': 'Notification not found.'}), 404

        student = db.query(Student).filter(Student.id == notif.student_id).first()
        if not student or not student.email:
            return jsonify({'error': 'Student has no email address.'}), 400

        html_body = f"""
        <html><body style="font-family: 'Segoe UI', sans-serif; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea, #764ba2); padding: 20px; border-radius: 12px 12px 0 0; text-align: center;">
                <h2 style="color: white;">📋 Notification (Resent)</h2>
            </div>
            <div style="background: white; padding: 20px; border-radius: 0 0 12px 12px;">
                <p>Dear {student.name},</p>
                <p>{notif.message}</p>
                <p style="color: #777; font-size: 13px;">— Smart Attendance System</p>
            </div>
        </body></html>
        """
        send_email_async(student.email, f'Notification — Smart Attendance', html_body)
        notif.status = 'sent'
        notif.sent_at = datetime.utcnow()
        db.commit()
        return jsonify({'success': True, 'message': 'Notification resent.'})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/notifications/stats', methods=['GET'])
def notification_stats():
    """Get notification statistics."""
    db = get_db()
    try:
        from sqlalchemy import func
        total = db.query(Notification).count()
        sent = db.query(Notification).filter(Notification.status == 'sent').count()
        failed = db.query(Notification).filter(Notification.status == 'failed').count()
        pending = db.query(Notification).filter(Notification.status == 'pending').count()
        no_email = db.query(Notification).filter(Notification.status == 'no_email').count()

        today = datetime.now().strftime('%Y-%m-%d')
        today_count = db.query(Notification).filter(
            func.date(Notification.sent_at) == today
        ).count()

        # Type distribution
        type_counts = {}
        for notif_type in ['absence', 'low_attendance', 'marks_published', 'custom']:
            type_counts[notif_type] = db.query(Notification).filter(
                Notification.type == notif_type
            ).count()

        return jsonify({
            'total': total,
            'sent': sent,
            'failed': failed,
            'pending': pending,
            'no_email': no_email,
            'today': today_count,
            'type_distribution': type_counts
        })
    finally:
        db.close()


# ─────────────────────────────────────────────
# LECTURER DASHBOARD
# ─────────────────────────────────────────────
@app.route('/api/lecturer/dashboard', methods=['GET'])
def lecturer_dashboard():
    """Get dashboard stats for a lecturer."""
    db = get_db()
    try:
        lecturer_id = request.args.get('lecturer_id')
        today = datetime.now().strftime('%Y-%m-%d')

        # Today's sessions
        sessions_query = db.query(ClassSession).filter(ClassSession.date == today)
        if lecturer_id:
            sessions_query = sessions_query.filter(ClassSession.lecturer_id == int(lecturer_id))
        today_sessions = sessions_query.all()

        # Total sessions
        total_query = db.query(ClassSession)
        if lecturer_id:
            total_query = total_query.filter(ClassSession.lecturer_id == int(lecturer_id))
        total_sessions = total_query.count()

        # Active sessions
        active_query = db.query(ClassSession).filter(ClassSession.status == 'active')
        if lecturer_id:
            active_query = active_query.filter(ClassSession.lecturer_id == int(lecturer_id))
        active_sessions = active_query.all()

        # Recent sessions (last 10)
        recent_query = db.query(ClassSession)
        if lecturer_id:
            recent_query = recent_query.filter(ClassSession.lecturer_id == int(lecturer_id))
        recent_sessions = recent_query.order_by(
            ClassSession.date.desc(), ClassSession.start_time.desc()
        ).limit(10).all()

        # Students count
        total_students = db.query(Student).count()

        return jsonify({
            'today_sessions': [s.to_dict() for s in today_sessions],
            'total_sessions': total_sessions,
            'active_sessions': [s.to_dict() for s in active_sessions],
            'recent_sessions': [s.to_dict() for s in recent_sessions],
            'total_students': total_students,
            'today_count': len(today_sessions),
        })
    finally:
        db.close()


# ─────────────────────────────────────────────
# STUDENT PROFILE UPDATE (phone, email)
# ─────────────────────────────────────────────
@app.route('/api/students/<int:student_id>', methods=['PUT'])
def update_student(student_id):
    """Update student details (phone, email, semester, etc.)."""
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return jsonify({'error': 'Student not found.'}), 404

        data = request.json or {}
        if 'name' in data:
            val = data['name']
            student.name = val.strip() if (val and isinstance(val, str)) else student.name
        if 'department' in data:
            val = data['department']
            student.department = val.strip() if (val and isinstance(val, str)) else student.department
        if 'phone' in data:
            val = data['phone']
            student.phone = val.strip() if (val and isinstance(val, str)) else None
        if 'email' in data:
            val = data['email']
            student.email = val.strip() if (val and isinstance(val, str)) else None
        if 'alt_phone' in data:
            val = data['alt_phone']
            student.alt_phone = val.strip() if (val and isinstance(val, str)) else None
        if 'alt_email' in data:
            val = data['alt_email']
            student.alt_email = val.strip() if (val and isinstance(val, str)) else None
        if 'semester' in data: student.semester = int(data['semester'])
        if 'year_of_admission' in data: student.year_of_admission = int(data['year_of_admission'])

        db.commit()
        return jsonify({'success': True, 'student': student.to_dict()})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
# SERVE FRONTEND
# ─────────────────────────────────────────────
@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return app.send_static_file(filename)


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)

