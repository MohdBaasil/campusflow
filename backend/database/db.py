"""
Database models and manager for CampusFlow / College Management System.
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Time, DateTime, ForeignKey, LargeBinary, Text, text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'attendance.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')
if DATABASE_URL:
    # Render PostgreSQL URLs sometimes use 'postgres://' which SQLAlchemy deprecated. Convert it to 'postgresql://'.
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL, echo=False)
else:
    engine = create_engine(f'sqlite:///{DB_PATH}', echo=False)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Student(Base):
    __tablename__ = 'students'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    roll_number = Column(String, unique=True, nullable=False)
    department = Column(String, nullable=False)
    photo_dir = Column(String, nullable=True)
    password = Column(String, nullable=True)          # SHA-256 hash
    marksheet_path = Column(String, nullable=True)    # Server path to uploaded marksheet
    id_card_path = Column(String, nullable=True)      # Server path to uploaded ID document
    phone = Column(String, nullable=True)             # Mobile number for notifications
    email = Column(String, nullable=True)             # Email for notifications
    alt_phone = Column(String, nullable=True)         # Alternative mobile number for notifications
    alt_email = Column(String, nullable=True)         # Alternative email for notifications
    semester = Column(Integer, default=1, nullable=False)
    year_of_admission = Column(Integer, nullable=True)
    attendance_percentage = Column(Float, default=100.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    attendances = relationship('Attendance', back_populates='student', cascade='all, delete')
    embeddings = relationship('FaceEmbedding', back_populates='student', cascade='all, delete')
    internal_marks = relationship('InternalMarks', back_populates='student', cascade='all, delete')
    notifications = relationship('Notification', back_populates='student', cascade='all, delete')
    percentage_logs = relationship('AttendancePercentageLog', back_populates='student', cascade='all, delete')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.password and self.roll_number:
            import hashlib
            reg_num = self.roll_number.strip().upper()
            self.password = hashlib.sha256(reg_num.encode()).hexdigest()

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'roll_number': self.roll_number,
            'department': self.department,
            'photo_dir': self.photo_dir,
            'phone': self.phone,
            'email': self.email,
            'alt_phone': self.alt_phone,
            'alt_email': self.alt_email,
            'semester': self.semester,
            'attendance_percentage': self.attendance_percentage,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'face_count': len(self.embeddings) if self.embeddings is not None else 0,
            'has_password': self.password is not None and len(self.password) > 0,
            'has_marksheet': self.marksheet_path is not None and len(self.marksheet_path) > 0,
            'has_id_card': self.id_card_path is not None and len(self.id_card_path) > 0,
        }


class FaceEmbedding(Base):
    __tablename__ = 'face_embeddings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    embedding = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship('Student', back_populates='embeddings')

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }



class Attendance(Base):
    __tablename__ = 'attendance'

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    subject = Column(String, nullable=False)
    date = Column(String, nullable=False)
    time = Column(String, nullable=False)
    status = Column(String, default='Present')
    confidence = Column(String, nullable=True)
    class_session_id = Column(Integer, ForeignKey('class_sessions.id'), nullable=True)

    student = relationship('Student', back_populates='attendances')
    class_session = relationship('ClassSession', back_populates='attendance_records')

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'student_name': self.student.name if self.student else 'Unknown',
            'roll_number': self.student.roll_number if self.student else '',
            'department': self.student.department if self.student else '',
            'subject': self.subject,
            'date': self.date,
            'time': self.time,
            'status': self.status,
            'confidence': self.confidence,
            'class_session_id': self.class_session_id,
        }


# ─────────────────────────────────────────────
# NEW MODELS FOR COLLEGE MANAGEMENT SYSTEM
# ─────────────────────────────────────────────

class Lecturer(Base):
    __tablename__ = 'lecturers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    employee_id = Column(String, unique=True, nullable=False)
    department = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    password = Column(String, nullable=False)  # SHA-256 hash
    created_at = Column(DateTime, default=datetime.utcnow)

    class_sessions = relationship('ClassSession', back_populates='lecturer', cascade='all, delete')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.password and self.employee_id:
            import hashlib
            self.password = hashlib.sha256(self.employee_id.strip().upper().encode()).hexdigest()

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'employee_id': self.employee_id,
            'department': self.department,
            'phone': self.phone,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'total_sessions': len(self.class_sessions) if self.class_sessions else 0,
        }


class Subject(Base):
    __tablename__ = 'subjects'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    department = Column(String, nullable=False)
    specialization = Column(String, nullable=True)
    semester = Column(Integer, nullable=True, default=1)
    credits = Column(Integer, nullable=True, default=3)
    lecturer_id = Column(Integer, ForeignKey('lecturers.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    lecturer = relationship('Lecturer')
    class_sessions = relationship('ClassSession', back_populates='subject', cascade='all, delete')
    internal_marks = relationship('InternalMarks', back_populates='subject', cascade='all, delete')

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'department': self.department,
            'specialization': self.specialization,
            'semester': self.semester,
            'credits': self.credits,
            'lecturer_id': self.lecturer_id,
            'lecturer_name': self.lecturer.name if self.lecturer else 'Unassigned',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'total_sessions': len(self.class_sessions) if self.class_sessions else 0,
        }


class ClassSession(Base):
    """Tracks which lecturer took which class, when, and what topic."""
    __tablename__ = 'class_sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_id = Column(Integer, ForeignKey('subjects.id'), nullable=False)
    lecturer_id = Column(Integer, ForeignKey('lecturers.id'), nullable=False)
    date = Column(String, nullable=False)         # YYYY-MM-DD
    start_time = Column(String, nullable=True)    # HH:MM
    end_time = Column(String, nullable=True)      # HH:MM
    topic_covered = Column(String, nullable=True)
    session_type = Column(String, default='Lecture')  # Lecture / Lab / Tutorial
    status = Column(String, default='active')     # active / completed
    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship('Subject', back_populates='class_sessions')
    lecturer = relationship('Lecturer', back_populates='class_sessions')
    attendance_records = relationship('Attendance', back_populates='class_session')
    percentage_logs = relationship('AttendancePercentageLog', back_populates='class_session')

    def to_dict(self):
        return {
            'id': self.id,
            'subject_id': self.subject_id,
            'subject_code': self.subject.code if self.subject else '',
            'subject_name': self.subject.name if self.subject else '',
            'department': self.subject.department if self.subject else '',
            'semester': self.subject.semester if self.subject else 1,
            'lecturer_id': self.lecturer_id,
            'lecturer_name': self.lecturer.name if self.lecturer else '',
            'date': self.date,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'topic_covered': self.topic_covered,
            'session_type': self.session_type,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'attendance_count': len(self.attendance_records) if self.attendance_records else 0,
        }


class InternalMarks(Base):
    """Stores internal assessment marks for students."""
    __tablename__ = 'internal_marks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    subject_id = Column(Integer, ForeignKey('subjects.id'), nullable=False)
    exam_type = Column(String, nullable=False)  # Internal 1 / Internal 2 / Internal 3 / Assignment / Lab
    max_marks = Column(Float, nullable=False, default=100.0)
    obtained_marks = Column(Float, nullable=False, default=0.0)
    semester = Column(Integer, nullable=True)
    date = Column(String, nullable=True)   # Exam date YYYY-MM-DD
    remarks = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship('Student', back_populates='internal_marks')
    subject = relationship('Subject', back_populates='internal_marks')

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'student_name': self.student.name if self.student else '',
            'roll_number': self.student.roll_number if self.student else '',
            'subject_id': self.subject_id,
            'subject_code': self.subject.code if self.subject else '',
            'subject_name': self.subject.name if self.subject else '',
            'exam_type': self.exam_type,
            'max_marks': self.max_marks,
            'obtained_marks': self.obtained_marks,
            'percentage': round((self.obtained_marks / self.max_marks * 100), 1) if self.max_marks > 0 else 0,
            'semester': self.semester,
            'date': self.date,
            'remarks': self.remarks,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class AttendancePercentageLog(Base):
    """Audit trail for attendance percentage changes (+1/-3 formula)."""
    __tablename__ = 'attendance_percentage_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    subject_id = Column(Integer, ForeignKey('subjects.id'), nullable=True)
    old_percentage = Column(Float, nullable=False)
    new_percentage = Column(Float, nullable=False)
    change_type = Column(String, nullable=False)  # "+1" or "-3"
    class_session_id = Column(Integer, ForeignKey('class_sessions.id'), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    student = relationship('Student', back_populates='percentage_logs')
    class_session = relationship('ClassSession', back_populates='percentage_logs')

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'student_name': self.student.name if self.student else '',
            'roll_number': self.student.roll_number if self.student else '',
            'subject_id': self.subject_id,
            'old_percentage': round(self.old_percentage, 1),
            'new_percentage': round(self.new_percentage, 1),
            'change_type': self.change_type,
            'class_session_id': self.class_session_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }


class Notification(Base):
    """Tracks notifications sent to students (absence alerts, low attendance, etc.)."""
    __tablename__ = 'notifications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    type = Column(String, nullable=False)       # absence / low_attendance / marks_published
    message = Column(Text, nullable=False)
    sent_via = Column(String, default='email')  # email / sms / push
    sent_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default='pending')  # pending / sent / failed

    student = relationship('Student', back_populates='notifications')

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'student_name': self.student.name if self.student else '',
            'roll_number': self.student.roll_number if self.student else '',
            'type': self.type,
            'message': self.message,
            'sent_via': self.sent_via,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'status': self.status,
        }


def init_db():
    Base.metadata.create_all(engine)
    # ── Migration: add new columns to existing tables ──
    _migrate_add_columns()
    # ── Migration: set default passwords for existing students ──
    _migrate_default_passwords()
    # ── Seed curriculum ──
    try:
        from backend.database.seed_curriculum import seed_database
        seed_database()
    except Exception as e:
        print(f"[Migration] Error seeding curriculum: {e}")


def _migrate_add_columns():
    """Safely add new columns to the students table for existing databases."""
    new_columns = [
        ('students', 'password', 'TEXT'),
        ('students', 'marksheet_path', 'TEXT'),
        ('students', 'id_card_path', 'TEXT'),
        ('students', 'phone', 'TEXT'),
        ('students', 'email', 'TEXT'),
        ('students', 'semester', 'INTEGER DEFAULT 1'),
        ('students', 'year_of_admission', 'INTEGER'),
        ('students', 'attendance_percentage', 'REAL DEFAULT 75.0'),
        ('attendance', 'class_session_id', 'INTEGER'),
        ('subjects', 'specialization', 'TEXT'),
    ]
    with engine.connect() as conn:
        for table, col, col_type in new_columns:
            try:
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {col} {col_type}'))
                conn.commit()
                print(f"[Migration] Added column '{col}' to '{table}'.")
            except Exception:
                # Column already exists — safe to ignore
                pass


def _migrate_default_passwords():
    """For existing students, set their login password to their roll/register number if not set."""
    import hashlib
    db = SessionLocal()
    try:
        # Fetch students where password is NULL or empty
        students = db.query(Student).filter(
            (Student.password == None) | (Student.password == '')
        ).all()
        if students:
            for student in students:
                if student.roll_number:
                    reg_num = student.roll_number.strip().upper()
                    pwd_hash = hashlib.sha256(reg_num.encode()).hexdigest()
                    student.password = pwd_hash
            db.commit()
            print(f"[Migration] Set default roll_number passwords for {len(students)} existing students.")

        # Set default attendance_percentage for students who don't have one
        students_no_pct = db.query(Student).filter(
            Student.attendance_percentage == None
        ).all()
        if students_no_pct:
            for student in students_no_pct:
                student.attendance_percentage = 75.0
            db.commit()
            print(f"[Migration] Set default attendance percentage (75%) for {len(students_no_pct)} students.")
    except Exception as e:
        print(f"[Migration] Error setting default passwords: {e}")
        db.rollback()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise
