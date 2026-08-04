from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QPushButton, QLabel, QLineEdit, QGroupBox, QMessageBox, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal

from key_utils import default_key_for_lane, qt_key_to_string


DARK_DIALOG_STYLE = """
    QDialog { background-color: #1e1e1e; }
    QGroupBox { color: #ffffff; border: 1px solid #444; border-radius: 5px;
                margin-top: 10px; padding-top: 10px; font-weight: bold; }
    QGroupBox::title { color: #ffffff; }
    QLabel { color: #e0e0e0; }
    QLineEdit { background-color: #2d2d2d; color: #ffffff; border: 1px solid #555;
                border-radius: 3px; padding: 5px; }
    QLineEdit:focus { border: 1px solid #2196F3; }
    QPushButton { background-color: #2d2d2d; color: #ffffff; border: 1px solid #555;
                  border-radius: 3px; padding: 8px; }
    QPushButton:hover { background-color: #3d3d3d; }
    QPushButton:pressed { background-color: #1d1d1d; }
"""


class KeybindDialog(QDialog):
    keybindsUpdated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Custom Keybinds")
        self.setMinimumSize(500, 400)
        self.setModal(True)

        self.column_count = parent.columns_input.value()
        self.key_entries = []
        self._waiting_for_key = False
        self._target_lane = 0
        self._saving = False

        self.setStyleSheet(DARK_DIALOG_STYLE)
        self.init_ui()
        self.load_current_keybinds()

    def init_ui(self):
        layout = QVBoxLayout()

        instructions = QLabel(
            "Click a key field, then press a key to bind it to that lane.\n"
            "Press Save to apply changes."
        )
        instructions.setStyleSheet("color: #aaa; padding: 10px;")
        layout.addWidget(instructions)

        grid_group = QGroupBox(f"Keybindings for {self.column_count} lanes")
        grid_layout = QGridLayout()

        grid_layout.addWidget(QLabel("Lane"), 0, 0)
        grid_layout.addWidget(QLabel("Key"), 0, 1)
        grid_layout.addWidget(QLabel("Action"), 0, 2)

        for i in range(self.column_count):
            lane_label = QLabel(f"Lane {i + 1}")
            lane_label.setStyleSheet("font-weight: bold; color: #e0e0e0;")
            grid_layout.addWidget(lane_label, i + 1, 0)

            key_input = QLineEdit()
            key_input.setReadOnly(True)
            key_input.setPlaceholderText("Click to set key")
            key_input.setMaximumWidth(100)
            key_input.mousePressEvent = lambda e, idx=i: self.set_key_for_lane(idx)
            grid_layout.addWidget(key_input, i + 1, 1)

            clear_btn = QPushButton("Clear")
            clear_btn.clicked.connect(lambda checked, idx=i: self.clear_key_for_lane(idx))
            grid_layout.addWidget(clear_btn, i + 1, 2)

            self.key_entries.append({'lane': i, 'input': key_input, 'current_key': None})

        grid_group.setLayout(grid_layout)
        layout.addWidget(grid_group)

        btn_layout = QHBoxLayout()
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self.reset_to_defaults)
        btn_layout.addWidget(reset_btn)
        btn_layout.addStretch()

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; border-radius: 3px;"
        )
        save_btn.clicked.connect(self.save_keybinds)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def load_current_keybinds(self):
        config = self.parent.config
        for entry in self.key_entries:
            lane = entry['lane']
            key = config.get_key_for_lane(lane) or default_key_for_lane(lane)
            entry['input'].setText(key)
            entry['current_key'] = key

    def set_key_for_lane(self, lane_idx):
        self.setWindowTitle(f"Press a key for Lane {lane_idx + 1}...")
        self._waiting_for_key = True
        self._target_lane = lane_idx
        self.installEventFilter(self)

    def clear_key_for_lane(self, lane_idx):
        if lane_idx < len(self.key_entries):
            self.key_entries[lane_idx]['input'].setText("")
            self.key_entries[lane_idx]['current_key'] = None

    def reset_to_defaults(self):
        for entry in self.key_entries:
            lane = entry['lane']
            key = default_key_for_lane(lane)
            entry['input'].setText(key)
            entry['current_key'] = key

    def eventFilter(self, obj, event):
        if event.type() == event.Type.KeyPress and self._waiting_for_key:
            key_str = qt_key_to_string(event.key())
            if key_str:
                used_by = self.is_key_used(key_str, self._target_lane)
                if used_by is not None:
                    reply = QMessageBox.question(
                        self,
                        "Key Already Used",
                        f"Key '{key_str}' is assigned to Lane {used_by + 1}.\n"
                        "Reassign it to this lane?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )
                    if reply == QMessageBox.StandardButton.No:
                        self._stop_waiting()
                        return True
                    for entry in self.key_entries:
                        if entry['lane'] != self._target_lane and entry['current_key'] == key_str:
                            entry['input'].setText("")
                            entry['current_key'] = None

                self.key_entries[self._target_lane]['input'].setText(key_str)
                self.key_entries[self._target_lane]['current_key'] = key_str
                self._stop_waiting()
                return True
        return super().eventFilter(obj, event)

    def _stop_waiting(self):
        self.setWindowTitle("Custom Keybinds")
        self._waiting_for_key = False
        self.removeEventFilter(self)

    def is_key_used(self, key_str, exclude_lane):
        for entry in self.key_entries:
            if entry['lane'] != exclude_lane and entry['current_key'] == key_str:
                return entry['lane']
        return None

    def save_keybinds(self):
        if self._saving:
            return
        self._saving = True
        
        try:
            if self.parent.is_recording:
                self.parent.stop_recording()
                QApplication.processEvents()
            
            self.parent.input_handler._finalize_active_holds()
            
            for entry in self.key_entries:
                lane = entry['lane']
                key = entry['current_key']
                if key:
                    self.parent.config.set_keybind(lane, key)
                else:
                    self.parent.config.clear_keybind(lane)
            
            self.parent.input_handler.reload_keybinds()
            
            self.parent.update_keybind_legend()
            self.keybindsUpdated.emit()
            
            QMessageBox.information(self, "Success", "Keybinds saved successfully!")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save keybinds:\n{e}")
            
        finally:
            self._saving = False
