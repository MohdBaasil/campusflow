"""
Training pipeline for the InsightFace + SVM face recognition model.
Scans the known_faces directory, extracts ArcFace embeddings, and trains the SVM.
Supports single-student training using a padded dummy class strategy.
"""
import os
import cv2
import numpy as np
from backend.face_recognition.insightface_detector import InsightFaceDetector
from backend.face_recognition.insightface_recognizer import InsightFaceRecognizer

KNOWN_FACES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'data', 'known_faces'
)


def train_model():
    """
    Load all registered face images, extract ArcFace embeddings, and train the SVM.
    Supports single-student mode using a synthetic negative class.
    Returns (success: bool, message: str, details: dict)
    """
    detector = InsightFaceDetector()
    recognizer = InsightFaceRecognizer()

    features_list = []
    labels = []
    student_counts = {}
    failed = []

    if not os.path.exists(KNOWN_FACES_DIR):
        return False, "No known_faces directory found. Please register at least one student.", {}

    # Iterate student folders: data/known_faces/<student_id>/
    for student_id in os.listdir(KNOWN_FACES_DIR):
        student_dir = os.path.join(KNOWN_FACES_DIR, student_id)
        if not os.path.isdir(student_dir):
            continue

        count = 0
        for filename in sorted(os.listdir(student_dir)):
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue

            img_path = os.path.join(student_dir, filename)
            frame = cv2.imread(img_path)
            if frame is None:
                failed.append(img_path)
                continue

            # Preprocess to get embedding
            embedding, _ = detector.preprocess_for_training(frame)
            if embedding is not None:
                features_list.append(embedding.tolist())
                labels.append(student_id)
                count += 1

        if count > 0:
            student_counts[student_id] = count

    if not features_list:
        return False, "No usable face images found. Please register students with clear face photos.", {
            'students_found': 0,
            'failed_images': failed
        }

    # ── Single-student mode: create a synthetic negative class ──
    unique_classes = list(set(labels))
    if len(unique_classes) == 1:
        print("[Trainer] Single student detected — adding synthetic negative samples for SVM.")
        sample_features = np.array(features_list)
        feature_dim = sample_features.shape[1]

        # Generate synthetic negative samples via Gaussian noise perturbation
        rng = np.random.RandomState(42)
        n_synthetic = max(len(features_list), 5)
        synthetic = rng.randn(n_synthetic, feature_dim) * 0.5
        # Normalize to [-1, 1] range like standard features
        synthetic = np.clip(synthetic, -1, 1)

        SYNTHETIC_LABEL = "__synthetic_negative__"
        for s in synthetic:
            features_list.append(s.tolist())
            labels.append(SYNTHETIC_LABEL)

        print(f"[Trainer] Added {n_synthetic} synthetic negative samples.")

    try:
        recognizer.train(features_list, labels)
        num_real_students = len(student_counts)
        return True, f"Model trained successfully! {len(features_list)} images processed across {num_real_students} student(s).", {
            'total_images': sum(student_counts.values()),
            'students': student_counts,
            'failed_images': failed,
            'single_student_mode': len(unique_classes) == 1
        }
    except Exception as e:
        return False, f"Training failed: {str(e)}", {}
