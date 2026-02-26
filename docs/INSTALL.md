# Install Tkonverter

This document provides installation methods for end users and a minimal "run from source" setup. For developer-oriented packaging/build instructions, see [CONTRIBUTING.md](../CONTRIBUTING.md).

## Quick install (recommended)

### Current Status

Tkonverter is currently distributed primarily through source code installation. This is due to the complexity of managing AI dependencies (Hugging Face models) and the need for dynamic model downloads that occur during runtime.

### Packaging

- **Windows**: PyInstaller + Inno Setup installer (planned). The tokenizer will be installable from the app after installation.
- **Linux (AUR)** / **macOS**: Planned.

Contributions for packaging solutions are welcome!

---

## Run from source (current method)

This approach is for users who prefer not to install system-wide packages or want to try the app quickly from the repository.

Prerequisites:
- Python 3.10+ recommended
- Git

Steps:
```bash
git clone https://github.com/Loganavter/Tkonverter.git
cd Tkonverter
chmod +x launcher.sh
./launcher.sh run
```

The launcher:
- Creates/uses a virtual environment
- Installs dependencies from `requirements-gui.txt` (PyQt6, numpy, Pillow, markdown; AI libraries like transformers are installed from the app when needed)
- Runs the application

Helpful commands:
```bash
./launcher.sh --help
./launcher.sh recreate       # recreate venv
./launcher.sh delete         # delete venv
./launcher.sh enable-logging # enable extended logging
```

### Command Line Interface (CLI)
Tkonverter also provides a full-featured CLI for automation and script integration:

```bash
# CLI launcher (uses same venv as GUI when run from repo)
./tkonverter-cli.sh --help

# Convert chat export
./tkonverter-cli.sh convert -i result.json -o output.txt

# Analyze statistics
./tkonverter-cli.sh analyze -i result.json --chars-only

# Show file information
./tkonverter-cli.sh info -i result.json --detailed
```

The CLI uses the same virtual environment as the GUI when you use `./tkonverter-cli.sh` after `./launcher.sh install`.

**CLI-only install (no PyQt, e.g. on a server):**
```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
# .\venv\Scripts\activate      # Windows PowerShell
pip install -r requirements-cli.txt
python -m src.cli --help
```

**Manual venv for GUI (optional):**
```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
# .\venv\Scripts\activate      # Windows PowerShell
pip install -r requirements-gui.txt
# or: pip install -r requirements.txt
python -m src
```

---

## Documentation

In-app Help (recommended):
- English: src/resources/help/en/
- Russian: src/resources/help/ru/

Entry topic (EN): src/resources/help/en/introduction.md

CLI Documentation: [CLI.md](CLI.md)

---

## Configuration and data in `~/.config`

On Linux the application stores settings and per-chat data under `~/.config/Tkonverter/`. (On Windows and macOS the base path may differ; Qt uses the standard platform config location.)

| Path | Description |
|------|-------------|
| **`~/.config/Tkonverter/Tkonverter.conf`** | Main application settings (Qt QSettings): theme, language, debug flag, export directories, and all conversion/UI options (profile, timestamps, reactions, markdown, anonymization on/off, selected preset id, etc.). |
| **`~/.config/Tkonverter/anonymizer_presets/`** | Anonymization presets. Each preset is a JSON file named `<preset_id>.json` (e.g. `default.json`). Contains preset name, link filters, mask formats. Created when you add or edit presets in the Anonymization dialog. |
| **`~/.config/Tkonverter/chat_memory/`** | Per-chat data: disabled dates and day overrides. One JSON file per chat: `<chat_id>.json`, where `chat_id` is the numeric id from the export. Stores `disabled_dates` (list of YYYY-MM-DD) and `day_overrides` (edited text for specific days). Used when you exclude days in the analysis chart or edit day text in the calendar. |

To reset the application to defaults you can remove or rename the `~/.config/Tkonverter` directory (you will lose all saved settings, presets, and per-chat disabled dates/overrides).

---

## Running on Windows

Run the app from the **project root** (the folder containing `src`), not from inside `src`:

```powershell
cd Tkonverter
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements-gui.txt
python -m src
```

Do not run `python src\main.py` or `python src\__main__.py` from the project root; use `python -m src` so that package imports resolve correctly.

---

## Troubleshooting

- **`ModuleNotFoundError: No module named 'shared_toolkit'`**  
  Run the app as a module from the project root: `python -m src`. Ensure the project root (the directory that contains the `src` folder) is the current directory when you run the command.

- Blank window or crashes:
  - Ensure your GPU drivers are up-to-date.
  - Try running with logging enabled: `./launcher.sh enable-logging && ./launcher.sh run`.
- Missing fonts/icons:
  - Verify that `src/resources/` assets are available and not removed.
- AI model / tokenizer issues:
  - Check your internet connection.
  - The app will attempt to download required models on first use.
  - Models are cached locally after download.
- Slow performance with large chat exports:
  - Use the filtering options in the analysis tab to reduce data size.
  - Consider using shorter time periods for analysis.
- Packaging issues (future):
  - See developer packaging notes in [CONTRIBUTING.md](../CONTRIBUTING.md).

---

## License

Tkonverter is MIT-licensed. See:
- LICENSE.txt
