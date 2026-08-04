import os

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QSpinBox,
    QComboBox, QCheckBox, QFileDialog, QGridLayout,
    QMessageBox, QGroupBox, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap

from audio_player import AudioPlayer
from input_handler import InputHandler
from beatmap_exporter import BeatmapExporter, BeatmapParser, BeatmapValidationError
from note_visualizer import NoteVisualizer
from config_manager import ConfigManager, ConfigError
from keybind_dialog import KeybindDialog
from key_utils import default_key_for_lane, MIN_HOLD_DURATION_MS


APP_STYLE = """
    QMainWindow { background-color: #1a1a1a; }
    QWidget { background-color: #1a1a1a; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
    QGroupBox {
        color: #ffffff; border: 1px solid #3a3a3a; border-radius: 6px;
        margin-top: 12px; padding-top: 14px; font-weight: bold; font-size: 12px;
    }
    QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #ccc; }
    QLabel { color: #e0e0e0; background-color: transparent; }
    QLineEdit, QSpinBox, QComboBox {
        background-color: #2a2a2a; color: #ffffff; border: 1px solid #444;
        border-radius: 4px; padding: 6px 8px; min-height: 20px;
    }
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid #2196F3; }
    QPushButton {
        background-color: #2a2a2a; color: #ffffff; border: 1px solid #444;
        border-radius: 4px; padding: 8px 14px; font-size: 12px;
    }
    QPushButton:hover { background-color: #383838; border-color: #666; }
    QPushButton:pressed { background-color: #1a1a1a; }
    QPushButton:disabled { color: #555; background-color: #222; border-color: #333; }
    QCheckBox { color: #e0e0e0; spacing: 8px; }
    QCheckBox::indicator { width: 18px; height: 18px; border-radius: 3px; }
    QCheckBox::indicator:unchecked { background-color: #2a2a2a; border: 1px solid #555; }
    QCheckBox::indicator:checked { background-color: #2196F3; border: 1px solid #2196F3; }
    QScrollArea { border: none; background-color: #1a1a1a; }
    QScrollBar:vertical { background-color: #222; width: 10px; border-radius: 5px; }
    QScrollBar::handle:vertical { background-color: #555; border-radius: 5px; min-height: 24px; }
    QScrollBar::handle:vertical:hover { background-color: #777; }
    QStatusBar { background-color: #141414; color: #888; font-size: 11px; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("osu!mania Beatmap Creator")
        self.setMinimumSize(1050, 920)
        self.setStyleSheet(APP_STYLE)

        try:
            self.config = ConfigManager()
        except ConfigError:
            self.config = ConfigManager.__new__(ConfigManager)
            self.config.config = ConfigManager.DEFAULT_CONFIG.copy()
            self.config._config_path = ConfigManager.CONFIG_FILE

        self.notes = []
        self.is_recording = False
        self.audio_file_path = None
        self.background_path = None
        self.undo_stack = []
        self.redo_stack = []
        self.snap_enabled = False

        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_remaining = 0

        self.init_ui()

        self.audio_player = AudioPlayer()
        self.audio_player.positionUpdated.connect(self.on_position_update)
        self.audio_player.playbackStateChanged.connect(self.on_playback_state_changed)
        self.audio_player.durationChanged.connect(self.on_duration_changed)
        self.audio_player.errorOccurred.connect(self.on_audio_error)

        self.input_handler = InputHandler(self)
        self.input_handler.noteRecorded.connect(self.record_note)
        self.input_handler.longNoteRecorded.connect(self.record_long_note)

        if self.config.get("window_geometry"):
            self.restoreGeometry(self.config.get("window_geometry"))

        self.bpm_input.setValue(self.config.get("bpm", 120))
        self.columns_input.setValue(self.config.get("columns", 4))
        self.grid_combo.setCurrentText(self.config.get("grid", "1/4"))
        self.snap_checkbox.setChecked(self.config.get("snap_enabled", False))
        self.offset_input.setValue(self.config.get("offset", -20))
        self.countdown_input.setValue(self.config.get("countdown_delay", 3))
        self.hold_threshold_input.setValue(self.config.get("hold_threshold", 40))

        self.toggle_snap(self.snap_checkbox.isChecked())
        self.update_keybind_legend()
        self._update_stats()

        self.statusBar().showMessage("Ready — load an audio file to begin.", 4000)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_body = QWidget()
        controls = QVBoxLayout(scroll_body)
        controls.setSpacing(12)
        controls.setContentsMargins(4, 4, 4, 4)

        stats_frame = QFrame()
        stats_frame.setStyleSheet(
            "QFrame { background-color: #222; border: 1px solid #3a3a3a; border-radius: 6px; padding: 4px; }"
        )
        stats_layout = QGridLayout(stats_frame)
        stats_layout.setSpacing(8)

        def stat_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #888; font-size: 11px;")
            return lbl

        def stat_value(text):
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #fff; font-size: 12px; font-weight: bold; font-family: Consolas, monospace;")
            return lbl

        self.stat_time = stat_value("0 ms")
        self.stat_bpm = stat_value("120")
        self.stat_columns = stat_value("4")
        self.stat_snap = stat_value("OFF")
        self.stat_recording = stat_value("Idle")
        self.stat_notes = stat_value("0")
        self.stat_holds = stat_value("0")
        self.stat_duration = stat_value("0:00")

        stats_layout.addWidget(stat_label("Time"), 0, 0)
        stats_layout.addWidget(self.stat_time, 0, 1)
        stats_layout.addWidget(stat_label("BPM"), 0, 2)
        stats_layout.addWidget(self.stat_bpm, 0, 3)
        stats_layout.addWidget(stat_label("Columns"), 0, 4)
        stats_layout.addWidget(self.stat_columns, 0, 5)
        stats_layout.addWidget(stat_label("Snap"), 0, 6)
        stats_layout.addWidget(self.stat_snap, 0, 7)

        stats_layout.addWidget(stat_label("Recording"), 1, 0)
        stats_layout.addWidget(self.stat_recording, 1, 1)
        stats_layout.addWidget(stat_label("Notes"), 1, 2)
        stats_layout.addWidget(self.stat_notes, 1, 3)
        stats_layout.addWidget(stat_label("Holds"), 1, 4)
        stats_layout.addWidget(self.stat_holds, 1, 5)
        stats_layout.addWidget(stat_label("Duration"), 1, 6)
        stats_layout.addWidget(self.stat_duration, 1, 7)

        controls.addWidget(stats_frame)

        file_group = QGroupBox("Audio File")
        file_row = QHBoxLayout()
        self.file_label = QLabel("No file loaded")
        self.file_label.setStyleSheet(
            "padding: 6px 10px; background-color: #2a2a2a; border-radius: 4px; color: #ccc;"
        )
        self.file_label.setMinimumWidth(280)
        file_row.addWidget(self.file_label, 1)
        self.file_btn = QPushButton("Select Audio")
        self.file_btn.setMinimumWidth(120)
        self.file_btn.clicked.connect(self.select_audio_file)
        file_row.addWidget(self.file_btn)
        file_group.setLayout(file_row)
        controls.addWidget(file_group)

        meta_group = QGroupBox("Beatmap Metadata")
        meta = QGridLayout()
        meta.setHorizontalSpacing(12)
        meta.setVerticalSpacing(8)

        for row, (label, attr, default) in enumerate([
            ("Title:", "title_input", "My Beatmap"),
            ("Artist:", "artist_input", "Unknown Artist"),
            ("Creator:", "creator_input", "YourName"),
            ("Version:", "version_input", "Normal"),
        ]):
            col = (row % 2) * 2
            r = row // 2
            meta.addWidget(QLabel(label), r, col)
            field = QLineEdit(default)
            setattr(self, attr, field)
            meta.addWidget(field, r, col + 1)

        meta_group.setLayout(meta)
        controls.addWidget(meta_group)

        bg_group = QGroupBox("Background Image")
        bg_layout = QVBoxLayout()
        bg_row = QHBoxLayout()
        self.bg_label = QLabel("No background selected")
        self.bg_label.setStyleSheet("padding: 6px; background-color: #2a2a2a; border-radius: 4px;")
        bg_row.addWidget(self.bg_label, 1)
        self.bg_btn = QPushButton("Select Background")
        self.bg_btn.clicked.connect(self.select_background_image)
        bg_row.addWidget(self.bg_btn)
        self.clear_bg_btn = QPushButton("Clear")
        self.clear_bg_btn.clicked.connect(self.clear_background)
        self.clear_bg_btn.setEnabled(False)
        bg_row.addWidget(self.clear_bg_btn)
        bg_layout.addLayout(bg_row)
        self.bg_preview = QLabel("Preview")
        self.bg_preview.setMinimumHeight(100)
        self.bg_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bg_preview.setStyleSheet(
            "background-color: #141414; border: 1px dashed #444; border-radius: 4px; color: #555;"
        )
        bg_layout.addWidget(self.bg_preview)
        bg_group.setLayout(bg_layout)
        controls.addWidget(bg_group)

        timing_group = QGroupBox("Timing && Snap")
        timing = QGridLayout()
        timing.addWidget(QLabel("BPM:"), 0, 0)
        self.bpm_input = QSpinBox()
        self.bpm_input.setRange(60, 300)
        self.bpm_input.setValue(120)
        self.bpm_input.valueChanged.connect(self.on_bpm_changed)
        timing.addWidget(self.bpm_input, 0, 1)
        timing.addWidget(QLabel("Columns:"), 0, 2)
        self.columns_input = QSpinBox()
        self.columns_input.setRange(4, 14)
        self.columns_input.setValue(4)
        self.columns_input.valueChanged.connect(self.on_columns_changed)
        timing.addWidget(self.columns_input, 0, 3)
        timing.addWidget(QLabel("Grid:"), 1, 0)
        self.grid_combo = QComboBox()
        self.grid_combo.addItems(["1/1", "1/2", "1/3", "1/4", "1/6", "1/8", "1/12", "1/16"])
        self.grid_combo.currentTextChanged.connect(lambda _: self._update_stats())
        timing.addWidget(self.grid_combo, 1, 1)
        self.snap_checkbox = QCheckBox("Enable Snap")
        self.snap_checkbox.stateChanged.connect(self.toggle_snap)
        timing.addWidget(self.snap_checkbox, 1, 2)
        self.snap_status = QLabel("SNAP OFF")
        self.snap_status.setStyleSheet("color: #f44336; font-weight: bold;")
        timing.addWidget(self.snap_status, 1, 3)
        timing_group.setLayout(timing)
        controls.addWidget(timing_group)

        playback_group = QGroupBox("Playback && Recording")
        playback_row = QHBoxLayout()

        offset_col = QVBoxLayout()
        offset_col.addWidget(QLabel("Latency Offset (ms):"))
        offset_inner = QHBoxLayout()
        self.offset_input = QSpinBox()
        self.offset_input.setRange(-200, 200)
        self.offset_input.setValue(-20)
        self.offset_input.setToolTip("Negative = notes earlier, Positive = later")
        offset_inner.addWidget(self.offset_input)
        offset_inner.addWidget(QLabel("(- earlier / + later)"))
        offset_col.addLayout(offset_inner)
        playback_row.addLayout(offset_col)

        hold_col = QVBoxLayout()
        hold_col.addWidget(QLabel("Hold Threshold (ms):"))
        hold_inner = QHBoxLayout()
        self.hold_threshold_input = QSpinBox()
        self.hold_threshold_input.setRange(10, 500)
        self.hold_threshold_input.setValue(40)
        self.hold_threshold_input.setToolTip("Minimum press duration to register as a hold note")
        self.hold_threshold_input.valueChanged.connect(self.on_hold_threshold_changed)
        hold_inner.addWidget(self.hold_threshold_input)
        hold_inner.addWidget(QLabel("(shorter = more holds)"))
        hold_col.addLayout(hold_inner)
        playback_row.addLayout(hold_col)

        playback_row.addStretch()

        btn_col = QVBoxLayout()
        btn_row = QHBoxLayout()
        self.play_btn = QPushButton("Play")
        self.play_btn.setMinimumSize(90, 38)
        self.play_btn.clicked.connect(self.toggle_playback)
        btn_row.addWidget(self.play_btn)
        self.record_btn = QPushButton("Record")
        self.record_btn.setMinimumSize(90, 38)
        self.record_btn.clicked.connect(self.toggle_recording)
        self.record_btn.setEnabled(False)
        self.record_btn.setStyleSheet(
            "background-color: #388E3C; color: white; font-weight: bold; border: none;"
        )
        btn_row.addWidget(self.record_btn)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setMinimumSize(70, 38)
        self.stop_btn.clicked.connect(self.stop_playback)
        btn_row.addWidget(self.stop_btn)
        btn_col.addLayout(btn_row)

        self.time_label = QLabel("0 ms")
        self.time_label.setStyleSheet("font-size: 13px; font-weight: bold; font-family: Consolas, monospace;")
        btn_col.addWidget(self.time_label)
        playback_row.addLayout(btn_col)
        playback_group.setLayout(playback_row)
        controls.addWidget(playback_group)

        countdown_group = QGroupBox("Countdown")
        countdown_row = QHBoxLayout()
        countdown_row.addWidget(QLabel("Delay (seconds):"))
        self.countdown_input = QSpinBox()
        self.countdown_input.setRange(0, 10)
        self.countdown_input.setValue(3)
        countdown_row.addWidget(self.countdown_input)
        self.countdown_status = QLabel("Ready")
        self.countdown_status.setStyleSheet("font-weight: bold; color: #4CAF50;")
        countdown_row.addWidget(self.countdown_status)
        countdown_row.addStretch()
        countdown_group.setLayout(countdown_row)
        controls.addWidget(countdown_group)

        actions = QHBoxLayout()
        self.clear_btn = QPushButton("Clear Notes")
        self.clear_btn.clicked.connect(self.clear_notes)
        actions.addWidget(self.clear_btn)
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.clicked.connect(self.undo_note)
        self.undo_btn.setEnabled(False)
        actions.addWidget(self.undo_btn)
        self.redo_btn = QPushButton("Redo")
        self.redo_btn.clicked.connect(self.redo_note)
        self.redo_btn.setEnabled(False)
        actions.addWidget(self.redo_btn)
        self.keybind_btn = QPushButton("Keybinds")
        self.keybind_btn.clicked.connect(self.open_keybind_dialog)
        actions.addWidget(self.keybind_btn)
        self.import_btn = QPushButton("Import .osu")
        self.import_btn.clicked.connect(self.import_beatmap)
        actions.addWidget(self.import_btn)
        self.export_btn = QPushButton("Export .osu")
        self.export_btn.setMinimumSize(110, 34)
        self.export_btn.clicked.connect(self.export_beatmap)
        self.export_btn.setEnabled(False)
        self.export_btn.setStyleSheet(
            "background-color: #1565C0; color: white; font-weight: bold; border: none;"
        )
        actions.addWidget(self.export_btn)
        actions.addStretch()
        controls.addLayout(actions)

        scroll.setWidget(scroll_body)
        root.addWidget(scroll, 1)

        viz_panel = QWidget()
        viz_layout = QVBoxLayout(viz_panel)
        viz_layout.setSpacing(6)
        viz_layout.setContentsMargins(0, 0, 0, 0)

        viz_header = QHBoxLayout()
        self.note_count_label = QLabel("Notes: 0  |  Holds: 0")
        self.note_count_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #2196F3;")
        viz_header.addWidget(self.note_count_label)
        viz_header.addStretch()
        self.recording_indicator = QLabel("RECORDING")
        self.recording_indicator.setStyleSheet("color: #f44336; font-weight: bold; font-size: 13px;")
        self.recording_indicator.hide()
        viz_header.addWidget(self.recording_indicator)
        viz_layout.addLayout(viz_header)

        self.visualizer = NoteVisualizer()
        self.visualizer.set_column_count(self.columns_input.value())
        viz_layout.addWidget(self.visualizer)

        legend = QFrame()
        legend.setStyleSheet("background-color: #222; border-radius: 4px; border: 1px solid #3a3a3a;")
        legend_row = QHBoxLayout(legend)
        legend_row.setContentsMargins(10, 6, 10, 6)
        legend_row.addWidget(QLabel("Keys:"))
        self.legend_text = QLabel("1 2 3 4")
        self.legend_text.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 14px; color: #4CAF50; font-weight: bold;"
        )
        legend_row.addWidget(self.legend_text)
        legend_row.addStretch()
        viz_layout.addWidget(legend)

        root.addWidget(viz_panel, 0)


    def _update_stats(self):
        columns = self.columns_input.value()
        note_count = len(self.notes)
        hold_count = sum(1 for _, _, end in self.notes if end is not None)

        self.stat_bpm.setText(str(self.bpm_input.value()))
        self.stat_columns.setText(str(columns))
        self.stat_snap.setText(self.grid_combo.currentText() if self.snap_enabled else "OFF")
        self.stat_recording.setText("Recording" if self.is_recording else "Idle")
        self.stat_recording.setStyleSheet(
            "color: #f44336; font-size: 12px; font-weight: bold; font-family: Consolas, monospace;"
            if self.is_recording else
            "color: #4CAF50; font-size: 12px; font-weight: bold; font-family: Consolas, monospace;"
        )
        self.stat_notes.setText(str(note_count))
        self.stat_holds.setText(str(hold_count))
        self.note_count_label.setText(f"Notes: {note_count}  |  Holds: {hold_count}")

        duration_ms = self.audio_player.get_duration() if hasattr(self, 'audio_player') else 0
        if duration_ms > 0:
            secs = duration_ms // 1000
            self.stat_duration.setText(f"{secs // 60}:{secs % 60:02d}")
        else:
            self.stat_duration.setText("0:00")

    def _process_note_time(self, raw_time_ms):
        adjusted = raw_time_ms + self.offset_input.value()
        if self.snap_enabled:
            beat_duration_ms = 60000 / self.bpm_input.value()
            division = int(self.grid_combo.currentText().split('/')[1])
            step = beat_duration_ms / division
            adjusted = round(adjusted / step) * step
        return max(0, int(adjusted))

    def _validate_lane(self, lane):
        columns = self.columns_input.value()
        if lane < 0 or lane >= columns:
            raise BeatmapValidationError(f"Lane {lane} out of range (0–{columns - 1})")

    def _add_note(self, start, lane, end=None):
        self._validate_lane(lane)
        note = (start, lane, end)
        self.notes.append(note)
        self.visualizer.add_note(start, lane, end)
        self._update_stats()

    def load_notes(self, notes):
        self.notes = list(notes)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.undo_btn.setEnabled(False)
        self.redo_btn.setEnabled(False)
        self.visualizer.set_notes(self.notes)
        self._update_stats()

    def _set_recording_ui_locked(self, locked):
        for btn in (self.file_btn, self.keybind_btn, self.import_btn,
                    self.export_btn, self.bg_btn, self.clear_bg_btn):
            btn.setEnabled(not locked)
        self.record_btn.setEnabled(not locked or self.is_recording)
        self.play_btn.setEnabled(not locked or self.is_recording)


    def open_keybind_dialog(self):
        KeybindDialog(self).exec()

    def update_keybind_legend(self):
        keybinds = self.config.get_keybinds()
        columns = self.columns_input.value()
        parts = []
        for i in range(columns):
            parts.append(keybinds.get(f"lane_{i}") or default_key_for_lane(i))
        self.legend_text.setText("  ".join(parts))


    def select_audio_file(self):
        start_dir = self.config.get("last_audio_dir", "")
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio File", start_dir,
            "Audio Files (*.mp3 *.wav *.ogg *.flac *.m4a *.aac *.opus);;All Files (*.*)",
        )
        if not file_path:
            return
        self.audio_file_path = file_path
        self.file_label.setText(os.path.basename(file_path))
        self.config.set("last_audio_dir", os.path.dirname(file_path))

        if self.audio_player.load_file(file_path):
            self.record_btn.setEnabled(True)
            self.export_btn.setEnabled(True)
            self.statusBar().showMessage(f"Loaded: {os.path.basename(file_path)}", 3000)
            self.clear_notes(confirm=False)
            self.visualizer.set_duration(self.audio_player.get_duration())
            self._update_stats()
        else:
            QMessageBox.warning(self, "Error", "Failed to load audio file.")

    def select_background_image(self):
        start_dir = self.config.get("last_audio_dir", "")
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Background Image", start_dir,
            "Image Files (*.jpg *.jpeg *.png *.gif *.bmp);;All Files (*.*)",
        )
        if not file_path:
            return
        self.background_path = file_path
        self.bg_label.setText(os.path.basename(file_path))
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                200, 100, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.bg_preview.setPixmap(scaled)
        else:
            self.bg_preview.setText("Could not load image")
        self.clear_bg_btn.setEnabled(True)

    def clear_background(self):
        self.background_path = None
        self.bg_label.setText("No background selected")
        self.bg_preview.clear()
        self.bg_preview.setText("Preview")
        self.clear_bg_btn.setEnabled(False)

    def import_beatmap(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Beatmap", "", "osu! Beatmap Files (*.osu)",
        )
        if not file_path:
            return
        try:
            metadata = BeatmapParser.load_metadata_to_ui(file_path, self)
            hold_count = sum(1 for _, _, e in metadata['notes'] if e is not None)
            msg = (
                f"Imported: {os.path.basename(file_path)}\n\n"
                f"Title: {metadata['title']}\n"
                f"Artist: {metadata['artist']}\n"
                f"Columns: {metadata['column_count']}\n"
                f"BPM: {metadata['bpm']}\n"
                f"Notes: {len(metadata['notes'])} ({hold_count} holds)"
            )
            QMessageBox.information(self, "Import Successful", msg)
            self.statusBar().showMessage(f"Imported: {os.path.basename(file_path)}", 3000)
        except BeatmapValidationError as exc:
            QMessageBox.critical(self, "Import Error", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Import Error", f"Failed to import beatmap:\n{exc}")


    def toggle_snap(self, state):
        if isinstance(state, int):
            self.snap_enabled = state == Qt.CheckState.Checked.value
        else:
            self.snap_enabled = bool(state)
        self.config.set("snap_enabled", self.snap_enabled)
        if self.snap_enabled:
            self.snap_status.setText("SNAP ON")
            self.snap_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.snap_status.setText("SNAP OFF")
            self.snap_status.setStyleSheet("color: #f44336; font-weight: bold;")
        self._update_stats()

    def on_bpm_changed(self, value):
        self.config.set("bpm", value)
        self._update_stats()

    def on_columns_changed(self, value):
        self.config.set("columns", value)
        self.visualizer.set_column_count(value)
        self.update_keybind_legend()
        self.input_handler.reload_keybinds()
        self._update_stats()

    def on_hold_threshold_changed(self, value):
        self.config.set("hold_threshold", value)
        global MIN_HOLD_DURATION_MS
        MIN_HOLD_DURATION_MS = value


    def toggle_playback(self):
        if self.audio_player.is_playing():
            self.audio_player.pause()
            self.play_btn.setText("Play")
        else:
            self.audio_player.play()
            self.play_btn.setText("Pause")

    def stop_playback(self):
        self.audio_player.stop()
        self.play_btn.setText("Play")
        self.audio_player.set_position(0)
        self.time_label.setText("0 ms")
        self.stat_time.setText("0 ms")

    def on_position_update(self, position_ms):
        self.time_label.setText(f"{position_ms} ms")
        self.stat_time.setText(f"{position_ms} ms")
        self.visualizer.set_current_time(position_ms)

    def on_duration_changed(self, duration_ms):
        self.visualizer.set_duration(duration_ms)
        self._update_stats()

    def on_playback_state_changed(self, is_playing):
        if not is_playing and self.is_recording:
            self.stop_recording()

    def on_audio_error(self, error_message):
        QMessageBox.critical(self, "Audio Error", error_message)


    def start_countdown(self):
        delay = self.countdown_input.value()
        self.config.set("countdown_delay", delay)
        if delay == 0:
            self.start_recording()
            return

        self.countdown_remaining = delay
        self.countdown_status.setText(str(self.countdown_remaining))
        self.countdown_status.setStyleSheet("font-weight: bold; color: #FFA500;")
        self._set_recording_ui_locked(True)
        self.record_btn.setEnabled(False)
        self.countdown_timer.start(1000)

    def update_countdown(self):
        self.countdown_remaining -= 1
        if self.countdown_remaining > 0:
            self.countdown_status.setText(str(self.countdown_remaining))
        else:
            self.countdown_status.setText("GO!")
            self.countdown_status.setStyleSheet("font-weight: bold; color: #00FF00;")
            self.countdown_timer.stop()
            QTimer.singleShot(200, self.start_recording)

    def start_recording(self):
        self.is_recording = True
        self.input_handler.set_recording(True)
        self.record_btn.setText("Stop")
        self.record_btn.setStyleSheet(
            "background-color: #c62828; color: white; font-weight: bold; border: none;"
        )
        self.recording_indicator.show()
        self.countdown_status.setText("RECORDING")
        self.countdown_status.setStyleSheet("font-weight: bold; color: #f44336;")
        self._set_recording_ui_locked(False)
        self.record_btn.setEnabled(True)
        self._update_stats()
        self.statusBar().showMessage("Recording — press keys to place notes.", 0)

        if not self.audio_player.is_playing():
            self.audio_player.play()
            self.play_btn.setText("Pause")

    def stop_recording(self):
        self.is_recording = False
        self.input_handler.set_recording(False)
        self.record_btn.setText("Record")
        self.record_btn.setStyleSheet(
            "background-color: #388E3C; color: white; font-weight: bold; border: none;"
        )
        self.recording_indicator.hide()
        self.countdown_status.setText("Ready")
        self.countdown_status.setStyleSheet("font-weight: bold; color: #4CAF50;")
        self._set_recording_ui_locked(False)
        self._update_stats()
        self.statusBar().showMessage(f"Recording stopped. {len(self.notes)} notes total.", 3000)

    def toggle_recording(self):
        if not self.audio_player.current_file:
            QMessageBox.warning(self, "No Audio", "Load an audio file first.")
            return
        if not self.is_recording:
            self.start_countdown()
        else:
            self.stop_recording()

    def record_note(self, raw_time_ms, lane):
        if not self.is_recording:
            return
        try:
            final_time = self._process_note_time(raw_time_ms)
            self._validate_lane(lane)
            note = (final_time, lane, None)
            self.undo_stack.append(('add', note))
            self.redo_stack.clear()
            self.undo_btn.setEnabled(True)
            self.redo_btn.setEnabled(False)
            self._add_note(final_time, lane)
            snap = "SNAP" if self.snap_enabled else "RAW"
            self.statusBar().showMessage(
                f"[{snap}] Tap — Lane {lane + 1} @ {final_time} ms", 400,
            )
        except BeatmapValidationError as exc:
            self.statusBar().showMessage(f"Note rejected: {exc}", 2000)

    def record_long_note(self, raw_start_ms, lane, raw_end_ms):
        if not self.is_recording:
            return
        try:
            final_start = self._process_note_time(raw_start_ms)
            final_end = self._process_note_time(raw_end_ms)
            self._validate_lane(lane)
            hold_threshold = self.hold_threshold_input.value()
            if final_end <= final_start:
                final_end = final_start + hold_threshold
            note = (final_start, lane, final_end)
            self.undo_stack.append(('add', note))
            self.redo_stack.clear()
            self.undo_btn.setEnabled(True)
            self.redo_btn.setEnabled(False)
            self._add_note(final_start, lane, final_end)
            snap = "SNAP" if self.snap_enabled else "RAW"
            self.statusBar().showMessage(
                f"[{snap}] Hold — Lane {lane + 1} @ {final_start}–{final_end} ms", 400,
            )
        except BeatmapValidationError as exc:
            self.statusBar().showMessage(f"Note rejected: {exc}", 2000)


    def undo_note(self):
        if not self.undo_stack:
            return
        action, note = self.undo_stack.pop()
        if action == 'add' and note in self.notes:
            self.notes.remove(note)
            self.redo_stack.append(('add', note))
            self.visualizer.set_notes(self.notes)
            self._update_stats()
            self.redo_btn.setEnabled(True)
            self.statusBar().showMessage(f"Undo — removed note @ {note[0]} ms", 1000)
        if not self.undo_stack:
            self.undo_btn.setEnabled(False)

    def redo_note(self):
        if not self.redo_stack:
            return
        action, note = self.redo_stack.pop()
        if action == 'add':
            self.notes.append(note)
            self.undo_stack.append(('add', note))
            self.visualizer.set_notes(sorted(self.notes, key=lambda n: (n[0], n[1])))
            self._update_stats()
            self.undo_btn.setEnabled(True)
            self.statusBar().showMessage(f"Redo — restored note @ {note[0]} ms", 1000)
        if not self.redo_stack:
            self.redo_btn.setEnabled(False)

    def clear_notes(self, confirm=True):
        if not self.notes:
            return
        if confirm and QMessageBox.question(
            self, "Clear Notes",
            f"Clear all {len(self.notes)} notes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.No:
            return
        self.notes = []
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.undo_btn.setEnabled(False)
        self.redo_btn.setEnabled(False)
        self.visualizer.clear_notes()
        self._update_stats()
        self.statusBar().showMessage("Notes cleared.", 1000)


    def export_beatmap(self):
        if not self.notes:
            QMessageBox.warning(self, "No Notes", "Record some notes first.")
            return
        if not self.audio_file_path:
            QMessageBox.warning(self, "No Audio", "Load an audio file first.")
            return

        try:
            BeatmapExporter.validate_notes(self.notes, self.columns_input.value())
        except BeatmapValidationError as exc:
            QMessageBox.critical(self, "Validation Error", str(exc))
            return

        base_name = (
            f"{self.title_input.text()} - {self.artist_input.text()} "
            f"({self.creator_input.text()}) [{self.version_input.text()}]"
        )
        safe_name = "".join(c for c in base_name if c.isalnum() or c in " -_()[]")
        start_dir = self.config.get("last_export_dir", "")

        format_msg = QMessageBox()
        format_msg.setWindowTitle("Export Format")
        format_msg.setText("Choose export format:")
        osu_btn = format_msg.addButton(".osu (single file)", QMessageBox.ButtonRole.AcceptRole)
        osz_btn = format_msg.addButton(".osz (archive)", QMessageBox.ButtonRole.AcceptRole)
        format_msg.setDefaultButton(osz_btn)
        format_msg.exec()

        is_osz = format_msg.clickedButton() != osu_btn
        ext = ".osz" if is_osz else ".osu"
        file_path, _ = QFileDialog.getSaveFileName(
            self, f"Save Beatmap{ext}", os.path.join(start_dir, f"{safe_name}{ext}"),
            f"osu! Files (*{ext})",
        )
        if not file_path:
            return

        try:
            self.config.set("last_export_dir", os.path.dirname(file_path))
            exporter = BeatmapExporter(
                audio_filename=self.audio_file_path,
                title=self.title_input.text(),
                artist=self.artist_input.text(),
                creator=self.creator_input.text(),
                version=self.version_input.text(),
                column_count=self.columns_input.value(),
                bpm=self.bpm_input.value(),
                notes=self.notes,
                offset=self.offset_input.value(),
                background_image=self.background_path,
            )
            if is_osz:
                exporter.save_osz(file_path)
            else:
                exporter.save_osu(file_path)

            stats = exporter.get_stats()
            msg = (
                f"Export successful!\n\n"
                f"Notes: {stats['notes']} ({stats['taps']} taps, {stats['holds']} holds)\n"
                f"Duration: {stats['duration']:.1f}s\n"
                f"NPS: {stats['nps']}\n"
                f"BPM: {stats['bpm']}\n"
                f"Columns: {stats['columns']}\n\n"
                f"{file_path}"
            )
            QMessageBox.information(self, "Export Successful", msg)
            self.statusBar().showMessage(f"Exported: {os.path.basename(file_path)}", 5000)
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{exc}")

    def closeEvent(self, event):
        self.config.set("window_geometry", self.saveGeometry())
        self.config.set("bpm", self.bpm_input.value())
        self.config.set("columns", self.columns_input.value())
        self.config.set("grid", self.grid_combo.currentText())
        self.config.set("offset", self.offset_input.value())
        self.config.set("countdown_delay", self.countdown_input.value())
        self.config.set("hold_threshold", self.hold_threshold_input.value())
        try:
            self.config.save()
        except ConfigError:
            pass
        event.accept()
