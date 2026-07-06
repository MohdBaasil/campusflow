"""
seed_curriculum.py — Seeds comprehensive academic curriculum data.
Generates realistic lecturers and subjects matching the user's custom 8-semester syllabus.
"""
import os
import sys
import hashlib

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database.db import get_db, Lecturer, Subject, Student, InternalMarks, init_db

# Real academic departments & specializations
PROGRAMS = {
    "Computer Science & Engineering": {"type": "BTech", "code_pref": "CSE", "spec": "Core"},
    "CSE - Artificial Intelligence & Machine Learning": {"type": "BTech", "code_pref": "CSM", "spec": "Artificial Intelligence & Machine Learning"},
    "CSE - Data Science": {"type": "BTech", "code_pref": "CSD", "spec": "Data Science"},
    "CSE - Cyber Security": {"type": "BTech", "code_pref": "CSC", "spec": "Cyber Security"},
    "CSE - Cloud Computing": {"type": "BTech", "code_pref": "CSV", "spec": "Cloud Computing"},
    "CSE - Internet of Things": {"type": "BTech", "code_pref": "CSI", "spec": "Internet of Things"},
    "CSE - Blockchain": {"type": "BTech", "code_pref": "CSB", "spec": "Blockchain"},
    "CSE - Business Systems": {"type": "BTech", "code_pref": "CSG", "spec": "Business Systems"},
    "CSE - Full Stack Development": {"type": "BTech", "code_pref": "CSF", "spec": "Full Stack Development"},
    "Information Science & Engineering": {"type": "BTech", "code_pref": "ISE", "spec": "Core"},
    "Artificial Intelligence & Data Science": {"type": "BTech", "code_pref": "ADS", "spec": "Artificial Intelligence & Data Science"},
    "Electronics & Communication Engineering": {"type": "BTech", "code_pref": "ECE", "spec": "Core"},
    "Electrical & Electronics Engineering": {"type": "BTech", "code_pref": "EEE", "spec": "Core"},
    "Mechanical Engineering": {"type": "BTech", "code_pref": "MME", "spec": "Core"},
    "Civil Engineering": {"type": "BTech", "code_pref": "CIV", "spec": "Core"},
    "Robotics & Automation": {"type": "BTech", "code_pref": "ROB", "spec": "Robotics & Automation"},
    "Aerospace Engineering": {"type": "BTech", "code_pref": "ASE", "spec": "Core"},
    "Biotechnology": {"type": "BTech", "code_pref": "BIO", "spec": "Core"},
    "Chemical Engineering": {"type": "BTech", "code_pref": "CHE", "spec": "Core"},
    "MBA": {"type": "MBA", "code_pref": "MBA", "spec": "Business Analytics"},
    "MCA": {"type": "MCA", "code_pref": "MCA", "spec": "Computer Applications"},
    "BCA": {"type": "BCA", "code_pref": "BCA", "spec": "Core"},
    "BBA": {"type": "BBA", "code_pref": "BBA", "spec": "Core"}
}

# The user's exact 8-semester syllabus structure
CUSTOM_SYLLABUS = {
    1: [
        ("Engineering Mathematics I", 4),
        ("Engineering Physics", 4),
        ("Basic Electrical Engineering", 4),
        ("Programming in C", 4),
        ("Engineering Graphics", 3)
    ],
    2: [
        ("Mathematics II", 4),
        ("Data Structures", 4),
        ("Digital Logic", 4),
        ("OOP using Java", 4),
        ("Environmental Science", 2)
    ],
    3: [
        ("DBMS", 4),
        ("Operating Systems", 4),
        ("Computer Networks", 4),
        ("Software Engineering", 4),
        ("Python Programming", 3)
    ],
    4: [
        ("Design and Analysis of Algorithms", 4),
        ("Compiler Design", 4),
        ("Artificial Intelligence", 4),
        ("Machine Learning", 4),
        ("Web Technologies", 4)
    ],
    5: [
        ("Cloud Computing", 4),
        ("Cyber Security", 4),
        ("Distributed Systems", 4),
        ("Data Mining", 4),
        ("Software Project Management", 3)
    ],
    6: [
        ("Blockchain", 4),
        ("Big Data Analytics", 4),
        ("DevOps", 4),
        ("Internet of Things", 4),
        ("Elective I", 3)
    ],
    7: [
        ("Major Project", 6),
        ("Internship", 4),
        ("Elective II", 3),
        ("Elective III", 3)
    ],
    8: [
        ("Capstone Project", 8),
        ("Seminar", 2),
        ("Industrial Training", 4)
    ]
}

