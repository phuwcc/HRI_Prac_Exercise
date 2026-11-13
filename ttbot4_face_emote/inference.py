"""Fast MediaPipe face localization, then DeepFace on one aligned face crop."""
import math

import cv2


class FaceAnalyzer:
    def __init__(self, detection_width=320, min_face_size=24, detector_confidence=0.5):
        import mediapipe as mp
        from deepface import DeepFace
        self.deepface = DeepFace
        DeepFace.build_model('Emotion', task='facial_attribute')
        self.detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=detector_confidence)
        self.detection_width = detection_width
        self.min_face_size = min_face_size

    def analyze(self, frame):
        height, width = frame.shape[:2]
        scale = min(1.0, self.detection_width / width)
        small = cv2.resize(frame, (round(width * scale), round(height * scale)))
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        detections = self.detector.process(rgb).detections or []
        if len(detections) != 1:
            return []
        location = detections[0].location_data
        box = location.relative_bounding_box
        if min(box.width * small.shape[1], box.height * small.shape[0]) < self.min_face_size:
            return []
        x, y = max(0, round(box.xmin * width)), max(0, round(box.ymin * height))
        right = min(width, round((box.xmin + box.width) * width))
        bottom = min(height, round((box.ymin + box.height) * height))
        w, h = right-x, bottom-y
        if w < 10 or h < 10:
            return []
        crop = frame[y:bottom, x:right]
        # Eye keypoints already come from MediaPipe; avoid an extra eye cascade.
        eyes = sorted(location.relative_keypoints[:2], key=lambda point: point.x)
        if len(eyes) == 2:
            angle = math.degrees(math.atan2((eyes[1].y-eyes[0].y)*height,
                                           (eyes[1].x-eyes[0].x)*width))
            if 3 < abs(angle) < 30:
                center = ((eyes[0].x+eyes[1].x)*width/2-x,
                          (eyes[0].y+eyes[1].y)*height/2-y)
                matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
                crop = cv2.warpAffine(crop, matrix, (w, h), borderMode=cv2.BORDER_REPLICATE)
        crop = cv2.resize(crop, (224, 224), interpolation=cv2.INTER_AREA)
        # 'skip' applies only to this verified face crop, never the whole frame.
        results = self.deepface.analyze(
            img_path=crop, actions=['emotion'], detector_backend='skip',
            enforce_detection=True, align=False, silent=True)
        result = results[0] if isinstance(results, list) else results
        result['region'] = {'x': x, 'y': y, 'w': w, 'h': h}
        return [result]

    def close(self):
        self.detector.close()
