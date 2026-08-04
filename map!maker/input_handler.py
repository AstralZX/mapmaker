from PyQt6.QtCore import QObject, pyqtSignal, Qt

from key_utils import (
    KEY_DEBOUNCE_MS,
    MIN_HOLD_DURATION_MS,
    build_custom_keybind_map,
    map_default_key_to_lane,
    qt_key_to_string,
)


class InputHandler(QObject):

    noteRecorded = pyqtSignal(int, int)
    longNoteRecorded = pyqtSignal(int, int, int)
    keyPressed = pyqtSignal(int)
    keyReleased = pyqtSignal(int)

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.is_recording = False
        self._reloading = False

        self.active_holds = {}
        self.held_keys = {}
        self._last_event_time = {}

        self.custom_keybinds = {}
        self.load_custom_keybinds()

        parent.installEventFilter(self)

    def load_custom_keybinds(self):
        try:
            columns = self.parent.columns_input.value()
            self.custom_keybinds = build_custom_keybind_map(self.parent.config, columns)
        except (AttributeError, RuntimeError):
            self.custom_keybinds = {}

    def reload_keybinds(self):
        if self._reloading:
            return
        
        self._reloading = True
        
        try:
            if self.is_recording:
                self._reloading = False
                return
            
            self._finalize_active_holds()
            
            self.active_holds.clear()
            self.held_keys.clear()
            self._last_event_time.clear()
            
            self.custom_keybinds.clear()
            self.load_custom_keybinds()
            
        finally:
            self._reloading = False

    def set_recording(self, enabled):
        if self.is_recording and not enabled:
            self._finalize_active_holds()
        self.is_recording = enabled
        if not enabled:
            self.active_holds.clear()
            self.held_keys.clear()
            self._last_event_time.clear()

    def _get_current_time(self):
        try:
            return self.parent.audio_player.get_position()
        except (AttributeError, RuntimeError):
            return 0

    def _map_key_to_lane(self, key):
        if self._reloading:
            columns = self.parent.columns_input.value()
            return map_default_key_to_lane(key, columns)
            
        try:
            columns = self.parent.columns_input.value()
            
            if key in self.custom_keybinds:
                lane = self.custom_keybinds[key]
                return lane if lane < columns else -1
            
            return map_default_key_to_lane(key, columns)
            
        except (AttributeError, RuntimeError, KeyError):
            return -1

    def _is_debounced(self, key, current_time):
        last = self._last_event_time.get(key)
        if last is not None and current_time - last < KEY_DEBOUNCE_MS:
            return True
        self._last_event_time[key] = current_time
        return False

    def _handle_press(self, key):
        if self._reloading:
            return False
            
        lane = self._map_key_to_lane(key)
        if lane == -1:
            return False

        current_time = self._get_current_time()
        if self._is_debounced(key, current_time):
            return True

        if lane in self.active_holds:
            return True

        self.active_holds[lane] = current_time
        self.held_keys[key] = lane
        return True

    def _handle_release(self, key):
        if self._reloading:
            return False
            
        lane = self.held_keys.pop(key, None)
        if lane is None:
            lane = self._map_key_to_lane(key)
            if lane == -1 or lane not in self.active_holds:
                return False

        press_time = self.active_holds.pop(lane, None)
        if press_time is None:
            return False

        release_time = self._get_current_time()
        duration = release_time - press_time

        if duration >= MIN_HOLD_DURATION_MS:
            self.longNoteRecorded.emit(press_time, lane, release_time)
        else:
            self.noteRecorded.emit(press_time, lane)

        return True

    def _finalize_active_holds(self):
        if not self.active_holds:
            return

        current_time = self._get_current_time()
        lanes = list(self.active_holds.keys())
        for lane in lanes:
            press_time = self.active_holds.pop(lane, None)
            if press_time is None:
                continue
            duration = current_time - press_time
            if duration >= MIN_HOLD_DURATION_MS:
                self.longNoteRecorded.emit(press_time, lane, current_time)
            else:
                self.noteRecorded.emit(press_time, lane)

        self.held_keys.clear()

    def eventFilter(self, obj, event):
        if self._reloading:
            return False
            
        event_type = event.type()

        if event_type == event.Type.KeyPress:
            key = event.key()
            self.keyPressed.emit(key)

            if self.is_recording and not event.isAutoRepeat():
                if self._handle_press(key):
                    return True

        elif event_type == event.Type.KeyRelease:
            key = event.key()
            self.keyReleased.emit(key)

            if self.is_recording:
                if self._handle_release(key):
                    return True

        return super().eventFilter(obj, event)

    def get_key_name(self, key):
        return qt_key_to_string(key) or '?'
