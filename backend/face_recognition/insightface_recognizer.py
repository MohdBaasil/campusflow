"""
InsightFace-based Face Recognizer using SVM classifier on ArcFace embeddings.
"""
import numpy as np
import os
import joblib
from sklearn.svm import SVC
from sklearn.preprocessing import LabelEncoder

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'models')
MODEL_PATH = os.path.join(MODEL_DIR, 'insightface_svm_model.pkl')
LABELS_PATH = os.path.join(MODEL_DIR, 'insightface_label_encoder.pkl')


class InsightFaceRecognizer:
    """
    Recognizes faces using ArcFace deep embeddings + SVM classifier.
    """

    def __init__(self):
        os.makedirs(MODEL_DIR, exist_ok=True)
        self.model = None
        self.label_encoder = LabelEncoder()
        self.is_trained = False
        self._load_model()

    def _load_model(self):
        """Load existing trained SVM model from disk if available."""
        if os.path.exists(MODEL_PATH) and os.path.exists(LABELS_PATH):
            try:
                self.model = joblib.load(MODEL_PATH)
                self.label_encoder = joblib.load(LABELS_PATH)
                self.is_trained = True
                print("[InsightFaceRecognizer] SVM model loaded successfully.")
            except Exception as e:
                print(f"[InsightFaceRecognizer] Failed to load model: {e}")
                self.is_trained = False

    def train(self, features_list, labels):
        """
        Train the SVM classifier on ArcFace feature vectors.
        """
        if len(features_list) < 2:
            raise ValueError("Need at least 2 samples to train.")

        X = np.array(features_list)
        y = self.label_encoder.fit_transform(labels)

        # RBF SVM works wonderfully on deep learning embeddings
        self.model = SVC(kernel='rbf', C=10, gamma='scale', probability=True)
        self.model.fit(X, y)
        self.is_trained = True

        # Persist SVM model
        joblib.dump(self.model, MODEL_PATH)
        joblib.dump(self.label_encoder, LABELS_PATH)
        print(f"[InsightFaceRecognizer] Model trained on {len(labels)} samples, {len(set(labels))} students.")
        return True

    def predict(self, embedding):
        """
        Predict student identity from ArcFace embedding.
        Uses Cosine Similarity verification to avoid false positives.

        Returns:
            (student_id: str, confidence: float) or (None, 0.0) if unknown
        """
        SYNTHETIC_LABEL = "__synthetic_negative__"

        if not self.is_trained or self.model is None:
            return None, 0.0

        try:
            features = np.array(embedding).reshape(1, -1)
            classes = self.label_encoder.classes_
            n_classes = len(classes)

            if n_classes < 2:
                return None, 0.0

            # Predict class index using the SVM model
            pred_class_idx = int(self.model.predict(features)[0])
            predicted_label = str(classes[pred_class_idx])

            # If predicted label is the synthetic class, it's unknown
            if predicted_label == SYNTHETIC_LABEL:
                return None, 0.0

            # ── Verification step using Cosine Similarity against DB templates ──
            try:
                from backend.database.db import get_db, FaceEmbedding
                db = get_db()
                embeddings = db.query(FaceEmbedding).filter(FaceEmbedding.student_id == int(predicted_label)).all()
                db.close()

                if embeddings:
                    max_similarity = 0.0
                    for emb_record in embeddings:
                        stored_emb = np.frombuffer(emb_record.embedding, dtype=np.float32)
                        dot_product = np.dot(embedding, stored_emb)
                        norm_a = np.linalg.norm(embedding)
                        norm_b = np.linalg.norm(stored_emb)
                        similarity = dot_product / (norm_a * norm_b) if (norm_a > 0 and norm_b > 0) else 0.0
                        if similarity > max_similarity:
                            max_similarity = similarity
                    
                    confidence = float(max_similarity)
                    # ArcFace Cosine similarity is usually very high for matching faces.
                    # Standard verification threshold: 0.50 - 0.60 is common, let's use 0.55.
                    if confidence < 0.55:
                        return None, confidence
                    return predicted_label, confidence
            except Exception as db_err:
                print(f"[InsightFaceRecognizer] Database verification failed: {db_err}")

            # ── Fallback: SVM decision values softmax ──
            d = self.model.decision_function(features)[0]

            if n_classes == 2:
                val = float(d)
                p1 = 1.0 / (1.0 + np.exp(-val))
                p0 = 1.0 - p1
                proba = [p0, p1]
            else:
                exp_d = np.exp(d - np.max(d))
                proba = exp_d / np.sum(exp_d)

            confidence = float(proba[pred_class_idx])

            if confidence < 0.55:
                return None, confidence

            return predicted_label, confidence
        except Exception as e:
            print(f"[InsightFaceRecognizer] Prediction error: {e}")
            return None, 0.0

    def get_num_classes(self):
        """Return the number of trained student classes."""
        if self.is_trained and hasattr(self.label_encoder, 'classes_'):
            return len(self.label_encoder.classes_)
        return 0
