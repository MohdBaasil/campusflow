"""
migration_seed_students.py
Runs at startup: imports students from seed_students.json if they don't already exist.
This syncs the HuggingFace deployment database with local student registrations.
"""
import os
import json
import base64
import hashlib
import numpy as np

SEED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'seed_students.json')


def run_seed_migration():
    if not os.path.exists(SEED_FILE):
        print("[SeedMigration] No seed_students.json found. Skipping.")
        return

    from backend.database.db import SessionLocal, Student, FaceEmbedding

    with open(SEED_FILE, 'r', encoding='utf-8') as f:
        seed_data = json.load(f)

    db = SessionLocal()
    imported = 0
    skipped = 0

    try:
        for s in seed_data:
            roll = s['roll_number'].strip().upper()

            # Skip if already exists
            existing = db.query(Student).filter(Student.roll_number == roll).first()
            if existing:
                skipped += 1
                continue

            # Create student
            password = hashlib.sha256(roll.encode()).hexdigest()
            student = Student(
                name=s['name'],
                roll_number=roll,
                department=s.get('department', ''),
                phone=s.get('phone', ''),
                email=s.get('email', ''),
                semester=s.get('semester', ''),
                password=password
            )
            db.add(student)
            db.flush()  # Get auto-generated ID

            # Import face embeddings
            for emb_b64 in s.get('embeddings_b64', []):
                try:
                    emb_bytes = base64.b64decode(emb_b64)
                    # Validate: should be 512 float32 = 2048 bytes
                    arr = np.frombuffer(emb_bytes, dtype=np.float32)
                    if arr.shape[0] == 512:
                        face_emb = FaceEmbedding(
                            student_id=student.id,
                            embedding=emb_bytes
                        )
                        db.add(face_emb)
                except Exception as e:
                    print(f"[SeedMigration] Failed to import embedding for {s['name']}: {e}")

            imported += 1

        db.commit()
        print(f"[SeedMigration] Done — {imported} students imported, {skipped} already existed.")

        # Retrain model if any new students were imported
        if imported > 0:
            try:
                from backend.face_recognition.trainer import train_model
                success, msg, _ = train_model()
                print(f"[SeedMigration] Model retrained: {msg}")
            except Exception as e:
                print(f"[SeedMigration] Model retraining failed: {e}")

    except Exception as e:
        db.rollback()
        print(f"[SeedMigration] ERROR: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()
