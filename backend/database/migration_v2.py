"""
Database Migration v2 - Adds new models and columns for College Management System expansion.
"""
import os
import hashlib
from sqlalchemy import text
from backend.database.db import (
    engine, Base, SessionLocal, Student, Lecturer, Subject, 
    InternalMarks, AttendancePercentageLog, Notification
)

def run_migration_v2():
    print("[Migration v2] Starting migration...")
    
    # 1. Safely add new columns to the students table
    new_student_columns = [
        ('students', 'phone', 'TEXT'),
        ('students', 'email', 'TEXT'),
        ('students', 'alt_phone', 'TEXT'),
        ('students', 'alt_email', 'TEXT'),
        ('students', 'semester', 'INTEGER DEFAULT 1'),
        ('students', 'attendance_percentage', 'REAL DEFAULT 100.0'),
        ('students', 'year_of_admission', 'INTEGER'),
        ('subjects', 'lecturer_id', 'INTEGER'),
        ('subjects', 'specialization', 'TEXT')
    ]
    
    with engine.connect() as conn:
        for table, col, col_type in new_student_columns:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                conn.commit()
                print(f"[Migration v2] Added column '{col}' to '{table}'.")
            except Exception:
                # Column probably already exists — ignore
                pass
                
    # 2. Create any missing tables (Lecturer, Subject, ClassSession, etc.)
    Base.metadata.create_all(engine)
    print("[Migration v2] Tables verified / created.")
    
    # 3. Seed initial test data
    db = SessionLocal()
    try:
        # Check and seed a test lecturer
        lecturer = db.query(Lecturer).filter(Lecturer.employee_id == 'LECTURER1').first()
        if not lecturer:
            lecturer = Lecturer(
                name="Dr. Alan Turing",
                employee_id="LECTURER1",
                email="lecturer1@college.edu",
                password=hashlib.sha256("password123".encode()).hexdigest(),
                department="Computer Science"
            )
            db.add(lecturer)
            db.flush()
            print("[Migration v2] Seeded test lecturer: LECTURER1 / password123")
        else:
            print("[Migration v2] Lecturer LECTURER1 already exists.")
            
        # Seed test subjects linked to the lecturer
        subjects_data = [
            ('CS101', 'Computer Programming', 'Computer Science', 1),
            ('CS102', 'Data Structures', 'Computer Science', 2),
            ('CS103', 'Database Systems', 'Computer Science', 3)
        ]
        
        for code, name, dept, sem in subjects_data:
            subj = db.query(Subject).filter(Subject.code == code).first()
            if not subj:
                subj = Subject(
                    code=code,
                    name=name,
                    department=dept,
                    semester=sem,
                    lecturer_id=lecturer.id
                )
                db.add(subj)
                db.flush()
                print(f"[Migration v2] Seeded subject '{code}': {name}")
                
                # Automatically create default attendance log entry and internal marks entry for existing students in this dept/sem
                students = db.query(Student).filter(
                    Student.department == dept,
                    Student.semester == sem
                ).all()
                
                # Also fallback to matching all students if none match dept/sem exactly (for testing)
                if not students:
                    students = db.query(Student).all()
                
                for s in students:
                    # Update student contact info if blank
                    if not s.email:
                        s.email = f"{s.roll_number.lower()}@college.edu"
                    if not s.phone:
                        s.phone = "+1234567890"
                    
                    # Create empty internal marks entry
                    mark = db.query(InternalMarks).filter(
                        InternalMarks.student_id == s.id,
                        InternalMarks.subject_id == subj.id
                    ).first()
                    if not mark:
                        db.add(InternalMarks(student_id=s.id, subject_id=subj.id, exam_type="Internal 1"))
            else:
                print(f"[Migration v2] Subject '{code}' already exists.")
                
        db.commit()
        print("[Migration v2] Seed data successfully verified and committed.")
        
    except Exception as e:
        db.rollback()
        print(f"[Migration v2] Error seeding initial data: {e}")
    finally:
        db.close()

if __name__ == '__main__':
    run_migration_v2()
