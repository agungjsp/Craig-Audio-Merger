#!/usr/bin/env python3
"""
Craig Audio Merger - Automatic multi-audio file merger
Detects Craig folders and merges .aac files into a single optimized audio file
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple
import json
import time

class CraigAudioMerger:
    def __init__(self, base_directory: str = "."):
        self.base_directory = Path(base_directory)
        self.supported_formats = ['.aac', '.mp3', '.wav', '.m4a']
        self.craig_pattern = re.compile(r'craig-[a-zA-Z0-9_-]+')
        
    def detect_craig_folders(self) -> List[Path]:
        """Detect all Craig folders in the base directory"""
        craig_folders = []
        
        for item in self.base_directory.iterdir():
            if item.is_dir() and self.craig_pattern.match(item.name):
                craig_folders.append(item)
                
        return craig_folders
    
    def scan_audio_files(self, folder: Path) -> List[Path]:
        """Scan for supported audio files in the given folder"""
        audio_files = []
        
        for file in folder.iterdir():
            if file.is_file() and file.suffix.lower() in self.supported_formats:
                audio_files.append(file)
                
        # Sort files naturally (1, 2, 3... instead of 1, 10, 2...)
        audio_files.sort(key=lambda x: [int(s) if s.isdigit() else s.lower() 
                                       for s in re.split(r'(\d+)', x.name)])
        
        return audio_files
    
    def get_audio_info(self, file_path: Path) -> dict:
        """Get audio file information using ffprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', str(file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return {}
    
    def build_ffmpeg_command(self, input_files: List[Path], output_file: Path) -> List[str]:
        """Build optimized FFmpeg command for merging audio files"""
        if not input_files:
            raise ValueError("No input files provided")
        
        # Base command
        cmd = ['ffmpeg', '-y']  # -y to overwrite output file
        
        # Add input files
        for file in input_files:
            cmd.extend(['-i', str(file)])
        
        # Build filter_complex for dynamic number of inputs
        num_inputs = len(input_files)
        
        if num_inputs == 1:
            # Single file - just convert with normalization
            filter_complex = '[0:a]loudnorm=I=-16:TP=-1.5:LRA=11[out]'
        else:
            # Multiple files - mix and normalize
            # Create amix filter for all inputs
            inputs_str = ''.join(f'[{i}:a]' for i in range(num_inputs))
            filter_complex = f'{inputs_str}amix=inputs={num_inputs}:duration=longest:dropout_transition=2,loudnorm=I=-16:TP=-1.5:LRA=11[out]'
        
        cmd.extend(['-filter_complex', filter_complex])
        cmd.extend(['-map', '[out]'])
        
        # Optimized encoding settings for voice/speech
        cmd.extend([
            '-c:a', 'libmp3lame',    # MP3 encoder
            '-q:a', '2',             # Variable bitrate, high quality (equivalent to ~190kbps)
            '-ar', '44100',          # Sample rate
            '-ac', '2',              # Stereo output
            '-avoid_negative_ts', 'make_zero',  # Handle timestamp issues
            str(output_file)
        ])
        
        return cmd
    
    def execute_ffmpeg(self, cmd: List[str]) -> bool:
        """Execute FFmpeg command with progress monitoring"""
        try:
            print(f"Executing: {' '.join(cmd[:5])}... (truncated)")
            print("Processing audio files...")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True
            )
            
            # Monitor progress
            while True:
                output = process.stderr.readline()
                if output == '' and process.poll() is not None:
                    break
                if output and 'time=' in output:
                    # Extract and display progress
                    time_match = re.search(r'time=(\d+:\d+:\d+\.\d+)', output)
                    if time_match:
                        print(f"\rProgress: {time_match.group(1)}", end='', flush=True)
            
            print()  # New line after progress
            
            rc = process.poll()
            if rc == 0:
                print("✅ Audio merging completed successfully!")
                return True
            else:
                stderr_output = process.stderr.read()
                print(f"❌ FFmpeg error: {stderr_output}")
                return False
                
        except FileNotFoundError:
            print("❌ FFmpeg not found. Please install FFmpeg and ensure it's in your PATH.")
            return False
        except Exception as e:
            print(f"❌ Error executing FFmpeg: {e}")
            return False
    
    def generate_output_filename(self, craig_folder: Path) -> str:
        """Generate output filename based on Craig folder name"""
        # Extract meaningful part from Craig folder name
        folder_name = craig_folder.name
        
        # Remove 'craig-' prefix and clean up
        clean_name = re.sub(r'^craig-', '', folder_name)
        clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', clean_name)
        
        # Add timestamp for uniqueness
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        return f"merged_{clean_name}_{timestamp}.mp3"
    
    def merge_audio_files(self, craig_folder: Path) -> bool:
        """Main method to merge audio files from a Craig folder"""
        print(f"📁 Processing Craig folder: {craig_folder.name}")
        
        # Scan for audio files
        audio_files = self.scan_audio_files(craig_folder)
        
        if not audio_files:
            print("❌ No supported audio files found in the folder.")
            return False
        
        print(f"🎵 Found {len(audio_files)} audio files:")
        for i, file in enumerate(audio_files, 1):
            print(f"  {i}. {file.name}")
        
        # Generate output filename
        output_filename = self.generate_output_filename(craig_folder)
        output_path = craig_folder / output_filename
        
        print(f"📤 Output file: {output_filename}")
        
        # Build and execute FFmpeg command
        try:
            cmd = self.build_ffmpeg_command(audio_files, output_path)
            success = self.execute_ffmpeg(cmd)
            
            if success and output_path.exists():
                # Display file size
                file_size = output_path.stat().st_size
                file_size_mb = file_size / (1024 * 1024)
                print(f"📊 Output file size: {file_size_mb:.2f} MB")
                
                # Display audio info
                audio_info = self.get_audio_info(output_path)
                if audio_info and 'format' in audio_info:
                    duration = float(audio_info['format'].get('duration', 0))
                    print(f"⏱️  Duration: {duration/60:.2f} minutes")
                
                return True
            else:
                return False
                
        except Exception as e:
            print(f"❌ Error during processing: {e}")
            return False
    
    def run(self) -> None:
        """Main execution method"""
        print("🎙️  Craig Audio Merger - Starting...")
        print(f"📂 Scanning directory: {self.base_directory.absolute()}")
        
        # Detect Craig folders
        craig_folders = self.detect_craig_folders()
        
        if not craig_folders:
            print("❌ No Craig folders found in the current directory.")
            print("💡 Craig folders should match pattern: craig-[identifier]")
            return
        
        print(f"✅ Found {len(craig_folders)} Craig folder(s):")
        for folder in craig_folders:
            print(f"  📁 {folder.name}")
        
        # Process each Craig folder
        successful_merges = 0
        
        for craig_folder in craig_folders:
            print(f"\n{'='*60}")
            if self.merge_audio_files(craig_folder):
                successful_merges += 1
            print(f"{'='*60}")
        
        # Summary
        print(f"\n🎯 Summary:")
        print(f"  Total Craig folders: {len(craig_folders)}")
        print(f"  Successfully merged: {successful_merges}")
        print(f"  Failed: {len(craig_folders) - successful_merges}")
        
        if successful_merges > 0:
            print("✅ Audio merging process completed!")
        else:
            print("❌ No audio files were successfully merged.")


def main():
    """Main entry point"""
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Craig Audio Merger - Merge multiple audio files from Craig folders"
    )
    parser.add_argument(
        "-d", "--directory",
        default=".",
        help="Base directory to scan for Craig folders (default: current directory)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without actually merging"
    )
    
    args = parser.parse_args()
    
    # Create merger instance
    merger = CraigAudioMerger(args.directory)
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be processed")
        craig_folders = merger.detect_craig_folders()
        for folder in craig_folders:
            audio_files = merger.scan_audio_files(folder)
            print(f"📁 {folder.name}: {len(audio_files)} audio files")
    else:
        merger.run()


if __name__ == "__main__":
    main() 