# AGENTS.md

## Project Overview
Craig Audio Merger - Python CLI tool to merge Craig Discord recording audio files using FFmpeg.

## Build & Run Commands
- **Run**: `python audio_merger.py`
- **Dry run**: `python audio_merger.py --dry-run`
- **Verbose**: `python audio_merger.py -v`
- No tests or linting configured in this project.

## Code Style Guidelines
- **Python version**: 3.8+
- **Imports**: Standard library only; group by stdlib → pathlib. Use `from typing import` for type hints.
- **Types**: Use type hints on all function signatures (return types and parameters).
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_CASE` for constants.
- **Docstrings**: Triple-quoted one-line docstrings for all public methods.
- **Error handling**: Use try/except with specific exceptions; log errors via `self._log(msg, "error")`.
- **Logging**: Use callback pattern (`_log`, `_update_status`, `_update_progress`) for UI integration.
- **Line length**: ~100 chars max, break long function calls across lines.
- **Regex patterns**: Compile patterns as class attributes when reused.
