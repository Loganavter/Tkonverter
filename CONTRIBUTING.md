# Contributing Guide

Thank you for your interest in contributing to Tkonverter! This guide helps you set up a development environment, understand the repository layout, and build distributables.

If you are a user who just wants to install and use the app, please see:
- docs/INSTALL: docs/INSTALL.md
- In-app Help (recommended): src/resources/help/en/
- Russian Help: src/resources/help/ru/

## Quick start (development)

Prerequisites:
- Python 3.10+ recommended
- Git
- On Linux/macOS: bash shell for launcher scripts
- On Windows for packaging: Inno Setup (optional, for installer build)

Clone and run:
```bash
git clone https://github.com/Loganavter/Tkonverter.git
cd Tkonverter
chmod +x launcher.sh
./launcher.sh run
```

The launcher script manages a virtual environment, installs dependencies, and runs the app. Explore additional commands:
```bash
./launcher.sh --help
```
Common actions:
- Recreate venv from scratch: `./launcher.sh recreate`
- Delete venv: `./launcher.sh delete`
- Enable extended logging: `./launcher.sh enable-logging`

Tip: Prefer updating the in-app Help when you add features; the README links to those docs.

## Repository structure (high level)

- src/core: core application logic (state, settings, analysis, conversion, parsing, domain models)
- src/presenters: MVP pattern presenters (main, analysis, calendar, config, file, workers)
- src/ui: Qt UI, dialogs, main window, widgets, managers
- src/resources: application assets (icons, styles, fonts) and user Help in multiple languages
- src/shared_toolkit: shared library reused across projects (widgets, managers, utils, fonts)
- launcher.sh: CLI helper to manage venv and run tasks

Useful entry points:
- App main: src/__main__.py
- UI main window: src/ui/tkonverter_main_window.py
- Main presenter: src/presenters/main_presenter.py
- Settings: src/core/settings.py
- Conversion: src/core/conversion/main_converter.py
- Analysis: src/core/analysis/tree_analyzer.py
- Help Index (EN): src/resources/help/en/introduction.md

## Architectural notes

- Pattern: MVP (Model-View-Presenter). Keep UI (Qt widgets), presenter logic, and core state/services decoupled.
- Dependency injection: Use the DI container in src/core/dependency_injection.py for service management.
- Tree-based analysis: The analysis system uses a tree structure for efficient processing of chat data over time.
- Logging: use the standard logging system (src/shared_toolkit/core/logging.py). Avoid print statements.
- State: persist window geometry and selected options across sessions (src/presenters/app_state.py, src/core/settings.py).
- Shared components: consider using/adding to src/shared_toolkit for reusable UI or utilities across projects.

## Coding guidelines

- Python 3.10+ syntax; prefer type hints where practical.
- Keep modules focused; avoid creating new "god" modules.
- UI strings should support translations when visible to users.
- Follow existing naming and folder conventions.
- Keep public APIs of presenters/services minimal and explicit.

### Commit messages

- Prefer Conventional Commits (optional but encouraged):
  - feat: new user-facing feature
  - fix: bug fix
  - refactor: code restructure without feature change
  - docs: documentation-only change
  - perf: performance improvements
  - build/chore: packaging, CI, tooling
  - revert: revert a previous commit

### Opening issues and PRs

- Before large changes, open an Issue to discuss approach.
- Keep PRs focused and reasonably small.
- Include a short summary of the change and any user-facing impacts.
- Update in-app Help files under src/resources/help/... when appropriate.

## Running from source (minimal)

Linux/macOS:
```bash
chmod +x launcher.sh
./launcher.sh run
```

Windows (PowerShell or bash via Git Bash):
```powershell
git clone https://github.com/Loganavter/Tkonverter.git
cd Tkonverter
bash launcher.sh run
```

If you prefer manual venv management:
```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
# .\venv\Scripts\activate      # Windows PowerShell
pip install -r requirements.txt
python -m src
```

## Building packages

### Future packaging plans

Currently, Tkonverter is distributed primarily through source code installation via the launcher script. This is due to the complexity of managing AI dependencies (Hugging Face models) and the need for dynamic model downloads.

Future packaging options being considered:
- **Windows**: PyInstaller + Inno Setup installer
- **Linux (AUR)**: Arch Linux package for AUR
- **Linux (Flatpak)**: Flathub package
- **macOS**: Native macOS application bundle

Contributions for packaging solutions are welcome! The main challenge is handling the dynamic installation of AI models and dependencies.

## Documentation and translations

- In-app Help (EN): src/resources/help/en/
- In-app Help (RU): src/resources/help/ru/
- Other languages (e.g., zh, pt_BR) live under src/resources/help/

When you add or modify features:
- Update or add the corresponding topic in Help (e.g., conversion, analysis, export).
- Keep README minimal; link to Help for details.

## License

This project is licensed under the MIT License. See:
- LICENSE.txt
