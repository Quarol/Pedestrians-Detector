import cv2 as cv
from cv2.typing import MatLike
from ultralytics import YOLO
import numpy as np

from detector.app import App
from detector.video_capture import VideoCapture
from detector.system_settings import yolo_config

WARM_UP_IMAGE = 'demo_assets/people.jpg'

class ImageProcessor:
    def __init__(self) -> None:
        self.set_detection_model('yolov8n-pretrained-default.pt')
    

    def set_detection_model(self, name: str):
        self._detector = YOLO(f'yolo_models/{name}')
        self.detect_objects(WARM_UP_IMAGE) # Warmp up to initialize


    def set_confidence_threshold(confidence_threshold):
        yolo_config.confidence_threshold = confidence_threshold


    def detect_objects(self, frame: MatLike):
        results = self._detector.predict(
            frame,
            conf=yolo_config.confidence_threshold,
            device=yolo_config.device,
            verbose=yolo_config.verbose
        ) # Returns list of output frames
        first_frame_result = results[0] # Get first (and only) frame

        return first_frame_result


    def visualize_people_presence(self, frame: MatLike, detections):
        boxes = detections.boxes
        areTherePeople = False

        for box in boxes:
            if self._is_object_person:
                areTherePeople = True
                x_min, y_min, x_max, y_max = box.xyxy[0]
                cv.rectangle(frame, (int(x_min), int(y_min)), (int(x_max), int(y_max)), (0, 255, 0), 2)

        return frame, areTherePeople
    

    def _is_object_person(self, box):
        object_class = int(box.cls[0])
        return object_class == 0


    def fit_frame_into_screen(self, frame: MatLike, max_frame_width, max_frame_height):
        if frame is None:
            return None
        
        output_width, output_height = self._fitting_dimensions(frame, max_frame_width, max_frame_height)
        frame = cv.resize(frame, (output_width, output_height), interpolation=cv.INTER_LINEAR)
        return frame


    def _fitting_dimensions(self, frame, max_width, max_height):
        height, width = frame.shape[:2]

        if width <= max_width and height <= max_height:
            return width, height
        
        scale_x = max_width / width
        scale_y = max_height / height

        scale = min(scale_x, scale_y)

        new_width = int(width * scale)
        new_height = int(height * scale)

        return new_width, new_height
        