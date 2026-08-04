import bisect

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont


class NoteVisualizer(QWidget):

    VIEW_WINDOW_MS = 30000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._notes = []
        self._start_times = []
        self.current_time = 0
        self.duration = 0
        self.column_count = 4
        self._needs_repaint = True

        self.setMinimumHeight(140)
        self.setStyleSheet("background-color: #252525; border: 1px solid #444; border-radius: 6px;")

        self.lane_colors = [
            QColor(255, 90, 90), QColor(90, 220, 90), QColor(90, 140, 255),
            QColor(255, 220, 70), QColor(220, 90, 220), QColor(70, 220, 220),
            QColor(255, 170, 70), QColor(170, 90, 255), QColor(90, 255, 170),
            QColor(255, 130, 130), QColor(130, 255, 130), QColor(130, 130, 255),
            QColor(255, 180, 180), QColor(180, 180, 255),
        ]

    def _rebuild_index(self):
        self._start_times = [n[0] for n in self._notes]

    def set_notes(self, notes):
        self._notes = sorted(notes, key=lambda n: (n[0], n[1]))
        self._rebuild_index()
        self._needs_repaint = True
        self.update()

    def set_current_time(self, time_ms):
        if time_ms != self.current_time:
            self.current_time = time_ms
            self._needs_repaint = True
            self.update()

    def set_duration(self, duration_ms):
        self.duration = duration_ms

    def set_column_count(self, count):
        if count != self.column_count:
            self.column_count = count
            self._needs_repaint = True
            self.update()

    def add_note(self, time_ms, lane, end_time_ms=None):
        note = (time_ms, lane, end_time_ms)
        idx = bisect.bisect_left(self._start_times, time_ms)
        self._notes.insert(idx, note)
        self._start_times.insert(idx, time_ms)
        self._needs_repaint = True
        self.update()

    def clear_notes(self):
        self._notes.clear()
        self._start_times.clear()
        self._needs_repaint = True
        self.update()

    def note_count(self):
        return len(self._notes)

    def hold_count(self):
        return sum(1 for _, _, end in self._notes if end is not None)

    def _visible_range(self, start_time, end_time):
        if not self._notes:
            return 0, 0
        lo = bisect.bisect_left(self._start_times, start_time - self.VIEW_WINDOW_MS)
        hi = bisect.bisect_right(self._start_times, end_time)
        return lo, hi

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        painter.fillRect(0, 0, width, height, QColor(37, 37, 37))

        half_window = self.VIEW_WINDOW_MS / 2
        view_start = max(0, self.current_time - half_window)
        view_end = view_start + self.VIEW_WINDOW_MS

        lane_width = width / max(1, self.column_count)
        note_width = lane_width * 0.72
        head_radius = min(note_width * 0.35, 10)

        painter.setPen(QPen(QColor(55, 55, 55), 1))
        for i in range(1, self.column_count):
            x = int(i * lane_width)
            painter.drawLine(x, 0, x, height)

        painter.setPen(QColor(80, 80, 80))
        painter.setFont(QFont("Consolas", 8))
        for i in range(self.column_count):
            cx = int(i * lane_width + lane_width / 2 - 4)
            painter.drawText(cx, height - 4, str(i + 1))

        if not self._notes or self.duration == 0:
            painter.setPen(QColor(100, 100, 100))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(width // 2 - 70, height // 2, "No notes to display")
            painter.end()
            return

        lo, hi = self._visible_range(view_start, view_end)

        def time_to_y(t):
            progress = (t - view_start) / self.VIEW_WINDOW_MS
            return (1 - progress) * height

        for time_ms, lane, end_time in self._notes[lo:hi]:
            span_end = end_time if end_time is not None else time_ms
            if span_end < view_start or time_ms > view_end:
                continue
            if lane < 0 or lane >= self.column_count:
                continue

            color = self.lane_colors[lane % len(self.lane_colors)]
            x = lane * lane_width + (lane_width - note_width) / 2
            y_head = time_to_y(time_ms)
            cx = int(x + note_width / 2)
            cy = int(y_head)

            if end_time is not None:
                y_tail = time_to_y(end_time)
                top = min(cy, int(y_tail))
                bar_h = max(abs(cy - int(y_tail)), 3)
                bar_w = note_width * 0.45
                bar_x = x + (note_width - bar_w) / 2

                body = QColor(color)
                body.setAlpha(140)
                painter.setBrush(QBrush(body))
                painter.setPen(QPen(color.darker(130), 1))
                painter.drawRoundedRect(int(bar_x), top, int(bar_w), bar_h, 3, 3)

                painter.setBrush(QBrush(color.lighter(110)))
                painter.setPen(QPen(color.darker(150), 1))
                painter.drawRect(int(bar_x), int(y_tail) - 2, int(bar_w), 4)

            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color.darker(140), 2))
            painter.drawEllipse(cx - int(head_radius), cy - int(head_radius),
                                int(head_radius * 2), int(head_radius * 2))

        play_y = int(time_to_y(self.current_time))
        painter.setPen(QPen(QColor(255, 255, 255, 180), 2))
        painter.drawLine(0, play_y, width, play_y)

        painter.setPen(QColor(120, 120, 120))
        painter.setFont(QFont("Consolas", 8))
        for i in range(0, 11):
            t = int(view_start + (i / 10) * self.VIEW_WINDOW_MS)
            x = int((i / 10) * width)
            painter.drawText(x - 18, height - 16, f"{t / 1000:.1f}s")

        painter.end()
