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
        Verify if the face in the bounding box is a live person or a potential spoof (photo/screen replay).
        First tries to use the MiniFASNetV2 ONNX model, and falls back to Laplacian/HSV heuristics if unavailable.
        
        Returns:
            (is_live: bool, confidence_score: float, message: str)
        """
        if getattr(self, 'liveness_session', None) is not None:
            try:
                import cv2
                x, y, w, h = bbox
                h_frame, w_frame = frame.shape[:2]
                
                # Crop face with 2.7x scale margin for MiniFASNetV2
                cx = x + w / 2.0
                cy = y + h / 2.0
                max_size = max(w, h)
                crop_size = int(max_size * 2.7)
                
                x1 = int(cx - crop_size / 2.0)
                y1 = int(cy - crop_size / 2.0)
                x2 = x1 + crop_size
                y2 = y1 + crop_size
                
                pad_left = max(0, -x1)
                pad_top = max(0, -y1)
                pad_right = max(0, x2 - w_frame)
                pad_bottom = max(0, y2 - h_frame)
                
                x1_clamped = max(0, x1)
                y1_clamped = max(0, y1)
                x2_clamped = min(w_frame, x2)
                y2_clamped = min(h_frame, y2)
                
                cropped = frame[y1_clamped:y2_clamped, x1_clamped:x2_clamped]
                if cropped.size == 0:
                    return False, 0.0, "Face crop is empty."
                    
                if pad_left > 0 or pad_top > 0 or pad_right > 0 or pad_bottom > 0:
                    cropped = cv2.copyMakeBorder(cropped, pad_top, pad_bottom, pad_left, pad_right, cv2.BORDER_CONSTANT, value=[0, 0, 0])
                
                # Resize to 80x80
                face_crop_80 = cv2.resize(cropped, (80, 80))
                
                # Preprocess: BGR format, normalized to [0, 1]
                input_data = face_crop_80.astype(np.float32) / 255.0
                input_data = np.transpose(input_data, (2, 0, 1))  # HWC to CHW
                input_data = np.expand_dims(input_data, axis=0)   # Add batch dimension: (1, 3, 80, 80)
                
                # Run inference
                input_name = self.liveness_session.get_inputs()[0].name
                outputs = self.liveness_session.run(None, {input_name: input_data})
                logits = outputs[0]
                
                # Apply Softmax to logits
                exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
                probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
                probs = probs[0]  # Get first item in batch: [p_live, p_print, p_replay]
                
                p_live = float(probs[0])
                p_print = float(probs[1])
                p_replay = float(probs[2])
                
                # Threshold for being a real person (e.g. 0.70 / 70%)
                THRESHOLD = 0.70
                is_live = p_live >= THRESHOLD
                confidence = p_live * 100.0
                
                if is_live:
                    return True, confidence, f"Liveness check passed (Live: {confidence:.1f}%)."
                else:
                    if p_print > p_replay:
                        return False, confidence, f"Liveness check failed (Spoof print attack detected: {p_print*100:.1f}% confidence)."
                    else:
                        return False, confidence, f"Liveness check failed (Spoof replay attack detected: {p_replay*100:.1f}% confidence)."
                        
            except Exception as e:
                print(f"[Liveness] Error running ONNX model: {e}. Falling back to heuristics...")
        
        # ── HEURISTIC FALLBACK (Laplacian + HSV) ──
        try:
            import cv2
            x, y, w, h = bbox
            h_frame, w_frame = frame.shape[:2]
            
            # Crop the face region with a small padding
            pad_w = int(w * 0.1)
            pad_h = int(h * 0.1)
            x1 = max(0, x - pad_w)
            y1 = max(0, y - pad_h)
            x2 = min(w_frame, x + w + pad_w)
            y2 = min(h_frame, y + h + pad_h)
            
            face_roi = frame[y1:y2, x1:x2]
            if face_roi.size == 0:
                return False, 0.0, "Face ROI is empty."
                
            face_gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(face_gray, cv2.CV_64F).var()
            
            hsv = cv2.cvtColor(face_roi, cv2.COLOR_BGR2HSV)
            lower_skin_1 = np.array([0, 20, 50], dtype=np.uint8)
            upper_skin_1 = np.array([25, 255, 255], dtype=np.uint8)
            lower_skin_2 = np.array([165, 20, 50], dtype=np.uint8)
            upper_skin_2 = np.array([180, 255, 255], dtype=np.uint8)
            
            mask1 = cv2.inRange(hsv, lower_skin_1, upper_skin_1)
            mask2 = cv2.inRange(hsv, lower_skin_2, upper_skin_2)
            skin_mask = mask1 | mask2
            
            skin_pixels = np.sum(skin_mask > 0)
            total_pixels = skin_mask.size
            skin_ratio = skin_pixels / total_pixels if total_pixels > 0 else 0.0
            
            is_sharp = bool(laplacian_var >= 60.0)
            has_skin = bool(skin_ratio >= 0.15)
            
            sharpness_score = min(1.0, laplacian_var / 300.0)
            skin_score = min(1.0, skin_ratio / 0.60)
            confidence = (sharpness_score * 0.4 + skin_score * 0.6) * 100.0
            
            if not is_sharp:
                return False, confidence, f"Liveness check failed (Heuristics): Image lacks 3D texture/sharpness (var={laplacian_var:.1f}). Possible photo/screen spoof."
                
            if not has_skin:
                return False, confidence, f"Liveness check failed (Heuristics): Grayscale/color distortion detected (skin={skin_ratio*100:.1f}%). Possible print/replay spoof."
                
            return True, confidence, "Liveness check passed (Heuristics)."
            
        except Exception as e:
            print(f"[Liveness] Error detecting liveness: {e}")
            return True, 100.0, "Liveness check bypassed due to error."
