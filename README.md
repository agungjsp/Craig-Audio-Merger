# Craig Audio Merger

A powerful Python script that automatically detects Craig Discord recording folders and merges multiple audio files into a single optimized output file using FFmpeg.

## Features

- 🔍 **Automatic Craig Folder Detection**: Scans for folders matching the Craig naming pattern (`craig-[identifier]`)
- 🎵 **Multi-Format Support**: Handles .aac, .mp3, .wav, and .m4a files
- 🚀 **Dynamic Input Handling**: Automatically adjusts FFmpeg command based on the number of input files
- 🎚️ **Audio Normalization**: Applies loudness normalization for consistent audio levels
- 📊 **Optimized Output**: Balances file size and quality using variable bitrate encoding
- 📈 **Progress Monitoring**: Real-time progress feedback during processing
- 🔧 **Error Handling**: Comprehensive error handling and user feedback

## Requirements

- Python 3.7+
- FFmpeg installed and accessible in PATH
- Craig Discord recording folders with .aac files

## Installation

1. Ensure FFmpeg is installed on your system:
   ```bash
   # macOS (using Homebrew)
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt update && sudo apt install ffmpeg
   
   # Windows (using Chocolatey)
   choco install ffmpeg
   ```

2. Download the script:
   ```bash
   wget https://raw.githubusercontent.com/your-repo/craig-audio-merger/main/audio_merger.py
   # or simply copy the script to your directory
   ```

## Usage

### Basic Usage
```bash
python audio_merger.py
```

### Advanced Usage
```bash
# Specify a different directory
python audio_merger.py -d /path/to/craig/folders

# Dry run to see what would be processed
python audio_merger.py --dry-run
```

### Command Line Options
- `-d, --directory`: Base directory to scan for Craig folders (default: current directory)
- `--dry-run`: Show what would be processed without actually merging files

## How It Works

1. **Detection**: Scans the specified directory for folders matching the Craig pattern
2. **File Discovery**: Identifies all supported audio files in each Craig folder
3. **Sorting**: Naturally sorts files (1, 2, 3... instead of 1, 10, 2...)
4. **Processing**: Builds optimized FFmpeg command with:
   - Dynamic input handling
   - Audio mixing with `amix` filter
   - Loudness normalization
   - Variable bitrate encoding for optimal size/quality ratio
5. **Output**: Creates merged audio file with descriptive filename

## FFmpeg Command Optimization

The script generates optimized FFmpeg commands based on your original:

### For Multiple Files:
```bash
ffmpeg -y -i file1.aac -i file2.aac -i file3.aac \
  -filter_complex "[0:a][1:a][2:a]amix=inputs=3:duration=longest:dropout_transition=2,loudnorm=I=-16:TP=-1.5:LRA=11[out]" \
  -map "[out]" -c:a libmp3lame -q:a 2 -ar 44100 -ac 2 \
  -avoid_negative_ts make_zero output.mp3
```

### Key Improvements:
- **Dynamic Inputs**: Automatically handles any number of input files
- **Audio Normalization**: `loudnorm` filter ensures consistent volume levels
- **Variable Bitrate**: `-q:a 2` provides better quality/size ratio than fixed 320k
- **Dropout Transition**: Smooth handling of audio gaps
- **Timestamp Handling**: Prevents negative timestamp issues

## Output

- **Filename Format**: `merged_[clean_folder_name]_[timestamp].mp3`
- **Quality**: High-quality variable bitrate (~190kbps equivalent)
- **Normalization**: Loudness normalized to -16 LUFS
- **Format**: MP3 stereo at 44.1kHz

## Example Output

```
🎙️  Craig Audio Merger - Starting...
📂 Scanning directory: /Users/username/Documents/Project/audio-merge
✅ Found 1 Craig folder(s):
  📁 craig-mChaT25imLw2-fPhYImMNOPDGJDfikv-jGCqeZc7RPN_aac

============================================================
📁 Processing Craig folder: craig-mChaT25imLw2-fPhYImMNOPDGJDfikv-jGCqeZc7RPN_aac
🎵 Found 6 audio files:
  1. 1-theorizky27.aac
  2. 2-ifantaufiqh.aac
  3. 3-gungjay.aac
  4. 4-oizale.aac
  5. 5-nauvanadam.aac
  6. 6-omrestu.aac
📤 Output file: merged_mChaT25imLw2-fPhYImMNOPDGJDfikv-jGCqeZc7RPN_aac_20241220_143022.mp3
Executing: ffmpeg -y -i /path/to/1-theorizky27.aac... (truncated)
Processing audio files...
Progress: 00:45:23.45
✅ Audio merging completed successfully!
📊 Output file size: 45.67 MB
⏱️  Duration: 45.39 minutes
============================================================

🎯 Summary:
  Total Craig folders: 1
  Successfully merged: 1
  Failed: 0
✅ Audio merging process completed!
```

## Troubleshooting

### FFmpeg Not Found
```
❌ FFmpeg not found. Please install FFmpeg and ensure it's in your PATH.
```
**Solution**: Install FFmpeg and ensure it's accessible from command line.

### No Craig Folders Found
```
❌ No Craig folders found in the current directory.
💡 Craig folders should match pattern: craig-[identifier]
```
**Solution**: Ensure you're in the correct directory or use `-d` to specify the path.

### No Audio Files Found
```
❌ No supported audio files found in the folder.
```
**Solution**: Check that the folder contains .aac, .mp3, .wav, or .m4a files.

## License

This project is open source and available under the MIT License. 