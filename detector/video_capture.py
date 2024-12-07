import cv2 as cv
from cv2.typing import MatLike
from typing import Tuple, Optional

NO_VIDEO = -2
VIDEO_FILE = -1
# camera: >= 0

class VideoCapture:
    def __init__(self) -> None:
        self._video_capture = None


    def start_capture(self, source: int|str) -> None:
        self.end_capture()
        self._video_capture = cv.VideoCapture(source)

        self._video_capture.set(cv.CAP_PROP_FRAME_WIDTH, 1280)
        self._video_capture.set(cv.CAP_PROP_FRAME_HEIGHT, 720)


    def end_capture(self) -> None:
        if self._video_capture is None:
            return
        self._video_capture.release()
        self._video_capture = None
    

    def get_frame(self) -> Tuple[bool, Optional[MatLike]]:
        if self._video_capture is None:
            return False, None
        is_capture_on, frame = self._video_capture.read()
        
        if is_capture_on:
            frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
        else:
            self.end_capture()

        return is_capture_on, frame


    @staticmethod
    def get_available_sources() -> dict[str, int]:
        sources = {
            'No video': NO_VIDEO,
            'Video file': VIDEO_FILE
        }

        i = 0
        while True:
            cap = cv.VideoCapture(i)
            if cap.isOpened():
                sources[f'Camera {i}'] = i
                cap.release()
            else:
                break
            i += 1
            
        return sources