import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk, ImageGrab
import cv2 as cv
from cv2.typing import MatLike
import numpy as np
import time

from detector.timer import Timer
from detector.app import App
from detector.video_capture import NO_VIDEO

VIDEO_FRAME_MARGIN = 10
AFTER_DELAY = 1

class GUI:
    def __init__(self, video_stream: App, frame_display_scaling_factor : float = 1.0) -> None:
        self._video_stream = video_stream

        # Initializing screen resolution (for window size)
        screen = ImageGrab.grab()
        screen_width, screen_height = screen.size
        screen_width = int(frame_display_scaling_factor * screen_width)
        screen_height = int(frame_display_scaling_factor * screen_height)
        self._video_stream.set_frame_area_dimensions(screen_width, screen_height)

        self._selected_video_source_id = None
        self._initialize_settings_gui()

        self._frame_counter = 0
        self._time_before_frame = None
        self._fps_label_value = 'FPS: 00.00'
        self._is_displaying = None
        

    def _initialize_settings_gui(self) -> None:
        self._root = tk.Tk()
        self._root.title('Object detector')
        self._root.resizable(False, False)

        # Set window size based on screen resolution (70% of screen size)
        screen = ImageGrab.grab()
        screen_width, screen_height = screen.size
        scaling_factor = 0.3

        window_width = int(screen_width * scaling_factor)
        window_height = int(screen_height * scaling_factor)
        self._root.geometry(f'{window_width}x{window_height}')
        self._root.geometry(f'+{0}+{0}')

        self._menubar = tk.Menu(master=self._root)
        self._root.config(menu=self._menubar)
        self._initialize_video_source_menu()
        self._initialize_detector_parameters_menu()


    def _initialize_video_source_menu(self) -> None:
        self._source_menu = tk.Menu(master=self._menubar, tearoff=0)
        self._selected_video_source_id = tk.IntVar()

        sources = self._video_stream.get_available_sources()
        for source_name in sources:
            self._source_menu.add_radiobutton(
                label=source_name,
                variable=self._selected_video_source_id,
                value=sources[source_name],
                command=lambda source_index=sources[source_name]: self._on_video_source_select(source_index)
            )

        self._selected_video_source_id.set(NO_VIDEO)
        self._menubar.add_cascade(menu=self._source_menu, label='Video source')


    def _on_video_source_select(self, source_id: int):
        is_source_on = self._video_stream.set_video_source(source_id)
        self._selected_video_source_id.set(source_id)

        if is_source_on:
            self._start_displaying()
        else:
            self._stop_displaying()


    def _start_displaying(self):
        self._is_displaying = True
        self._root.after(AFTER_DELAY, self._update_frame)


    def _stop_displaying(self):
        self._is_displaying = False
    

    def _initialize_detector_parameters_menu(self):
        # This part is now moved to the main window
        self._detector_frame = tk.Frame(self._root)
        self._detector_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        # Add confidence threshold slider
        confidence_threshold_label = tk.Label(self._detector_frame, text='Confidence threshold:')
        confidence_threshold_label.pack(pady=1)

        confidence_threshold_slider = tk.Scale(
            self._detector_frame,
            from_=0.00,
            to=1.00,
            resolution=0.01,
            orient='horizontal',
            command=self._update_confidence_threshold
        )
        confidence_threshold_slider.set(self._video_stream.get_confidence_threshold())
        confidence_threshold_slider.pack(pady=10)

        # Add object class selection
        classes_label = tk.Label(self._detector_frame, text='Classes of objects:')
        classes_label.pack(pady=1)

        checkbox_canvas = tk.Canvas(self._detector_frame)
        checkbox_canvas.pack(side='left', fill='both', expand=True)

        scrollbar = tk.Scrollbar(self._detector_frame, orient='vertical', command=checkbox_canvas.yview)
        scrollbar.pack(side='right', fill='y')

        checkbox_canvas.configure(yscrollcommand=scrollbar.set)

        checkbox_frame = tk.Frame(checkbox_canvas)
        checkbox_canvas.create_window((0, 0), window=checkbox_frame, anchor='nw')

        checkbox_vars = []
        row = 0
        col = 0
        max_items_per_row = 4
        all_classes = self._video_stream.get_available_classes()
        detected_classes = self._video_stream.get_detected_classes()

        for index, class_name in enumerate(all_classes):
            var = tk.BooleanVar(value=(index in detected_classes))
            checkbox = tk.Checkbutton(
                checkbox_frame,
                text=class_name,
                variable=var,
                command=lambda idx=index, v=var: self._update_classes(idx, v)
            )

            # Place the checkbox in the grid
            checkbox.grid(row=row, column=col, sticky='w', padx=5, pady=2)

            checkbox_vars.append(var)

            col += 1
            if col == max_items_per_row:
                col = 0
                row += 1

        checkbox_frame.update_idletasks()
        checkbox_canvas.config(scrollregion=checkbox_canvas.bbox('all'))

        # Bind the scroll events
        checkbox_canvas.bind_all('<MouseWheel>', self._on_mouse_scroll)  # For Windows/macOS
        checkbox_canvas.bind_all('<Button-4>', self._on_mouse_scroll)    # For Linux scroll up
        checkbox_canvas.bind_all('<Button-5>', self._on_mouse_scroll)    # For Linux scroll down

        # Save checkbox_canvas reference
        self._checkbox_canvas = checkbox_canvas

    
    def _on_mouse_scroll(self, event):
        if event.num == 4 or event.delta > 0:
            self._checkbox_canvas.yview_scroll(-1, 'units')
        elif event.num == 5 or event.delta < 0:
            self._checkbox_canvas.yview_scroll(1, 'units')
        

    def _update_confidence_threshold(self, value):
        self._video_stream.set_confidence_threshold(float(value))


    def _update_classes(self, class_index, var):
        if var.get():
            self._video_stream.add_detected_class(class_index)
        else:
            self._video_stream.remove_detected_class(class_index)


    def select_video_file(self) -> str:
        filetypes = [
            ('Video files', '.mp4 *.avi *.mkv *.mov *.wmv')
        ]
        file_path = filedialog.askopenfilename(title='Select a recorded video', filetypes=filetypes)

        return file_path


    def show(self) -> None:
        self.MAX_FRAME = 5001
        self.CURRENT_FRAME = 0
        self.START_TOTAL_TIME = None
        self.END_TIME = None
        self.TOTAL_TIME_FILE = open('overall_time.txt', 'w')

        self.START_SINGLE_FRAME_TIME = None
        self.SINGLE_FRAME_TIMES_FILE = open('durations.txt', 'w')
        self.SINGLE_FRAME_TIMES_FILE.write('Time [s]\n')

        self._root.mainloop()


    def _show_frame(self, frame: MatLike) -> None:
        frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
        cv.putText(frame, self._fps_label_value, (30, 30), cv.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv.LINE_AA)
        cv.imshow('Display', frame)


    def _update_frame(self) -> None:
        if not self._is_displaying:
            cv.destroyAllWindows()
            return
        
        # 1) Pobór klatki obrazu z bufora
        is_capture_on, frame = self._video_stream.get_latest_frame()

        # 2) Kod do wykonania kiedy kamera jest wlaczona:
        if is_capture_on:
            if self._time_before_frame is None:
                self._time_before_frame = Timer.get_current_time()

            # 3) Kod do wykonania gdy bufor nie byl pusty (None):
            if frame is not None:
                self._show_frame(frame)
                self._frame_counter += 1

                # 4) Poczatek pomiaru: po pobraniu klatki 0 - nie wchodzacej do pomiarow
                if self.CURRENT_FRAME == 0:
                    self.START_SINGLE_FRAME_TIME = Timer.get_current_time()
                    self.START_TOTAL_TIME = self.START_SINGLE_FRAME_TIME

                if self.CURRENT_FRAME > 0 and self.CURRENT_FRAME <= self.MAX_FRAME:
                    INTERVAL_END = Timer.get_current_time()
                    periodic_duration = INTERVAL_END - self.START_SINGLE_FRAME_TIME
                    self.START_SINGLE_FRAME_TIME = INTERVAL_END
                    self.SINGLE_FRAME_TIMES_FILE.write(f'{periodic_duration}\n')

                if self.CURRENT_FRAME == self.MAX_FRAME:
                    self.END_TIME = Timer.get_current_time()
                    duration = self.END_TIME - self.START_TOTAL_TIME
                    periodic_duration = self.END_TIME - self.START_SINGLE_FRAME_TIME
                    self.TOTAL_TIME_FILE.write(f'{duration}')
                    self.TOTAL_TIME_FILE.close()
                    self.SINGLE_FRAME_TIMES_FILE.write(f'{periodic_duration}')
                    self.SINGLE_FRAME_TIMES_FILE.close()

                self.CURRENT_FRAME += 1
        else:
            self._time_before_frame = None
            self._video_stream.set_video_source(NO_VIDEO)
            self._selected_video_source_id.set(NO_VIDEO)
            self._stop_displaying()

        self._update_fps_label(is_capture_on)
        self._root.after(AFTER_DELAY, self._update_frame)
    

    def _update_fps_label(self, is_capture_on) -> None:
        if self._time_before_frame is None:
            return

        time_after_frame = Timer.get_current_time()
        duration = time_after_frame - self._time_before_frame

        if duration >= 1:
            real_fps = self._frame_counter / duration if duration != 0 else 'inf'
            self._fps_label_value = f'FPS: {real_fps:.2f}'
            
            self._time_before_frame = time_after_frame
            self._frame_counter = 0

        if not is_capture_on:
            self._fps_label_value = f'FPS: 00.00'
