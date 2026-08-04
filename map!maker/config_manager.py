import json
import os


class ConfigError(Exception):
    pass


class ConfigManager:
    CONFIG_FILE = "beatmap_creator_config.json"

    DEFAULT_CONFIG = {
        "last_audio_dir": "",
        "last_export_dir": "",
        "bpm": 120,
        "columns": 4,
        "grid": "1/4",
        "snap_enabled": False,
        "offset": -20,
        "countdown_delay": 3,
        "hold_threshold": 40,
        "window_geometry": None,
        "window_state": None,
        "keybinds": {},
    }

    def __init__(self):
        self.config = self.DEFAULT_CONFIG.copy()
        self._config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.CONFIG_FILE)
        self.load()

    def load(self):
        if not os.path.exists(self._config_path):
            return
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            for key in self.DEFAULT_CONFIG:
                if key in loaded:
                    self.config[key] = loaded[key]
        except (json.JSONDecodeError, OSError) as exc:
            raise ConfigError(f"Failed to load config: {exc}") from exc

    def save(self):
        try:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        except OSError as exc:
            raise ConfigError(f"Failed to save config: {exc}) from exc")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        try:
            self.save()
        except ConfigError:
            pass

    def get_keybinds(self):
        return self.config.get("keybinds", {})

    def set_keybind(self, lane, key):
        if "keybinds" not in self.config:
            self.config["keybinds"] = {}
        self.config["keybinds"][f"lane_{lane}"] = key.upper()
        self.save()

    def get_key_for_lane(self, lane):
        return self.get_keybinds().get(f"lane_{lane}")

    def clear_keybind(self, lane):
        keybinds = self.get_keybinds()
        if f"lane_{lane}" in keybinds:
            del keybinds[f"lane_{lane}"]
            self.save()

    def clear_all_keybinds(self):
        self.config["keybinds"] = {}
        self.save()

    def reset_to_defaults(self):
        self.config = self.DEFAULT_CONFIG.copy()
        self.save()
