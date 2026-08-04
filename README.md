# map!maker

a beatmap editor for osu!mania that doesn't make you want to throw your computer out the window

## what is this

the official osu!mania editor is garbage for actually making maps. this is my attempt at fixing that. you can record notes in real time while the audio plays, customize your keybinds, and export directly to .osu or .osz files.

no more fighting with the timing panel. no more clicking 500 times to place a single pattern. just press keys and go.

## features

- real-time note recording with keyboard input
- hold notes work exactly like you'd expect (press and hold)
- customizable hold threshold (how long you need to hold for it to count as a hold)
- snap-to-grid quantization (1/1 to 1/16)
- BPM detection and manual override
- custom keybinds for each lane (WEIO layout? go for it)
- import existing .osu files
- export to .osu or .osz
- undo/redo because you will mess up
- visual timeline with note preview
- countdown timer before recording
- latency offset for audio sync issues

## installation

```bash
# clone the repo
git clone https://github.com/AstralZX/mapmaker.git
cd mapmaker

# install dependencies
pip install PyQt6

# run it
python main.py
```

that's literally it. no complex setup. no database. no docker containers. just python.

## how to use

1. load an audio file (mp3, wav, ogg, flac, m4a, aac, opus)
2. set your BPM and column count
3. configure keybinds if you don't like the defaults (numbers 1-0 for lanes 1-10)
4. hit record, wait for the countdown, and play your chart
5. press keys to place notes, hold them for hold notes
6. stop recording, export your beatmap

## keybinds

default layout follows osu!mania standards:
- lanes 1-4: 1 2 3 4
- lanes 5-8: 5 6 7 8
- lanes 9-10: 9 0

you can rebind any lane to any key through the keybinds dialog. it'll warn you if you try to use the same key for two lanes.

## the hold threshold thing

this is the one setting you'll actually care about:

- **40ms** - default. feels like osu!mania
- **lower** - more notes become holds (if you're mapping for 7K and want more long notes)
- **higher** - notes need to be held longer to register as holds
- **10000ms** - practically infinite. everything becomes taps

the lower the threshold, the more sensitive it is. if you're getting too many hold notes, bump it up. if you want more holds, drop it down.

## file format support

### import
- .osu files (mania mode only)

### export
- .osu (single file)
- .osz (archive with audio + background)

## config

settings are saved to `beatmap_creator_config.json` in the same directory. you can delete it to reset everything to defaults.

## why did you make this

because the official editor is bad and i was tired of it. simple as that.

## license

do whatever you want with it. i don't care.

## contributing

if you find a bug or want to add something, open an issue or send a PR. i'll probably merge it if it's not totally broken.
