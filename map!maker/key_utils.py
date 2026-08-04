from PyQt6.QtCore import Qt

MIN_HOLD_DURATION_MS = 40

KEY_DEBOUNCE_MS = 10

QT_KEY_TO_STRING = {
    Qt.Key.Key_1: '1', Qt.Key.Key_2: '2', Qt.Key.Key_3: '3',
    Qt.Key.Key_4: '4', Qt.Key.Key_5: '5', Qt.Key.Key_6: '6',
    Qt.Key.Key_7: '7', Qt.Key.Key_8: '8', Qt.Key.Key_9: '9',
    Qt.Key.Key_0: '0',
    Qt.Key.Key_A: 'A', Qt.Key.Key_B: 'B', Qt.Key.Key_C: 'C',
    Qt.Key.Key_D: 'D', Qt.Key.Key_E: 'E', Qt.Key.Key_F: 'F',
    Qt.Key.Key_G: 'G', Qt.Key.Key_H: 'H', Qt.Key.Key_I: 'I',
    Qt.Key.Key_J: 'J', Qt.Key.Key_K: 'K', Qt.Key.Key_L: 'L',
    Qt.Key.Key_M: 'M', Qt.Key.Key_N: 'N', Qt.Key.Key_O: 'O',
    Qt.Key.Key_P: 'P', Qt.Key.Key_Q: 'Q', Qt.Key.Key_R: 'R',
    Qt.Key.Key_S: 'S', Qt.Key.Key_T: 'T', Qt.Key.Key_U: 'U',
    Qt.Key.Key_V: 'V', Qt.Key.Key_W: 'W', Qt.Key.Key_X: 'X',
    Qt.Key.Key_Y: 'Y', Qt.Key.Key_Z: 'Z',
}

STRING_TO_QT_KEY = {v: k for k, v in QT_KEY_TO_STRING.items()}

DEFAULT_LANE_KEYS = {
    0: '1', 1: '2', 2: '3', 3: '4',
    4: '5', 5: '6', 6: '7', 7: '8',
    8: '9', 9: '0',
    10: 'Q', 11: 'W', 12: 'E', 13: 'R',
}


def qt_key_to_string(key):
    return QT_KEY_TO_STRING.get(key)


def string_to_qt_key(key_str):
    if not key_str:
        return None
    return STRING_TO_QT_KEY.get(key_str.upper())


def default_key_for_lane(lane):
    return DEFAULT_LANE_KEYS.get(lane, '?')


def build_custom_keybind_map(config, column_count):
    keybinds = config.get_keybinds()
    mapping = {}
    for key, value in keybinds.items():
        if not key.startswith("lane_"):
            continue
        lane = int(key.split("_")[1])
        if lane >= column_count:
            continue
        qt_key = string_to_qt_key(value)
        if qt_key is not None:
            mapping[qt_key] = lane
    return mapping


def map_default_key_to_lane(key, column_count):
    number_map = {
        Qt.Key.Key_1: 1, Qt.Key.Key_2: 2, Qt.Key.Key_3: 3, Qt.Key.Key_4: 4,
        Qt.Key.Key_5: 5, Qt.Key.Key_6: 6, Qt.Key.Key_7: 7, Qt.Key.Key_8: 8,
        Qt.Key.Key_9: 9, Qt.Key.Key_0: 10,
    }
    letter_map = {
        Qt.Key.Key_A: 1, Qt.Key.Key_S: 2, Qt.Key.Key_D: 3, Qt.Key.Key_F: 4,
        Qt.Key.Key_J: 5, Qt.Key.Key_K: 6, Qt.Key.Key_L: 7,
        Qt.Key.Key_H: 8, Qt.Key.Key_G: 9, Qt.Key.Key_Q: 10,
        Qt.Key.Key_W: 11, Qt.Key.Key_E: 12, Qt.Key.Key_R: 13, Qt.Key.Key_T: 14,
    }

    lane = number_map.get(key, -1)
    if lane == -1 or lane > column_count:
        lane = letter_map.get(key, -1)

    if lane != -1 and lane <= column_count:
        return lane - 1
    return -1
