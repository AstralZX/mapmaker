import math
import os
import re
import zipfile
import tempfile
import shutil


class BeatmapValidationError(Exception):
    pass


class BeatmapExporter:
    HOLD_NOTE_TYPE = 128
    TAP_NOTE_TYPE = 1

    def __init__(self, audio_filename, title, artist, creator, version,
                 column_count, bpm, notes, offset=0, background_image=None):
        self.audio_filename = os.path.basename(audio_filename)
        self.audio_full_path = audio_filename
        self.title = title.strip() if title.strip() else "Untitled"
        self.artist = artist.strip() if artist.strip() else "Unknown Artist"
        self.creator = creator.strip() if creator.strip() else "Unknown"
        self.version = version.strip() if version.strip() else "Easy"
        self.column_count = column_count
        self.bpm = bpm
        self.notes = sorted(
            (self._normalize_note(n, column_count) for n in notes),
            key=lambda n: (n[0], n[1]),
        )
        self.offset = offset
        self.background_image = background_image
        self.background_filename = os.path.basename(background_image) if background_image else None

    @staticmethod
    def _normalize_note(note, column_count):
        if len(note) == 2:
            start, lane = note
            end = None
        else:
            start, lane, end = note

        start = int(start)
        lane = int(lane)
        end = int(end) if end is not None else None

        if lane < 0 or lane >= column_count:
            raise BeatmapValidationError(
                f"Invalid lane {lane} for {column_count} columns"
            )
        if start < 0:
            raise BeatmapValidationError(f"Negative start time: {start}")
        if end is not None:
            if end <= start:
                end = start + 1

        return (start, lane, end)

    @staticmethod
    def validate_notes(notes, column_count):
        normalized = []
        for note in notes:
            normalized.append(BeatmapExporter._normalize_note(note, column_count))
        return normalized

    def _lane_to_x(self, lane):
        return int(math.floor((lane * 512 + 256) / self.column_count))

    def generate_osu_content(self):
        lines = []

        lines.append("osu file format v14")
        lines.append("")

        lines.append("[General]")
        lines.append(f"AudioFilename: {self.audio_filename}")
        lines.append("AudioLeadIn: 0")
        lines.append("PreviewTime: -1")
        lines.append("Countdown: 0")
        lines.append("SampleSet: Soft")
        lines.append("StackLeniency: 0.7")
        lines.append("Mode: 3")
        lines.append("LetterboxInBreaks: 0")
        lines.append("SpecialStyle: 0")
        lines.append("WidescreenStoryboard: 1")
        lines.append("")

        lines.append("[Editor]")
        lines.append("DistanceSpacing: 1.2")
        lines.append("BeatDivisor: 4")
        lines.append("GridSize: 32")
        lines.append("TimelineZoom: 1")
        lines.append("")

        lines.append("[Metadata]")
        lines.append(f"Title:{self.title}")
        lines.append(f"TitleUnicode:{self.title}")
        lines.append(f"Artist:{self.artist}")
        lines.append(f"ArtistUnicode:{self.artist}")
        lines.append(f"Creator:{self.creator}")
        lines.append(f"Version:{self.version}")
        lines.append("Source:")
        lines.append("Tags:")
        lines.append("BeatmapID:0")
        lines.append("BeatmapSetID:-1")
        lines.append("")

        lines.append("[Difficulty]")
        lines.append("HPDrainRate:7")
        lines.append(f"CircleSize:{self.column_count}")
        lines.append("OverallDifficulty:7")
        lines.append("ApproachRate:5")
        lines.append("SliderMultiplier:1.4")
        lines.append("SliderTickRate:1")
        lines.append("")

        lines.append("[Events]")
        lines.append("//Background and Video events")
        if self.background_filename:
            lines.append(f'0,0,"{self.background_filename}",0,0')
        lines.append("//Break Periods")
        lines.append("//Storyboard Layer 0 (Background)")
        lines.append("//Storyboard Layer 1 (Fail)")
        lines.append("//Storyboard Layer 2 (Pass)")
        lines.append("//Storyboard Layer 3 (Foreground)")
        lines.append("//Storyboard Layer 4 (Overlay)")
        lines.append("//Storyboard Sound Samples")
        lines.append("")

        lines.append("[TimingPoints]")
        beat_length_ms = 60000 / self.bpm
        timing_offset = max(0, self.notes[0][0] - 1000) if self.notes else 0
        lines.append(f"{timing_offset:.0f},{beat_length_ms:.3f},4,1,0,100,1,0")
        lines.append("")

        lines.append("[HitObjects]")
        if not self.notes:
            lines.append("// No notes recorded")
        else:
            for start, lane, end in self.notes:
                x = self._lane_to_x(lane)
                y = 192
                hit_sound = 0
                if end is not None:
                    lines.append(
                        f"{x},{y},{int(start)},{self.HOLD_NOTE_TYPE},{hit_sound},"
                        f"{int(end)}:0:0:0:0:"
                    )
                else:
                    lines.append(
                        f"{x},{y},{int(start)},{self.TAP_NOTE_TYPE},{hit_sound},0:0:0:0:"
                    )

        return "\n".join(lines)

    @staticmethod
    def validate_osu_content(content, expected_holds=0):
        if not content.startswith("osu file format"):
            raise BeatmapValidationError("Missing osu file format header")
        if "Mode: 3" not in content:
            raise BeatmapValidationError("Not a mania beatmap (Mode: 3)")
        if "[HitObjects]" not in content:
            raise BeatmapValidationError("Missing [HitObjects] section")

        hold_lines = re.findall(r",128,\d+,(\d+):", content)
        if expected_holds and len(hold_lines) != expected_holds:
            raise BeatmapValidationError(
                f"Expected {expected_holds} hold notes, found {len(hold_lines)}"
            )
        for end_str in hold_lines:
            if not end_str.isdigit():
                raise BeatmapValidationError(f"Invalid hold end time: {end_str}")
        return True

    def save_osu(self, filepath):
        content = self.generate_osu_content()
        hold_count = sum(1 for _, _, e in self.notes if e is not None)
        self.validate_osu_content(content, expected_holds=hold_count)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except OSError as exc:
            raise OSError(f"Failed to save .osu file: {exc}") from exc

    def save_osz(self, filepath):
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                osu_content = self.generate_osu_content()
                hold_count = sum(1 for _, _, e in self.notes if e is not None)
                self.validate_osu_content(osu_content, expected_holds=hold_count)

                base_name = f"{self.title} - {self.artist} ({self.creator}) [{self.version}]"
                safe_base_name = "".join(c for c in base_name if c.isalnum() or c in " -_()[]")
                if not safe_base_name:
                    safe_base_name = "beatmap"
                osu_filename = f"{safe_base_name}.osu"
                osu_path = os.path.join(temp_dir, osu_filename)

                with open(osu_path, 'w', encoding='utf-8') as f:
                    f.write(osu_content)

                if not os.path.exists(self.audio_full_path):
                    raise FileNotFoundError(f"Audio file not found: {self.audio_full_path}")

                audio_filename = os.path.basename(self.audio_full_path)
                shutil.copy2(self.audio_full_path, os.path.join(temp_dir, audio_filename))

                bg_filename = None
                if self.background_image and os.path.exists(self.background_image):
                    bg_filename = os.path.basename(self.background_image)
                    shutil.copy2(
                        self.background_image,
                        os.path.join(temp_dir, bg_filename),
                    )

                with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(osu_path, os.path.basename(osu_path))
                    zipf.write(
                        os.path.join(temp_dir, audio_filename),
                        audio_filename,
                    )
                    if bg_filename:
                        zipf.write(
                            os.path.join(temp_dir, bg_filename),
                            bg_filename,
                        )
                return True
        except Exception as exc:
            raise RuntimeError(f"Failed to create .osz archive: {exc}") from exc

    def save(self, filepath):
        if filepath.lower().endswith('.osz'):
            return self.save_osz(filepath)
        return self.save_osu(filepath)

    def get_stats(self):
        note_count = len(self.notes)
        hold_count = sum(1 for _, _, end in self.notes if end is not None)
        tap_count = note_count - hold_count
        if note_count == 0:
            return {
                "notes": 0, "holds": 0, "taps": 0,
                "duration": 0, "nps": 0,
                "bpm": self.bpm, "columns": self.column_count,
                "has_background": bool(self.background_image),
            }

        first_note = self.notes[0][0]
        last_note = max(end if end is not None else start for start, _, end in self.notes)
        duration_sec = (last_note - first_note) / 1000
        nps = note_count / duration_sec if duration_sec > 0 else 0

        return {
            "notes": note_count,
            "holds": hold_count,
            "taps": tap_count,
            "duration": duration_sec,
            "nps": round(nps, 2),
            "bpm": self.bpm,
            "columns": self.column_count,
            "has_background": bool(self.background_image),
        }


