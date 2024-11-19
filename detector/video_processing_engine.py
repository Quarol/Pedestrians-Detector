import threading
from collections import deque
from cv2.typing import MatLike
import time
from typing import Tuple, Optional

from detector.timer import Timer
from detector.image_processor import ImageProcessor
from detector.video_capture import VideoCapture

CAPTURED_FRAMES_QUEUE_SIZE = 1  # Define a limit for frame queue size

class VideoProcessingEngine:
    def __init__(self, video_capture: VideoCapture, image_processor: ImageProcessor, notification_function) -> None:
        self._video_capture = video_capture
        self._image_processor = image_processor
        self._notification_function = notification_function

        self._latest_frame = None
        self._ret = False

        self._camera_seconds_per_frame = None

        self._max_frame_width = 1920
        self._max_frame_height = 1080
        self._min_frame_width = self._max_frame_width * 0.5
        self._min_frame_height = self._max_frame_height * 0.5

        self._frame_queue = deque(maxlen=CAPTURED_FRAMES_QUEUE_SIZE)

        self._lock = threading.Lock()
        self._queue_not_empty = threading.Condition(self._lock)
        self._queue_not_full = threading.Condition(self._lock)
        self._capture_event = threading.Event()
        self._process_event = threading.Event()

        self._continue_process_loop = True
        self._continue_capture_loop = True

        self._processing_thread = threading.Thread(target=self._process_frames)
        self._capture_thread = threading.Thread(target=self._capture_frames)

        self._capture_event.clear()
        self._process_event.clear()
        self._processing_thread.start()
        self._capture_thread.start()


    def set_window_dimensions(self, max_width, max_height, min_width, min_height) -> None:
        self._max_frame_width = max_width
        self._max_frame_height = max_height

        self._min_frame_width = min_width
        self._min_frame_height = min_height

    
    def shutdown(self):
        self._continue_process_loop = False
        self._continue_capture_loop = False

        self._capture_event.set()
        self._process_event.set()
        
        with self._lock:
            self._queue_not_full.notify_all()
            self._queue_not_empty.notify_all()

        self._capture_thread.join()
        print('Capture thread shot down')

        with self._lock:
            self._queue_not_full.notify_all()
            self._queue_not_empty.notify_all()

        self._processing_thread.join()
        print('Process thread shot down')

        print("Shutdown completed")

    
    def start_processing(self) -> None:
        self.stop_processing()
        self._process_event.set()


    def stop_processing(self) -> None:
        self._process_event.clear()


    def remove_video_source(self) -> None:
        self.stop_processing()
        self._end_capture()
        self._video_capture.end_capture()
        self._ret = False


    def set_video_source(self, source: int|str) -> None:
        self.stop_processing()
        self._end_capture()
        self._video_capture.end_capture()

        self._video_capture.start_capture(source)
        capture_fps = self._video_capture.get_fps()

        if capture_fps is None:
            self._video_capture.end_capture()
            return
        
        self._camera_seconds_per_frame = 1 / capture_fps
        self._ret = True

        self._start_capture()
        self.start_processing()


    def _start_capture(self):
        self._capture_event.set()


    def _end_capture(self):
        self._capture_event.clear()

        with self._lock:
            self._frame_queue.clear()
            self._queue_not_empty.notify_all()
            self._queue_not_full.notify_all()


    def _capture_frames(self) -> None:
        self._ret = True

        while self._continue_capture_loop:
            if not self._capture_event.is_set():
                self._capture_event.wait()
                # In case shutdown happened: end thread
                if not self._continue_capture_loop:
                    return

            capture_time_begin = Timer.get_current_time()
            is_capture_on, frame = self._video_capture.get_frame()

            if not is_capture_on:
                self.remove_video_source()
                continue

            if frame is None:
                continue

            frame = self._image_processor.fit_frame_into_screen(frame, 
                                                                self._max_frame_width, self._max_frame_height,
                                                                self._min_frame_width, self._min_frame_height)
            
            with self._queue_not_full:
                while len(self._frame_queue) == CAPTURED_FRAMES_QUEUE_SIZE:
                    self._queue_not_full.wait()
                    # In case shutdown happened: end thread
                    if not self._continue_capture_loop:
                        return

                self._frame_queue.append(frame)
                self._queue_not_empty.notify()

            capture_time_end = Timer.get_current_time()
            capture_duration = capture_time_end - capture_time_begin
            sleep_time = self._camera_seconds_per_frame - capture_duration
            
            if sleep_time > 0:
                time.sleep(sleep_time)
        

    def _process_frames(self) -> None:
        while self._continue_process_loop:
            if not self._process_event.is_set():
                self._process_event.wait()
                # In case shutdown happened: end thread
                if not self._continue_process_loop:
                    return

            with self._queue_not_empty:
                while not self._frame_queue:
                    self._queue_not_empty.wait()
                    # In case shutdown happened: end thread
                    if not self._continue_process_loop:  
                        return

                frame = self._frame_queue.popleft()
                self._queue_not_full.notify()

            detections = self._image_processor.detect_objects(frame)
            frame, are_there_objects = self._image_processor.visualize_objects_presence(frame, detections)

            with self._lock:
                self._latest_frame = frame

            if are_there_objects:
                self._notification_function()
       

    def get_latest_frame(self) -> Tuple[Optional[bool], Optional[MatLike]]:
        with self._lock:
            frame = self._latest_frame
            self._latest_frame = None

        return self._ret, frame