# Install Tkonverter

This document provides installation methods for end users and a minimal "run from source" setup. For developer-oriented packaging/build instructions, see [CONTRIBUTING.md](../CONTRIBUTING.md).

## Quick install (recommended)

### Current Status

Tkonverter is currently distributed primarily through source code installation. This is due to the complexity of managing AI dependencies (Hugging Face models) and the need for dynamic model downloads that occur during runtime.

### Future Packaging Plans

We are working on packaging solutions for easier distribution:
- **Windows**: PyInstaller + Inno Setup installer (planned)
- **Linux (AUR)**: Arch Linux package for AUR (planned)
- **Linux (Flatpak)**: Flathub package (planned)
- **macOS**: Native macOS application bundle (planned)

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
- Installs dependencies (including AI libraries like transformers, huggingface_hub)
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
# CLI launcher
./tkonverter-cli.sh --help

# Convert chat export
./tkonverter-cli.sh convert -i result.json -o output.txt

# Analyze statistics
./tkonverter-cli.sh analyze -i result.json --chars-only

# Show file information
./tkonverter-cli.sh info -i result.json --detailed
```

The CLI uses the same virtual environment as the GUI application.

Manual venv (optional):
```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
# .\venv\Scripts\activate      # Windows PowerShell
pip install -r requirements.txt
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

## Troubleshooting

- Blank window or crashes:
  - Ensure your GPU drivers are up-to-date.
  - Try running with logging enabled: `./launcher.sh enable-logging && ./launcher.sh run`.
- Missing fonts/icons:
  - Verify that `src/resources/` assets are available and not removed.
- AI model download issues:
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
