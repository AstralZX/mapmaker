import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing imports...")
errors = []

from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)

modules = [
    "audio_player", "input_handler", "beatmap_exporter",
    "note_visualizer", "config_manager", "keybind_dialog",
    "key_utils", "main_window",
]
for mod in modules:
    try:
        __import__(mod)
        print(f"  OK  {mod}")
    except Exception as exc:
        print(f"  FAIL {mod}: {exc}")
        errors.append(str(exc))

print("\nTesting hold note export (type 128)...")
try:
    from beatmap_exporter import BeatmapExporter

    notes = [
        (1000, 0, None),
        (2000, 1, 3500),
        (4000, 2, 4001),
        (5000, 0, 8000),
    ]
    exporter = BeatmapExporter(
        audio_filename="test.mp3",
        title="Test", artist="Test", creator="Test", version="Test",
        column_count=4, bpm=120, notes=notes,
    )
    content = exporter.generate_osu_content()
    assert "Mode: 3" in content
    assert ",128," in content
    hold_lines = [l for l in content.split("\n") if ",128," in l]
    assert len(hold_lines) == 3, f"Expected 3 holds, got {len(hold_lines)}"
    for line in hold_lines:
        parts = line.split(",")
        end = int(parts[5].split(":")[0])
        start = int(parts[2])
        assert end > start, f"Hold end must exceed start: {line}"
    print("  OK  hold notes export as type 128 with valid end times")

    with tempfile.NamedTemporaryFile(suffix=".osu", delete=False, mode="w") as f:
        path = f.name
    try:
        exporter.save_osu(path)
        with open(path, encoding="utf-8") as f:
            saved = f.read()
        assert saved == content
        print("  OK  save_osu round-trip")
    finally:
        os.unlink(path)

except Exception as exc:
    print(f"  FAIL export test: {exc}")
    errors.append(str(exc))

print("\nTesting input handler signals...")
try:
    from input_handler import InputHandler
    assert hasattr(InputHandler, "longNoteRecorded")
    assert hasattr(InputHandler, "noteRecorded")
    print("  OK  input handler has required signals")
except Exception as exc:
    print(f"  FAIL input handler: {exc}")
    errors.append(str(exc))

print("\nTesting note visualizer performance index...")
try:
    from note_visualizer import NoteVisualizer
    import bisect
    viz = NoteVisualizer()
    big = [(i * 10, i % 4, None) for i in range(50000)]
    viz.set_notes(big)
    assert len(viz._start_times) == 50000
    lo, hi = viz._visible_range(100000, 130000)
    assert hi - lo < 50000
    print(f"  OK  visible range slices {hi - lo} of 50000 notes")
except Exception as exc:
    print(f"  FAIL visualizer: {exc}")
    errors.append(str(exc))

if errors:
    print(f"\n{len(errors)} test(s) failed.")
    sys.exit(1)
else:
    print("\nAll tests passed.")