# Generic names for realistic lecturers
LECTURER_NAMES = [
    "Dr. Ramesh Chandra", "Dr. Priya Gowda", "Dr. Amit Verma", "Dr. Sudha Murthy",
    "Dr. Satya Nadella", "Dr. Sundar Pichai", "Dr. Raghuram Rajan", "Dr. Vikram Sarabhai",
    "Dr. APJ Abdul Kalam", "Dr. Homi Bhabha", "Dr. CV Raman", "Dr. Shakuntala Devi",
    "Dr. CNR Rao", "Dr. Tessy Thomas", "Dr. Jagadish Chandra Bose", "Dr. Srinivasa Ramanujan",
    "Dr. Satyendra Nath Bose", "Dr. Visvesvaraya", "Dr. Meghanad Saha", "Dr. Har Gobind Khorana",
    "Dr. Venkatraman Ramakrishnan", "Dr. Shanti Swarup Bhatnagar", "Dr. Rajeshwari Chatterjee",
    "Dr. Anna Mani", "Dr. Janaki Ammal", "Dr. Kamala Sohonie", "Dr. Asima Chatterjee"
]

def seed_database():
    print("[Seed] Opening database connection...")
    db = get_db()
    try:
        # Create lecturers list
        lecturer_map = {} # dept -> list of Lecturers
        
        print("[Seed] Seeding lecturers...")
        for i, (dept, meta) in enumerate(PROGRAMS.items()):
            lecturer_map[dept] = []
            
            # Generate 2 lecturers per department/specialization
            for l_idx in range(1, 3):
                emp_id = f"T-{meta['code_pref']}{l_idx:02d}"
                if dept == "Computer Science & Engineering" and l_idx == 1:
                    emp_id = "LECTURER1"
                
                # Check if lecturer already exists
                existing = db.query(Lecturer).filter(Lecturer.employee_id == emp_id).first()
                if existing:
                    lecturer_map[dept].append(existing)
                    continue
                
                name = LECTURER_NAMES[(i * 2 + l_idx - 1) % len(LECTURER_NAMES)]
                email = f"{name.lower().replace(' ', '.').replace('dr.', '')}@jainuniversity.ac.in"
                pwd_hash = hashlib.sha256("password123".encode()).hexdigest()
                
                lec = Lecturer(
                    name=name,
                    employee_id=emp_id,
                    email=email,
                    password=pwd_hash,
                    department=dept
                )
                db.add(lec)
                db.flush()
                lecturer_map[dept].append(lec)
                print(f"  + Seeded Lecturer: {name} ({emp_id}) for '{dept}'")

        print("[Seed] Seeding custom subjects...")
        subject_count = 0
        
        for dept, meta in PROGRAMS.items():
            type_ = meta["type"]
            code_pref = meta["code_pref"]
            spec = meta["spec"]
            lecturers = lecturer_map[dept]
            
            # MBA/MCA are 4 semesters, BCA/BBA are 6 semesters, Engineering BTech are 8 semesters
            if type_ in ("MBA", "MCA"):
                semesters = list(range(1, 5))
            elif type_ in ("BCA", "BBA"):
                semesters = list(range(1, 7))
            else:
                semesters = list(range(1, 9))

            for sem in semesters:
                subjects_list = CUSTOM_SYLLABUS.get(sem, [])
                
                for s_idx, (s_name, credits) in enumerate(subjects_list, 1):
                    code = f"23{code_pref}{sem}{s_idx:02d}"
                    
                    # Alternating assignment to department lecturers
                    assigned_lec = lecturers[s_idx % len(lecturers)]
                    
                    # Format subject names to specify PG focus if MBA/MCA
                    display_name = s_name
                    if type_ in ("MBA", "MCA"):
                        display_name = f"Advanced {s_name}" if "Project" not in s_name and "Internship" not in s_name else s_name

                    # Check if subject already exists
                    subj = db.query(Subject).filter(Subject.code == code).first()
                    if subj:
                        subj.name = display_name
                        subj.department = dept
                        subj.specialization = spec
                        subj.semester = sem
                        subj.credits = credits
                        subj.lecturer_id = assigned_lec.id
                    else:
                        subj = Subject(
                            code=code,
                            name=display_name,
                            department=dept,
                            specialization=spec,
                            semester=sem,
                            credits=credits,
                            lecturer_id=assigned_lec.id
                        )
                        db.add(subj)
                    db.flush()
                    subject_count += 1

                    # Setup default internal marks for students of this department & semester
                    students = db.query(Student).filter(
                        Student.department == dept,
                        Student.semester == sem
                    ).all()
                    
                    for s in students:
                        mark = db.query(InternalMarks).filter(
                            InternalMarks.student_id == s.id,
                            InternalMarks.subject_id == subj.id
                        ).first()
                        if not mark:
                            db.add(InternalMarks(
                                student_id=s.id,
                                subject_id=subj.id,
                                exam_type="Internal 1",
                                max_marks=50.0,
                                obtained_marks=0.0,
                                semester=sem,
                                remarks="Seeded custom curriculum"
                            ))

        db.commit()
        print(f"[Seed] Successfully seeded {subject_count} new subjects into the database.")
        
    except Exception as e:
        db.rollback()
        print(f"[Seed] Error occurred during seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    print("[Seed] Initializing database and running migrations...")
    init_db()
    seed_database()