class BeatmapParser:

    @staticmethod
    def parse_osu_file(filepath):
        metadata = {
            "title": "",
            "artist": "",
            "creator": "",
            "version": "",
            "audio_filename": "",
            "bpm": 120,
            "column_count": 4,
            "background": None,
            "notes": [],
        }

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except OSError as exc:
            raise BeatmapValidationError(f"Cannot read file: {exc}") from exc

        if not content.startswith("osu file format"):
            raise BeatmapValidationError("Not a valid .osu file")

        current_section = ""

        for raw_line in content.split('\n'):
            line = raw_line.strip()
            if not line or line.startswith('//'):
                continue
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1]
                continue

            if current_section == "General":
                if line.startswith('AudioFilename:'):
                    metadata["audio_filename"] = line.split(':', 1)[1].strip()

            elif current_section == "Metadata":
                for prefix, field in [
                    ('Title:', 'title'), ('Artist:', 'artist'),
                    ('Creator:', 'creator'), ('Version:', 'version'),
                ]:
                    if line.startswith(prefix):
                        metadata[field] = line.split(':', 1)[1].strip()

            elif current_section == "Difficulty":
                if line.startswith('CircleSize:'):
                    try:
                        metadata["column_count"] = int(float(line.split(':', 1)[1].strip()))
                    except ValueError:
                        pass

            elif current_section == "TimingPoints":
                parts = line.split(',')
                if len(parts) >= 2:
                    try:
                        beat_length = float(parts[1])
                        if beat_length > 0:
                            metadata["bpm"] = round(60000 / beat_length, 2)
                    except ValueError:
                        pass

            elif current_section == "Events":
                if line.startswith('0,0,"') and any(
                    ext in line for ext in ('.jpg', '.png', '.jpeg', '.gif', '.bmp')
                ):
                    parts = line.split(',')
                    if len(parts) >= 3:
                        metadata["background"] = parts[2].strip('"')

            elif current_section == "HitObjects":
                parts = line.split(',')
                if len(parts) >= 4 and parts[0].lstrip('-').isdigit():
                    try:
                        x = int(parts[0])
                        time = int(parts[2])
                        type_val = int(parts[3])
                        column_count = metadata["column_count"]

                        end_time = None
                        if type_val & BeatmapExporter.HOLD_NOTE_TYPE and len(parts) >= 6:
                            end_time = int(parts[5].split(':')[0])
                            if end_time <= time:
                                end_time = time + 1

                        if column_count > 0:
                            lane = ((x * column_count) - 256) // 512
                            lane = max(0, min(column_count - 1, lane))
                            metadata["notes"].append((time, lane, end_time))
                    except (ValueError, IndexError):
                        continue

        metadata["notes"].sort(key=lambda n: (n[0], n[1]))
        return metadata

    @staticmethod
    def load_metadata_to_ui(filepath, main_window):
        metadata = BeatmapParser.parse_osu_file(filepath)

        if metadata["title"]:
            main_window.title_input.setText(metadata["title"])
        if metadata["artist"]:
            main_window.artist_input.setText(metadata["artist"])
        if metadata["creator"]:
            main_window.creator_input.setText(metadata["creator"])
        if metadata["version"]:
            main_window.version_input.setText(metadata["version"])
        if metadata["column_count"]:
            main_window.columns_input.setValue(metadata["column_count"])
        if metadata["bpm"]:
            main_window.bpm_input.setValue(int(round(metadata["bpm"])))

        if metadata["notes"]:
            columns = main_window.columns_input.value()
            try:
                validated = BeatmapExporter.validate_notes(metadata["notes"], columns)
                main_window.load_notes(validated)
            except BeatmapValidationError as exc:
                raise BeatmapValidationError(
                    f"Imported notes failed validation: {exc}"
                ) from exc

        return metadata
