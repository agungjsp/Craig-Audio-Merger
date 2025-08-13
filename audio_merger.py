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
import shutil
from pathlib import Path
from typing import List, Optional, Tuple, Callable, Dict, Any

class CraigAudioMerger:
    def __init__(self, base_directory: str = ".", output_dir: Optional[str] = None,
                 progress_callback: Optional[Callable[[float], None]] = None,
                 log_callback: Optional[Callable[[str, str], None]] = None,
                 status_callback: Optional[Callable[[str], None]] = None):
        self.base_directory = Path(base_directory)
        self.output_dir = Path(output_dir) if output_dir else self.base_directory
        self.supported_formats = [".aac", ".mp3", ".wav", ".m4a", ".ogg"]
        self.craig_pattern = re.compile(r"craig-[a-zA-Z0-9_-]+")
        self.logger = logging.getLogger(__name__)
        
        # UI callbacks
        self.progress_callback = progress_callback
        self.log_callback = log_callback  # (message, level)
        self.status_callback = status_callback
        self.cancel_requested = False

    def _log(self, message: str, level: str = "info"):
        """Internal logging with UI callback support"""
        if self.log_callback:
            self.log_callback(message, level)
        
        # Standard logging
        if level == "error":
            self.logger.error(message)
        elif level == "warning":
            self.logger.warning(message)
        elif level == "debug":
            self.logger.debug(message)
        else:
            self.logger.info(message)
    
    def _update_status(self, status: str):
        """Update processing status"""
        if self.status_callback:
            self.status_callback(status)
    
    def _update_progress(self, progress: float):
        """Update progress (0.0 to 1.0)"""
        if self.progress_callback:
            self.progress_callback(progress)
    
    def cancel_processing(self):
        """Request cancellation of current processing"""
        self.cancel_requested = True
        self._update_status("Cancelling...")
    
    def check_ffmpeg(self) -> bool:
        """Check if FFmpeg is installed and meets minimum version"""
        try:
            self._update_status("Checking FFmpeg...")
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
                    self._log(
                        "FFmpeg version is too old (needs 4.0+ for loudnorm)", "error"
                    )
                    return False
                self._log(f"FFmpeg version {version} detected")
            else:
                # Could not parse version but ffmpeg exists; continue
                self._log("FFmpeg detected")

            # Also check ffprobe availability
            try:
                subprocess.run(["ffprobe", "-version"], capture_output=True, text=True, check=True)
            except (FileNotFoundError, subprocess.CalledProcessError):
                self._log("ffprobe not found. Please install FFmpeg with ffprobe.", "error")
                return False

            return True
        except FileNotFoundError:
            self._log(
                "FFmpeg not found. Please install FFmpeg and ensure it's in your PATH.", "error"
            )
            return False
        except subprocess.CalledProcessError as e:
            self._log(f"Error checking FFmpeg: {e}", "error")
            return False

    def detect_craig_folders(self) -> List[Path]:
        """Detect all Craig folders in the base directory"""
        self._update_status("Scanning for Craig folders...")
        craig_folders = [
            item
            for item in self.base_directory.iterdir()
            if item.is_dir() and self.craig_pattern.match(item.name)
        ]
        self._log(f"Found {len(craig_folders)} Craig folder(s)")
        return craig_folders

    def scan_audio_files(self, folder: Path) -> List[Path]:
        """Scan for supported audio files in the given folder (case-insensitive)"""
        # Collect files by suffix to support case-insensitive matching and avoid glob pitfalls
        audio_files = [
            path for path in folder.iterdir()
            if path.is_file() and path.suffix.lower() in self.supported_formats and path.stat().st_size > 0
        ]
        # Natural sort (handles Unicode and numbers properly)
        audio_files.sort(
            key=lambda path: [
                int(segment) if segment.isdigit() else segment.lower()
                for segment in re.split(r"(\d+)", path.name)
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
        codec_map = {
            "mp3": "libmp3lame",
            "wav": "pcm_s16le",
            "ogg": "libvorbis",
            "aac": "aac",
            "m4a": "aac",  # AAC in MP4 container
        }
        if output_format not in codec_map:
            raise ValueError(f"Unsupported output format: {output_format}")

        cmd.extend(["-c:a", codec_map[output_format]])

        # Apply codec-appropriate quality settings
        if output_format == "mp3":
            # libmp3lame VBR scale: 0 (best) .. 9 (worst)
            mp3_quality_map = {"low": "4", "medium": "2", "high": "0"}
            cmd.extend(["-q:a", mp3_quality_map.get(quality_level, "2")])
        elif output_format == "ogg":
            # libvorbis quality scale: typically 0..10
            ogg_quality_map = {"low": "4", "medium": "5", "high": "6"}
            cmd.extend(["-q:a", ogg_quality_map.get(quality_level, "5")])
        elif output_format in {"aac", "m4a"}:
            # Use target bitrates for native AAC encoder
            aac_bitrate_map = {"low": "128k", "medium": "192k", "high": "256k"}
            cmd.extend(["-b:a", aac_bitrate_map.get(quality_level, "192k")])
        # WAV is lossless PCM, no quality setting

        # Common output audio parameters
        cmd.extend([
            "-ar", "44100",
            "-ac", "2",
            "-avoid_negative_ts", "make_zero",
        ])

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
        self, cmd: List[str], estimated_duration: Optional[float] = None
    ) -> Tuple[bool, str]:
        """Execute FFmpeg command with progress monitoring"""
        self._log(f"Executing FFmpeg command (truncated): {' '.join(cmd[:5])}...")
        self._update_status("Processing audio files...")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True,
            )

            # Monitor progress
            stderr_lines = []
            while True:
                if self.cancel_requested:
                    process.terminate()
                    self._log("Processing cancelled by user", "warning")
                    return False, "Cancelled by user"
                
                output = process.stderr.readline()
                if output == "" and process.poll() is not None:
                    break
                
                stderr_lines.append(output)
                
                if output and "time=" in output:
                    time_match = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", output)
                    if time_match and estimated_duration:
                        hours = int(time_match.group(1))
                        minutes = int(time_match.group(2))
                        seconds = float(time_match.group(3))
                        current_time = hours * 3600 + minutes * 60 + seconds
                        progress = min(current_time / estimated_duration, 0.95)
                        self._update_progress(progress)
                        self._log(f"Progress: {time_match.group(0)[5:]}")

            rc = process.poll()
            stderr_output = ''.join(stderr_lines)
            
            if rc == 0:
                self._update_progress(1.0)
                self._log("✅ Audio merging completed successfully!")
                self._update_status("Completed successfully")
                return True, ""
            else:
                self._log(f"❌ FFmpeg error: {stderr_output}", "error")
                self._update_status("Processing failed")
                return False, stderr_output
        except Exception as e:
            self._log(f"❌ Error executing FFmpeg: {e}", "error")
            self._update_status("Processing failed")
            return False, str(e)


    def generate_output_filename(
        self, craig_folder: Path, output_format: str
    ) -> str:
        """Generate output filename based on Craig folder name"""
        folder_name = craig_folder.name
        clean_name = re.sub(r"^craig-", "", folder_name)
        clean_name = re.sub(r"[^a-zA-Z0-9_-]", "_", clean_name)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        return f"merged_{clean_name}_{timestamp}.{output_format}"

    def delete_originals(self, craig_folder: Path) -> None:
        """Delete the entire Craig folder after successful merge"""
        try:
            # Extra safety: only remove folders that match the Craig pattern
            if craig_folder.is_dir() and self.craig_pattern.match(craig_folder.name):
                shutil.rmtree(craig_folder)
                self._log(f"Deleted folder: {craig_folder}")
            else:
                self._log(f"Refusing to delete non-Craig folder: {craig_folder}", "warning")
        except Exception as e:
            self._log(f"Failed to delete folder {craig_folder}: {e}", "warning")

    def get_estimated_duration(self, audio_files: List[Path]) -> Optional[float]:
        """Estimate total duration by getting info from the longest file"""
        try:
            max_duration = 0.0
            for file in audio_files:
                info = self.get_audio_info(file)
                if "format" in info and "duration" in info["format"]:
                    duration = float(info["format"]["duration"])
                    max_duration = max(max_duration, duration)
            return max_duration if max_duration > 0 else None
        except Exception:
            return None
    
    def merge_audio_files(
        self,
        craig_folder: Path,
        output_format: str = "mp3",
        quality_level: str = "medium",
        delete_originals: bool = False,
    ) -> Tuple[bool, Optional[Path]]:
        """Merge audio files from a Craig folder into a single output file"""
        try:
            self.cancel_requested = False
            self._update_status(f"Processing {craig_folder.name}...")
            
            # Scan for audio files
            audio_files = self.scan_audio_files(craig_folder)
            if not audio_files:
                self._log("❌ No supported audio files found in the folder.", "error")
                return False, None

            self._log(f"🎵 Found {len(audio_files)} audio files:")
            for i, file in enumerate(audio_files, 1):
                self._log(f"  {i}. {file.name}")

            # Generate output filename
            output_filename = self.generate_output_filename(craig_folder, output_format)
            output_file = self.output_dir / output_filename
            self._log(f"📤 Output file: {output_filename}")

            # Get estimated duration for progress tracking
            estimated_duration = self.get_estimated_duration(audio_files)

            # Build and execute FFmpeg command
            cmd = self.build_ffmpeg_command(
                audio_files, output_file, output_format, quality_level
            )
            success, error = self.execute_ffmpeg(cmd, estimated_duration)

            if success and output_file.exists():
                # Display file info
                file_size = output_file.stat().st_size / (1024 * 1024)  # MB
                self._log(f"📊 Output file size: {file_size:.2f} MB")
                
                # Get duration if possible
                output_info = self.get_audio_info(output_file)
                if "format" in output_info and "duration" in output_info["format"]:
                    duration = float(output_info["format"]["duration"])
                    self._log(f"⏱️  Duration: {duration/60:.2f} minutes")

                # Delete originals if requested
                if delete_originals:
                    self.delete_originals(craig_folder)

                return True, output_file
            else:
                self._log(f"❌ Merging failed: {error}", "error")
                return False, None

        except Exception as e:
            self._log(f"❌ Error processing {craig_folder}: {e}", "error")
            return False, None

    def process_all_craig_folders(
        self,
        output_format: str = "mp3",
        quality_level: str = "medium",
        delete_originals: bool = False,
        dry_run: bool = False,
        selected_folders: Optional[List[Path]] = None,
    ) -> Dict[str, Any]:
        """Process all Craig folders in the base directory"""
        self._log("🎙️  Craig Audio Merger - Starting...")
        self._update_status("Starting audio merger...")
        
        # Check FFmpeg
        if not self.check_ffmpeg():
            return {"success": False, "error": "FFmpeg check failed"}

        # Detect Craig folders
        craig_folders = self.detect_craig_folders()
        if not craig_folders:
            self._log("❌ No Craig folders found in the current directory.", "error")
            self._log("💡 Craig folders should match pattern: craig-[identifier]")
            return {"success": False, "error": "No Craig folders found"}

        # Use selected folders if provided
        if selected_folders is not None:
            craig_folders = [f for f in craig_folders if f in selected_folders]

        self._log(f"✅ Found {len(craig_folders)} Craig folder(s):")
        for folder in craig_folders:
            self._log(f"  📁 {folder.name}")

        if dry_run:
            self._log("🔍 Dry run mode - no files will be processed")
            results = []
            for folder in craig_folders:
                audio_files = self.scan_audio_files(folder)
                output_filename = self.generate_output_filename(folder, output_format)
                results.append({
                    "folder": folder.name,
                    "audio_files": len(audio_files),
                    "output_filename": output_filename
                })
                self._log(f"\n📁 {folder.name}")
                self._log(f"  🎵 Audio files: {len(audio_files)}")
                self._log(f"  📤 Would create: {output_filename}")
            return {"success": True, "dry_run_results": results}

        # Process each folder
        total_folders = len(craig_folders)
        successful = 0
        failed = 0
        output_files = []
        
        for i, folder in enumerate(craig_folders):
            if self.cancel_requested:
                self._log("Processing cancelled by user", "warning")
                break
                
            folder_progress = i / total_folders
            self._update_progress(folder_progress)
            
            self._log("=" * 60)
            self._log(f"📁 Processing Craig folder: {folder.name}")

            success, output_file = self.merge_audio_files(folder, output_format, quality_level, delete_originals)
            if success:
                successful += 1
                if output_file:
                    output_files.append(output_file)
            else:
                failed += 1

        # Summary
        self._log("=" * 60)
        self._log("🎯 Summary:")
        self._log(f"  Total Craig folders: {total_folders}")
        self._log(f"  Successfully merged: {successful}")
        self._log(f"  Failed: {failed}")
        
        if failed == 0 and not self.cancel_requested:
            self._log("✅ Audio merging process completed!")
            self._update_status("All processing completed successfully")
        elif self.cancel_requested:
            self._update_status("Processing cancelled")
        else:
            self._log(f"⚠️  Process completed with {failed} failures.", "warning")
            self._update_status(f"Completed with {failed} failures")
        
        return {
            "success": failed == 0 and not self.cancel_requested,
            "total": total_folders,
            "successful": successful,
            "failed": failed,
            "output_files": output_files,
            "cancelled": self.cancel_requested
        }


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
        choices=["mp3", "wav", "ogg", "aac", "m4a"],
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
        help="Delete Craig folder(s) after successful merge"
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
    results = merger.process_all_craig_folders(
        output_format=args.format,
        quality_level=args.quality,
        delete_originals=args.delete_originals,
        dry_run=args.dry_run
    )

    # Exit with non-zero code on failure for CI/scripting use
    if not results.get("success", False):
        sys.exit(1)


if __name__ == "__main__":
    main()