# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Unified Annotation Platform backend — a Python/Flask service for recording and annotating UI automation test cases on **TV** (via capture card + ADB/serial) and **Mobile** (via ADB screen mirroring) devices. Test steps are captured as screenshots with metadata, managed in Excel files, and uploaded to Aliyun OSS.

## Running the Application

```bash
python main_app.py          # Starts Flask server on http://localhost:5004
cd frontend && npm run dev   # Frontend dev server (separate repo/directory)
```

No requirements.txt exists. Key third-party dependencies: `flask`, `opencv-python`, `pillow`, `openpyxl`, `oss2`, `requests`.

## Architecture

### Module Structure

Two independent feature modules share a common layer:

- **`tv_annotation/`** — TV recording via capture card (OpenCV VideoCapture) + device control via ADB/serial. Core: `tv_recorder.py` (CaptureCardManager singleton, thread-safe frame capture).
- **`mobile_annotation/`** — Mobile recording via ADB screen capture + touch event analysis. Core: `recorder.py` (MobileRecorder), `action_analyzer.py` (state machine: idle → pressing → analyzing → tap/swipe/drag classification).
- **`common/`** — Shared utilities: `testcase_utils.py` (Excel/CSV test case CRUD), `oss_bucket.py` / `oss_uploader.py` (Aliyun OSS upload), `utils.py` (filename sanitization).

### Route Registration

`main_app.py` is the entry point. Each module exposes a `register_*_routes(app, base_dir)` function (in `tv_annotation/app.py` and `mobile_annotation/app.py`) that registers Flask Blueprints. Modules are independently loadable — if one fails to import, the other still works.

Routes follow factory pattern: `create_tv_config_routes(base_dir)` returns a Blueprint. URL prefix convention: `/api/tv/...` and `/api/mobile/...`.

### Data Storage

No database — all data is file-based:
- **Test cases**: Excel files (`.xlsx`) parsed by `testcase_utils.py`
- **Recorded steps**: Directories of screenshots + JSON metadata
- **Config**: `device_config.json`, `train_data_config.json` (auto-created with defaults)
- **Data root**: `C:/annotation/{tv,mobile}` on Windows, `~/annotation/{tv,mobile}` on Unix

### API Response Convention

```json
{"success": true/false, "message": "...", "data": {...}, "error": "..."}
```

### Key Patterns

- **Singleton**: `CaptureCardManager` for video capture card access
- **Background threads**: Recording runs in separate threads with thread-safe state
- **Atomic file writes**: JSON progress files written to temp then renamed
- **Graceful degradation**: Failed module imports are logged but don't crash the app
- **Logging**: Dual output (console + `log/app.log`) via `TeeOutput`; logs cleared on each restart

## Codebase Language

Comments and UI strings are in Chinese. The project targets Chinese-speaking teams.
