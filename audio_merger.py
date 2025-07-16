#!/usr/bin/env python3
"""
Craig Audio Merger - Automatic multi-audio file merger
Detects Craig folders and merges .aac files into a single optimized audio file
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

class CraigAudioMerger:
    def __init__(self, base_directory: str = ".", output_dir: Optional[str] = None):
        self.base_directory = Path(base_directory)
        self.output_dir = Path(output_dir) if output_dir else self.base_directory
        self.supported_formats = [".aac", ".mp3", ".wav", ".m4a"]
        self.craig_pattern = re.compile(r"craig-[a-zA-Z0-9_-]+")
        self.logger = logging.getLogger(__name__)

    def check_ffmpeg(self) -> bool:
        """Check if FFmpeg is installed and meets minimum version"""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                check=True,
            )
            version_match = re.search(r"ffmpeg version (\d+\.\d+)", result.stdout)
            if version_match:
                version = float(version_match.group(1))
                if version < 4.0:
                    self.logger.error(
                        "FFmpeg version is too old (needs 4.0+ for loudnorm)"
                    )
                    return False
                return True
            return False
        except FileNotFoundError:
            self.logger.error(
                "FFmpeg not found. Please install FFmpeg and ensure it's in your PATH."
            )
            return False
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error checking FFmpeg: {e}")
            return False

    def detect_craig_folders(self) -> List[Path]:
        """Detect all Craig folders in the base directory"""
        craig_folders = [
            item
            for item in self.base_directory.iterdir()
            if item.is_dir() and self.craig_pattern.match(item.name)
        ]
        return craig_folders

    def scan_audio_files(self, folder: Path) -> List[Path]:
        """Scan for supported audio files in the given folder using glob"""
        audio_files = []
        for ext in self.supported_formats:
            audio_files.extend(folder.glob(f"*{ext}"))
        # Natural sort (handles Unicode and numbers properly)
        audio_files.sort(
            key=lambda x: [
                int(s) if s.isdigit() else s.lower()
                for s in re.split(r"(\d+)", x.name)
            ]
        )
        return audio_files

    def get_audio_info(self, file_path: Path) -> dict:
        """Get audio file information using ffprobe"""
        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(file_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            self.logger.debug(f"Error getting audio info for {file_path}: {e}")
            return {}

    def get_total_duration(self, input_files: List[Path]) -> float:
        """Estimate total duration from the longest input file"""
        max_duration = 0.0
        for file in input_files:
            info = self.get_audio_info(file)
            if "format" in info and "duration" in info["format"]:
                duration = float(info["format"]["duration"])
                if duration > max_duration:
                    max_duration = duration
        return max_duration

    def build_ffmpeg_command(
        self,
        input_files: List[Path],
        output_file: Path,
        output_format: str,
        quality_level: str,
    ) -> List[str]:
        """Build optimized FFmpeg command for merging audio files"""
        if not input_files:
            raise ValueError("No input files provided")

        cmd = ["ffmpeg", "-y"]  # -y to overwrite output file

        # Add input files
        for file in input_files:
            cmd.extend(["-i", str(file)])

        # Build filter_complex
        num_inputs = len(input_files)
        if num_inputs == 1:
            filter_complex = "[0:a]loudnorm=I=-16:TP=-1.5:LRA=11[out]"
        else:
            inputs_str = "".join(f"[{i}:a]" for i in range(num_inputs))
            filter_complex = (
                f"{inputs_str}amix=inputs={num_inputs}:duration=longest:"
                "dropout_transition=2,loudnorm=I=-16:TP=-1.5:LRA=11[out]"
            )

        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[out]"])

        # Encoding settings based on format and quality
        quality_map = {"low": "4", "medium": "2", "high": "0"}  # For -q:a (VBR)
        codec_map = {
            "mp3": "libmp3lame",
            "wav": "pcm_s16le",
            "ogg": "libvorbis",
            "aac": "aac",
        }
        if output_format not in codec_map:
            raise ValueError(f"Unsupported output format: {output_format}")

        cmd.extend(
            [
                "-c:a",
                codec_map[output_format],
                "-q:a",
                quality_map.get(quality_level, "2"),  # Default medium
                "-ar",
                "44100",
                "-ac",
                "2",
                "-avoid_negative_ts",
                "make_zero",
            ]
        )

        # Add metadata
        clean_name = re.sub(r"^craig-", "", output_file.stem)
        cmd.extend(
            [
                "-metadata",
                f"title=Merged {clean_name}",
                "-metadata",
                "artist=Craig Recording",
                "-metadata",
                f"date={time.strftime('%Y-%m-%d')}",
            ]
        )

        cmd.append(str(output_file))
        return cmd

    def execute_ffmpeg(
        self, cmd: List[str], total_duration: float
    ) -> Tuple[bool, str]:
        """Execute FFmpeg command with progress monitoring"""
        self.logger.info(f"Executing FFmpeg command (truncated): {' '.join(cmd[:5])}...")
        self.logger.info("Processing audio files...")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True,
            )

            # Monitor progress
            while True:
                output = process.stderr.readline()
                if output == "" and process.poll() is not None:
                    break
                if output and "time=" in output:
                    time_match = re.search(r"time=(\d+:\d+:\d+\.\d+)", output)
                    if time_match:
                        current_time = self._time_to_seconds(time_match.group(1))
                        percentage = (
                            (current_time / total_duration) * 100
                            if total_duration > 0
                            else 0
                        )
                        sys.stdout.write(
                            f"\rProgress: {time_match.group(1)} ({percentage:.1f}%)"
                        )
                        sys.stdout.flush()

            print()  # New line after progress

            rc = process.poll()
            stderr_output = process.stderr.read()
            if rc == 0:
                self.logger.info("✅ Audio merging completed successfully!")
                return True, ""
            else:
                self.logger.error(f"❌ FFmpeg error: {stderr_output}")
                return False, stderr_output
        except Exception as e:
            self.logger.error(f"❌ Error executing FFmpeg: {e}")
            return False, str(e)

    def _time_to_seconds(self, time_str: str) -> float:
        """Convert HH:MM:SS.ss to seconds"""
        h, m, s = time_str.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    def generate_output_filename(
        self, craig_folder: Path, output_format: str
    ) -> str:
        """Generate output filename based on Craig folder name"""
        folder_name = craig_folder.name
        clean_name = re.sub(r"^craig-", "", folder_name)
        clean_name = re.sub(r"[^a-zA-Z0-9_-]", "_", clean_name)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        return f"merged_{clean_name}_{timestamp}.{output_format}"

    def delete_originals(self, input_files: List[Path]) -> None:
        """Delete original files after confirmation"""
        confirm = input(
            "Delete original files? (y/n): "
        ).lower()  # Note: For non-interactive, could make this a flag param
        if confirm == "y":
            for file in input_files:
                try:
                    file.unlink()
                    self.logger.info(f"Deleted: {file}")
                except Exception as e:
                    self.logger.warning(f"Failed to delete {file}: {e}")

    def merge_audio_files(
        self,
        craig_folder: Path,
        output_format: str = "mp3",
        quality_level: str = "medium",
        delete_originals: bool = False,
    ) -> bool:
        """Merge audio files from a Craig folder into a single output file"""
        try:
            # Scan for audio files
            audio_files = self.scan_audio_files(craig_folder)
            if not audio_files:
                self.logger.error("❌ No supported audio files found in the folder.")
                return False

            self.logger.info(f"🎵 Found {len(audio_files)} audio files:")
            for i, file in enumerate(audio_files, 1):
                self.logger.info(f"  {i}. {file.name}")

            # Generate output filename
            output_filename = self.generate_output_filename(craig_folder, output_format)
            output_file = self.output_dir / output_filename
            self.logger.info(f"📤 Output file: {output_filename}")

            # Get total duration for progress monitoring
            total_duration = self.get_total_duration(audio_files)

            # Build and execute FFmpeg command
            cmd = self.build_ffmpeg_command(
                audio_files, output_file, output_format, quality_level
            )
            success, error = self.execute_ffmpeg(cmd, total_duration)

            if success and output_file.exists():
                # Display file info
                file_size = output_file.stat().st_size / (1024 * 1024)  # MB
                self.logger.info(f"📊 Output file size: {file_size:.2f} MB")
                
                # Get duration if possible
                output_info = self.get_audio_info(output_file)
                if "format" in output_info and "duration" in output_info["format"]:
                    duration = float(output_info["format"]["duration"])
                    self.logger.info(f"⏱️  Duration: {duration/60:.2f} minutes")

                # Delete originals if requested
                if delete_originals:
                    self.delete_originals(audio_files)

                return True
            else:
                self.logger.error(f"❌ Merging failed: {error}")
                return False

        except Exception as e:
            self.logger.error(f"❌ Error processing {craig_folder}: {e}")
            return False

    def process_all_craig_folders(
        self,
        output_format: str = "mp3",
        quality_level: str = "medium",
        delete_originals: bool = False,
        dry_run: bool = False,
    ) -> None:
        """Process all Craig folders in the base directory"""
        self.logger.info("🎙️  Craig Audio Merger - Starting...")
        self.logger.info(f"📂 Scanning directory: {self.base_directory}")

        # Check FFmpeg
        if not self.check_ffmpeg():
            return

        # Detect Craig folders
        craig_folders = self.detect_craig_folders()
        if not craig_folders:
            self.logger.error("❌ No Craig folders found in the current directory.")
            self.logger.info("💡 Craig folders should match pattern: craig-[identifier]")
            return

        self.logger.info(f"✅ Found {len(craig_folders)} Craig folder(s):")
        for folder in craig_folders:
            self.logger.info(f"  📁 {folder.name}")

        if dry_run:
            self.logger.info("🔍 Dry run mode - no files will be processed")
            for folder in craig_folders:
                audio_files = self.scan_audio_files(folder)
                output_filename = self.generate_output_filename(folder, output_format)
                self.logger.info(f"\n📁 {folder.name}")
                self.logger.info(f"  🎵 Audio files: {len(audio_files)}")
                self.logger.info(f"  📤 Would create: {output_filename}")
            return

        # Process each folder
        total_folders = len(craig_folders)
        successful = 0
        failed = 0

        for folder in craig_folders:
            self.logger.info("=" * 60)
            self.logger.info(f"📁 Processing Craig folder: {folder.name}")

            if self.merge_audio_files(folder, output_format, quality_level, delete_originals):
                successful += 1
            else:
                failed += 1

        # Summary
        self.logger.info("=" * 60)
        self.logger.info("🎯 Summary:")
        self.logger.info(f"  Total Craig folders: {total_folders}")
        self.logger.info(f"  Successfully merged: {successful}")
        self.logger.info(f"  Failed: {failed}")
        
        if failed == 0:
            self.logger.info("✅ Audio merging process completed!")
        else:
            self.logger.warning(f"⚠️  Process completed with {failed} failures.")


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration"""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Craig Audio Merger - Merge Craig Discord recording files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python audio_merger.py                    # Process current directory
  python audio_merger.py -d /path/to/craig  # Process specific directory
  python audio_merger.py --dry-run          # Show what would be processed
  python audio_merger.py --format wav      # Output as WAV files
  python audio_merger.py --quality high    # High quality output
        """
    )
    
    parser.add_argument(
        "-d", "--directory",
        default=".",
        help="Base directory to scan for Craig folders (default: current directory)"
    )
    
    parser.add_argument(
        "--output-dir",
        help="Output directory for merged files (default: same as input directory)"
    )
    
    parser.add_argument(
        "--format",
        choices=["mp3", "wav", "ogg", "aac"],
        default="mp3",
        help="Output format (default: mp3)"
    )
    
    parser.add_argument(
        "--quality",
        choices=["low", "medium", "high"],
        default="medium",
        help="Output quality level (default: medium)"
    )
    
    parser.add_argument(
        "--delete-originals",
        action="store_true",
        help="Delete original files after successful merge"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without actually merging files"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Create merger instance
    merger = CraigAudioMerger(args.directory, args.output_dir)

    # Process folders
    merger.process_all_craig_folders(
        output_format=args.format,
        quality_level=args.quality,
        delete_originals=args.delete_originals,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()