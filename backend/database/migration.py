"""
Database migration script.
Detects legacy 8100-dimensional HOG face embeddings and converts them to 512-dimensional ArcFace embeddings.
"""
import os
import cv2
import numpy as np
from backend.database.db import get_db, Student, FaceEmbedding
from backend.face_recognition.insightface_detector import InsightFaceDetector
from backend.face_recognition.trainer import train_model


def run_migration():
    """
    Check if the database contains old HOG embeddings.
    If so, re-extract and save 512-dimensional ArcFace embeddings from physical photos on disk.
    """
    db = get_db()
    try:
        # Check if any embedding exists
        first_emb = db.query(FaceEmbedding).first()
        if not first_emb:
            print("[Migration] Database is empty. No migration needed.")
            return

        # Check embedding length
        emb_data = np.frombuffer(first_emb.embedding, dtype=np.float32)
        if len(emb_data) == 512:
            print("[Migration] Database already uses 512-dimensional ArcFace embeddings. Skipping.")
            return

        print(f"[Migration] Legacy HOG embeddings detected (dim={len(emb_data)}). Starting migration...")

        # Initialize detector for migration
        detector = InsightFaceDetector()

        # Delete all old embeddings
        db.query(FaceEmbedding).delete()
        db.commit()

        students = db.query(Student).all()
        migrated_count = 0
        failed_count = 0

        for student in students:
            if not student.photo_dir or not os.path.exists(student.photo_dir):
                print(f"[Migration] Warning: Photo directory not found for {student.name} ({student.roll_number})")
                continue

            print(f"[Migration] Processing photos for {student.name}...")
            for filename in os.listdir(student.photo_dir):
                if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                    continue

                img_path = os.path.join(student.photo_dir, filename)
                frame = cv2.imread(img_path)
                if frame is None:
                    continue

                # Preprocess frame to extract ArcFace embedding
                embedding, _ = detector.preprocess_for_training(frame)
                if embedding is not None:
                    embedding_bytes = embedding.astype(np.float32).tobytes()
                    face_emb = FaceEmbedding(student_id=student.id, embedding=embedding_bytes)
                    db.add(face_emb)
                    migrated_count += 1
                else:
                    failed_count += 1
                    print(f"[Migration] Failed to detect face in {filename} for {student.name}")

        db.commit()
        print(f"[Migration] Re-extracted {migrated_count} ArcFace embedding(s) successfully (failed: {failed_count}).")

        # Automatically train the new SVM model
        print("[Migration] Re-training the SVM model with new embeddings...")
        success, message, _ = train_model()
        if success:
            print(f"[Migration] {message}")
        else:
            print(f"[Migration] Model training failed: {message}")

    except Exception as e:
        db.rollback()
        print(f"[Migration] Error during migration: {e}")
    finally:
        db.close()
