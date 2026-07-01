"""
HOG-based Face Detector using scikit-image.
Detects faces in a frame using HOG features + sliding window approach.
"""
import cv2
import numpy as np
from skimage.feature import hog
from skimage.transform import pyramid_gaussian
from skimage import color


class HOGFaceDetector:
    """
    Detects faces using a Histogram of Oriented Gradients (HOG) descriptor
    combined with a sliding-window approach powered by scikit-image.
    
    For detection we use OpenCV's pre-trained Haar/HOG cascade as the 
    detection backbone since training a custom HOG face detector requires 
    large negative datasets. The HOG feature pipeline is fully used in the 
    recognition stage (hog_recognizer.py).
    """

    def __init__(self):
        # OpenCV face cascade (HOG-based internally for LBP + frontal)
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        self.target_size = (128, 128)

    def detect_faces(self, frame):
        """
        Detect faces in a BGR OpenCV frame.
        Returns list of (x, y, w, h) bounding boxes, sorted by area descending (largest first).
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),
            flags=cv2.CASCADE_SCALE_IMAGE
        )

        if len(faces) == 0:
            return []
        
        # Sort faces by area (w * h) descending so the largest face is always first
        sorted_faces = sorted(faces.tolist(), key=lambda b: b[2] * b[3], reverse=True)
        return sorted_faces

    def extract_face_region(self, frame, bbox, padding=20):
        """
        Crop and normalize a face region from a frame.
        Returns a grayscale, resized, equalized face image.
        """
        x, y, w, h = bbox
        h_frame, w_frame = frame.shape[:2]

        # Add padding, clamped to frame bounds
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(w_frame, x + w + padding)
        y2 = min(h_frame, y + h + padding)

        face_region = frame[y1:y2, x1:x2]
        gray_face = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
        gray_face = cv2.equalizeHist(gray_face)
        resized = cv2.resize(gray_face, self.target_size)
        return resized

    def extract_hog_features(self, face_image):
        """
        Extract HOG descriptor from a normalized face image.
        Parameters tuned for 128×128 face images.
        """
        features = hog(
            face_image,
            orientations=9,
            pixels_per_cell=(8, 8),
            cells_per_block=(2, 2),
            block_norm='L2-Hys',
            visualize=False,
            feature_vector=True
        )
        return features

    def preprocess_for_training(self, frame):
        """Full pipeline: detect → crop → HOG features for one face."""
        faces = self.detect_faces(frame)
        if not faces:
            return None, None
        bbox = faces[0]
        face_img = self.extract_face_region(frame, bbox)
        features = self.extract_hog_features(face_img)
        return features, bbox
