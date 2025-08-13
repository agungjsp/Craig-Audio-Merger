# Craig Audio Merger

A simple command‑line tool that detects Craig Discord recording folders and merges multiple audio files into a single, normalized output using FFmpeg.

## Features

- **Automatic Craig folder detection**: finds folders matching `craig-[identifier]`
- **Multi‑format input**: supports .aac, .mp3, .wav, .m4a inputs
- **Optimized mixing**: mixes all tracks with `amix` and applies `loudnorm` to -16 LUFS
- **Flexible output**: choose `mp3`, `wav`, `ogg`, or `aac` with quality presets
- **Progress + logging**: clear console logs with progress updates

## Requirements

- Python 3.8+
- FFmpeg installed and available on PATH

## Installation

Clone the repository (no Python package dependencies required):

```bash
git clone https://github.com/your-username/craig-audio-merger.git
cd craig-audio-merger
```

## Usage

Basic:

```bash
python audio_merger.py
```

Options:

- `-d, --directory` Base directory to scan (default: current directory)
- `--output-dir` Directory to write merged files (default: same as input)
- `--format` Output format: `mp3`, `wav`, `ogg`, `aac` (default: `mp3`)
- `--quality` Quality preset: `low`, `medium`, `high` (default: `medium`)
- `--delete-originals` Delete Craig folder(s) after a successful merge
- `--dry-run` Show what would be processed without merging
- `-v, --verbose` More detailed logs

Examples:

```bash
# Process a specific directory
python audio_merger.py -d /path/to/craig

# Preview without writing files
python audio_merger.py --dry-run

# High‑quality WAV output
python audio_merger.py --format wav --quality high

# Delete Craig folder(s) after merge
python audio_merger.py --delete-originals
```

## Notes

- Output files are named like `merged_[clean_folder_name]_[YYYYMMDD_HHMMSS].[ext]`
- For `wav` output, the tool uses PCM 16‑bit (`pcm_s16le`) and ignores quality presets (since lossless)
- Ensure FFmpeg is installed. On macOS: `brew install ffmpeg`; Debian/Ubuntu: `sudo apt install ffmpeg`

## License

MIT
