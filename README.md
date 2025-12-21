# Craig Audio Merger

A simple command-line tool that detects Craig Discord recording folders and merges multiple audio files into a single, normalized output using FFmpeg.

## Features

- **Automatic Craig folder detection**: finds folders matching `craig-[identifier]`
- **Multi-format input**: supports .aac, .mp3, .wav, .m4a, .ogg inputs
- **Optimized mixing**: mixes all tracks with `amix` and applies `loudnorm` to -16 LUFS
- **Silence removal**: optionally remove silent sections from the merged audio
- **Flexible output**: choose `mp3`, `wav`, `ogg`, `aac`, or `m4a` with quality presets
- **Progress + logging**: clear console logs with progress updates

## Requirements

- Python 3.8+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- FFmpeg installed and available on PATH

## Installation

Clone the repository:

```bash
git clone https://github.com/your-username/craig-audio-merger.git
cd craig-audio-merger
```

Install uv (if not already installed):

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Install FFmpeg:

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows (using winget)
winget install ffmpeg
```

## Usage

### Basic Usage

```bash
# Process current directory
uv run audio_merger.py

# Process a specific directory
uv run audio_merger.py -d /path/to/craig
```

### Command-Line Options

| Option | Description |
|--------|-------------|
| `-d, --directory` | Base directory to scan (default: current directory) |
| `--output-dir` | Directory to write merged files (default: same as input) |
| `--format` | Output format: `mp3`, `wav`, `ogg`, `aac`, `m4a` (default: `mp3`) |
| `--quality` | Quality preset: `low`, `medium`, `high` (default: `medium`) |
| `--remove-silence` | Remove silent sections from the merged audio |
| `--delete-originals` | Delete Craig folder(s) after a successful merge |
| `--dry-run` | Show what would be processed without merging |
| `-v, --verbose` | Enable verbose logging |

### Examples

```bash
# Preview what would be processed (dry run)
uv run audio_merger.py --dry-run

# High-quality WAV output
uv run audio_merger.py --format wav --quality high

# Remove silence from merged audio
uv run audio_merger.py --remove-silence

# MP3 output with silence removal and high quality
uv run audio_merger.py --format mp3 --quality high --remove-silence

# Process and delete original Craig folders after merge
uv run audio_merger.py --delete-originals

# Full example with all options
uv run audio_merger.py -d /path/to/recordings --output-dir /path/to/output \
    --format mp3 --quality high --remove-silence -v
```

### Output Formats & Quality

| Format | Codec | Quality Settings |
|--------|-------|------------------|
| `mp3` | libmp3lame | VBR: low=4, medium=2, high=0 |
| `ogg` | libvorbis | Quality: low=4, medium=5, high=6 |
| `aac` | aac | Bitrate: low=128k, medium=192k, high=256k |
| `m4a` | aac | Bitrate: low=128k, medium=192k, high=256k |
| `wav` | pcm_s16le | Lossless (quality setting ignored) |

## Notes

- Output files are named: `merged_[folder_name]_[YYYYMMDD_HHMMSS].[ext]`
- Craig folders must match the pattern: `craig-[identifier]`
- The `--remove-silence` option removes gaps longer than 0.5s below -50dB
- Audio is normalized to -16 LUFS with -1.5dB true peak

## License

MIT
