import os
import cv2
import numpy as np
import json
import urllib.request
from config import Config

# Try to import insightface
try:
    from insightface.app import FaceAnalysis
    _has_insightface = True
except Exception as e:
    print(f"[FaceEngine] InsightFace library import failed: {e}. Using legacy fallbacks.")
    FaceAnalysis = None
    _has_insightface = False

# Try to import face_recognition library globally
try:
    import face_recognition
    _has_face_rec_global = True
    print("[FaceEngine] Loaded face_recognition library (dlib backend).")
except ImportError:
    face_recognition = None
    _has_face_rec_global = False
    print("[FaceEngine] face_recognition library not found. Checking OpenCV DNN models...")

class FaceEngine:
    _has_face_rec = _has_face_rec_global
    _has_dnn_models = False
    _has_insightface = _has_insightface
    insightface_app = None
    
    # Paths for YuNet and SFace model files
    YUNET_MODEL_PATH = "face_detection_yunet_2023mar.onnx"
    SFACE_MODEL_PATH = "face_recognition_sface_2021dec.onnx"

    @classmethod
    def initialize(cls):
        """Initializes the backend. Checks for InsightFace first, then fallbacks to face_recognition and OpenCV DNN."""
        
        # 1. Try to load InsightFace
        if cls._has_insightface and FaceAnalysis is not None:
            model_name = Config.INSIGHTFACE_MODEL
            print(f"[FaceEngine] Initializing InsightFace {model_name} model pack...")
            try:
                cls.insightface_app = FaceAnalysis(name=model_name, providers=['CPUExecutionProvider'])
                cls.insightface_app.prepare(ctx_id=0, det_size=(640, 640))
                print(f"[FaceEngine] InsightFace {model_name} initialized successfully.")
                return # Successfully loaded primary backend!
            except Exception as e:
                print(f"[FaceEngine] Error loading InsightFace: {e}. Falling back to legacy engines.")
                cls.insightface_app = None
                cls._has_insightface = False

        # 2. Try to initialize existing engines
        if cls._has_face_rec:
            return
        
        # Check if ONNX models are available, download if missing
        if not os.path.exists(cls.YUNET_MODEL_PATH):
            print(f"[FaceEngine] Downloading YuNet model to {cls.YUNET_MODEL_PATH}...")
            try:
                url = "https://github.com/opencv/opencv_zoo/raw/master/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
                urllib.request.urlretrieve(url, cls.YUNET_MODEL_PATH)
                print("[FaceEngine] YuNet downloaded successfully.")
            except Exception as e:
                print(f"[FaceEngine] Failed to download YuNet: {e}. Falling back to Haar Cascades.")
                
        if not os.path.exists(cls.SFACE_MODEL_PATH):
            print(f"[FaceEngine] Downloading SFace model to {cls.SFACE_MODEL_PATH}...")
            try:
                url = "https://github.com/opencv/opencv_zoo/raw/master/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
                urllib.request.urlretrieve(url, cls.SFACE_MODEL_PATH)
                print("[FaceEngine] SFace downloaded successfully.")
            except Exception as e:
                print(f"[FaceEngine] Failed to download SFace: {e}. Falling back to local Haar + Pixel similarity.")

        if os.path.exists(cls.YUNET_MODEL_PATH) and os.path.exists(cls.SFACE_MODEL_PATH):
            try:
                # Test-load OpenCV DNN models
                cls.detector = cv2.FaceDetectorYN.create(cls.YUNET_MODEL_PATH, "", (320, 320))
                cls.recognizer = cv2.FaceRecognizerSF.create(cls.SFACE_MODEL_PATH, "")
                cls._has_dnn_models = True
                print("[FaceEngine] OpenCV DNN models loaded successfully (YuNet & SFace backend).")
            except Exception as e:
                print(f"[FaceEngine] Failed to initialize OpenCV DNN: {e}. Using Haar Cascade fallback.")
        else:
            print("[FaceEngine] ONNX models missing or failed. Using Haar Cascade fallback.")

    @classmethod
    def detect_faces(cls, img_np):
        """
        Detects faces in an image and returns a list of bounding boxes (x, y, w, h).
        """
        # 1. Primary: InsightFace RetinaFace detector
        if cls._has_insightface and cls.insightface_app is not None:
            faces = cls.insightface_app.get(img_np)
            boxes = []
            for face in faces:
                bbox = face.bbox.astype(int)
                x = int(max(0, bbox[0]))
                y = int(max(0, bbox[1]))
                w = int(min(img_np.shape[1] - x, bbox[2] - bbox[0]))
                h = int(min(img_np.shape[0] - y, bbox[3] - bbox[1]))
                boxes.append((x, y, w, h))
            return boxes

        # 2. Existing option: face_recognition (dlib)
        if cls._has_face_rec and face_recognition is not None:
            rgb_img = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
            locations = face_recognition.face_locations(rgb_img)
            boxes = []
            for (top, right, bottom, left) in locations:
                boxes.append((int(left), int(top), int(right - left), int(bottom - top)))
            return boxes

        # 3. Existing option: SFace / YuNet
        if cls._has_dnn_models:
            h, w = img_np.shape[:2]
            cls.detector.setInputSize((w, h))
            _, faces = cls.detector.detect(img_np)
            boxes = []
            if faces is not None:
                for face in faces:
                    coords = face[:4].astype(int)
                    boxes.append((int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3])))
            return boxes

        # 4. Fallback Haar Cascades
        cascade_path = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
        face_cascade = cv2.CascadeClassifier(cascade_path)
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]

    @classmethod
    def get_embeddings(cls, img_np, boxes=None):
        """
        Generates face embeddings for the detected faces.
        Returns a list of list of floats (embeddings).
        """
        # 1. Primary: InsightFace ArcFace (512-D)
        if cls._has_insightface and cls.insightface_app is not None:
            faces = cls.insightface_app.get(img_np)
            if not faces:
                return []
            return [face.embedding.tolist() for face in faces]

        # 2. Existing option: face_recognition (128-D)
        if boxes is None:
            boxes = cls.detect_faces(img_np)
        if not boxes:
            return []

        if cls._has_face_rec and face_recognition is not None:
            rgb_img = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
            locations = [(y, x + w, y + h, x) for (x, y, w, h) in boxes]
            encodings = face_recognition.face_encodings(rgb_img, locations)
            return [enc.tolist() for enc in encodings]

        # 3. Existing option: OpenCV DNN (112-D)
        if cls._has_dnn_models:
            embeddings = []
            for box in boxes:
                h, w = img_np.shape[:2]
                cls.detector.setInputSize((w, h))
                _, faces = cls.detector.detect(img_np)
                matched_face = None
                if faces is not None:
                    for face in faces:
                        fx, fy, fw, fh = face[:4].astype(int)
                        if abs(fx - box[0]) < 30 and abs(fy - box[1]) < 30:
                            matched_face = face
                            break
                if matched_face is not None:
                    aligned_face = cls.recognizer.alignCrop(img_np, matched_face)
                    feat = cls.recognizer.feature(aligned_face)
                    embeddings.append(feat[0].tolist())
                else:
                    x, y, w, h = box
                    x_start = max(0, x)
                    y_start = max(0, y)
                    x_end = min(img_np.shape[1], x + w)
                    y_end = min(img_np.shape[0], y + h)
                    crop = img_np[y_start:y_end, x_start:x_end]
                    if crop.size > 0:
                        aligned_crop = cv2.resize(crop, (112, 112))
                        feat = cls.recognizer.feature(aligned_crop)
                        embeddings.append(feat[0].tolist())
            return embeddings

        # 4. Fallback pixel similarity (256-D)
        embeddings = []
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        for (x, y, w, h) in boxes:
            x_start = max(0, x)
            y_start = max(0, y)
            x_end = min(img_np.shape[1], x + w)
            y_end = min(img_np.shape[0], y + h)
            crop = gray[y_start:y_end, x_start:x_end]
            if crop.size > 0:
                crop = cv2.equalizeHist(crop)
                resized = cv2.resize(crop, (16, 16))
                vector = resized.flatten().astype(float)
                norm = np.linalg.norm(vector)
                if norm > 0:
                    vector = vector / norm
                embeddings.append(vector.tolist())
            else:
                embeddings.append([0.0] * 256)
        return embeddings

    @classmethod
    def compare_faces(cls, embedding1, embedding2, threshold=None):
        """
        Compares two face embeddings using Dot Product (Cosine Similarity) method.
        Returns (is_match, similarity_score).
        """
        eb1 = np.array(embedding1)
        eb2 = np.array(embedding2)
        
        dot_product = np.dot(eb1, eb2)
        norm_a = np.linalg.norm(eb1)
        norm_b = np.linalg.norm(eb2)
        
        if norm_a == 0 or norm_b == 0:
            return False, 0.0
            
        similarity = float(dot_product / (norm_a * norm_b))
        
        # Check active model version from vector dimension
        dim = len(embedding1)
        
        if dim == 512:
            # 1. InsightFace ArcFace
            limit = threshold if threshold is not None else 0.45
            is_match = similarity >= limit
            return bool(is_match), similarity
            
        # For old system options (dlib, SFace, Haar):
        # Auto-convert old distance parameter if supplied
        if threshold is not None and threshold <= 0.6:
            threshold = float(1.0 - (threshold ** 2) / 2.0)
            
        if dim == 128:
            # 2. dlib face_recognition
            limit = threshold if threshold is not None else 0.85
            is_match = similarity >= limit
            return bool(is_match), similarity
            
        if dim == 112:
            # 3. SFace ONNX
            limit = 0.40
            if threshold is not None:
                limit = float(threshold * 0.47)
            is_match = similarity >= limit
            return bool(is_match), similarity
            
        # 4. Fallback pixel similarity (256-D)
        limit = threshold if threshold is not None else 0.85
        is_match = similarity >= limit
        return bool(is_match), similarity

    @classmethod
    def match_face_in_database(cls, query_embedding, db_embeddings, threshold=None):
        """
        Finds the best matching face from a list of database embeddings using KNN voting.
        """
        if not db_embeddings:
            return None, 0.0
            
        matches = []
        for record in db_embeddings:
            emp_id = record['employee_id']
            db_emb = record['embedding']
            
            # Ensure we are comparing vectors of the same dimension
            if len(query_embedding) != len(db_emb):
                continue
                
            is_match, similarity = cls.compare_faces(query_embedding, db_emb, threshold)
            
            if is_match:
                matches.append({
                    'employee_id': emp_id,
                    'similarity': similarity
                })
                
        if not matches:
            return None, 0.0
            
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        
        K = min(3, len(matches))
        top_k = matches[:K]
        
        votes = {}
        for match in top_k:
            emp_id = match['employee_id']
            votes[emp_id] = votes.get(emp_id, 0) + 1
            
        best_emp_id = max(votes, key=votes.get)
        
        closest_match = top_k[0]
        if closest_match['employee_id'] == best_emp_id:
            return best_emp_id, closest_match['similarity']
            
        return None, 0.0

# Initialize immediately on module load
FaceEngine.initialize()
