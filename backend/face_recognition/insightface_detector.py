"""
InsightFace-based Face Detector and Embedding Extractor.
Uses SCRFD for detection and ArcFace (ResNet50) for generating 512-dim face embeddings.
"""
import os
import cv2
import numpy as np
import warnings

# Suppress standard onnxruntime warnings
warnings.filterwarnings('ignore', category=UserWarning, module='onnxruntime')

import os
from insightface.app import FaceAnalysis


class InsightFaceDetector:
    """
    Detects faces and extracts ArcFace embeddings using the InsightFace framework.
    """

    def __init__(self):
        # buffalo_l is the model pack containing detection and w600k_r50 recognition models.
        # ctx_id=-1 forces CPU execution.
        model_root = os.environ.get('INSIGHTFACE_ROOT')
        if not model_root:
            # Fallback: check if 'models' directory exists in project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            project_models_dir = os.path.join(project_root, 'models')
            if os.path.exists(project_models_dir):
                model_root = project_models_dir
            else:
                model_root = os.path.expanduser('~/.insightface')
                
        self.app = FaceAnalysis(name='buffalo_l', root=model_root)
        self.app.prepare(ctx_id=-1, det_size=(640, 640))

        # Support custom ONNX Liveness Model (MiniFASNetV2)
        model_url = "https://huggingface.co/garciafido/minifasnet-v2-anti-spoofing-onnx/resolve/main/minifasnet_v2.onnx"
        self.liveness_model_path = os.path.join(model_root, 'minifasnet_v2.onnx')
        
        # Programmatic fallback download if not already cached
        if not os.path.exists(self.liveness_model_path):
            print(f"[InsightFaceDetector] Liveness model not found at {self.liveness_model_path}. Downloading...")
            try:
                import requests
                os.makedirs(os.path.dirname(self.liveness_model_path), exist_ok=True)
                response = requests.get(model_url, stream=True, timeout=30)
                response.raise_for_status()
                with open(self.liveness_model_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print("[InsightFaceDetector] Liveness model downloaded successfully.")
            except Exception as e:
                print(f"[InsightFaceDetector] Failed to download liveness model: {e}")

        # Initialize ONNX inference session for liveness
        if os.path.exists(self.liveness_model_path):
            try:
                import onnxruntime as ort
                self.liveness_session = ort.InferenceSession(self.liveness_model_path, providers=['CPUExecutionProvider'])
                print("[InsightFaceDetector] Liveness ONNX model loaded successfully.")
            except Exception as e:
                self.liveness_session = None
                print(f"[InsightFaceDetector] Failed to load liveness ONNX session: {e}")
        else:
            self.liveness_session = None

    def detect_faces(self, frame):
        """
        Detect faces in a BGR OpenCV frame.
        Returns list of (x, y, w, h) bounding boxes, sorted by area descending (largest first).
        """
        try:
            faces = self.app.get(frame)
            if not faces:
                return []
            
            bboxes = []
            for face in faces:
                x1, y1, x2, y2 = face.bbox
                x = int(max(0, x1))
                y = int(max(0, y1))
                w = int(max(1, x2 - x1))
                h = int(max(1, y2 - y1))
                bboxes.append([x, y, w, h])
                
            # Sort by area (w * h) descending
            bboxes = sorted(bboxes, key=lambda b: b[2] * b[3], reverse=True)
            return bboxes
        except Exception as e:
            print(f"[InsightFaceDetector] Error detecting faces: {e}")
            return []

    def extract_embedding(self, frame, bbox):
        """
        Extract the 512-dimensional ArcFace embedding from the face closest to the bbox region.
        """
        try:
            faces = self.app.get(frame)
            if not faces:
                return None
                
            if len(faces) == 1:
                return faces[0].embedding

            tx, ty, tw, th = bbox
            target_center = (tx + tw / 2, ty + th / 2)
            
            best_face = None
            min_dist = float('inf')
            
            for face in faces:
                x1, y1, x2, y2 = face.bbox
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                dist = (cx - target_center[0])**2 + (cy - target_center[1])**2
                if dist < min_dist:
                    min_dist = dist
                    best_face = face
                    
            if best_face is not None:
                return best_face.embedding
            return None
        except Exception as e:
            print(f"[InsightFaceDetector] Error extracting embedding: {e}")
            return None

    def preprocess_for_training(self, frame):
        """
        Full pipeline: detect → get embedding for the largest face.
        Returns (embedding, bbox) or (None, None).
        """
        try:
            faces = self.app.get(frame)
            if not faces:
                return None, None
                
            # Sort faces by bbox area descending
            sorted_faces = sorted(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
            largest_face = sorted_faces[0]
            
            x1, y1, x2, y2 = largest_face.bbox
            x = int(max(0, x1))
            y = int(max(0, y1))
            w = int(max(1, x2 - x1))
            h = int(max(1, y2 - y1))
            
            return largest_face.embedding, [x, y, w, h]
        except Exception as e:
            print(f"[InsightFaceDetector] Error preprocessing frame: {e}")
            return None, None

    def detect_liveness(self, frame, bbox):
        """
        Liveness check bypassed by user request.
        Always returns True.
        """
        return True, 100.0, "Liveness check bypassed."
