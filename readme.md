<p align="center">
  <img src="https://raw.githubusercontent.com/Loganavter/media_archive/1.5.1/Tkonverter/icons/logo.png" alt="Logo" width="100">
</p>

<p align="center">
  <strong>An open-source desktop tool for converting and analyzing exported Telegram chats.</strong>
</p>

<p align="center">
  <a href="https://github.com/Loganavter/Tkonverter/releases/latest">
    <img src="https://img.shields.io/github/v/release/Loganavter/Tkonverter?style=flat-square&label=latest%20release">
  </a>
  <a href="LICENSE.txt">
    <img src="https://img.shields.io/github/license/Loganavter/Tkonverter?style=flat-square">
  </a>
  <a href="https://github.com/Loganavter/Tkonverter/issues">
    <img src="https://img.shields.io/github/issues/Loganavter/Tkonverter?style=flat-square">
  </a>
</p>

<p align="center">
  Read this in other languages:
  <a href="README.ru.md">Русский</a>
</p>

---

## 📸 Preview

<div align="center">
  <img src="https://raw.githubusercontent.com/Loganavter/media_archive/1.5.2/Tkonverter/screenshots/screenshot_2.png" width="24%">
  <img src="https://raw.githubusercontent.com/Loganavter/media_archive/1.5.2/Tkonverter/screenshots/screenshot_1.png" width="50%">
  <img src="https://raw.githubusercontent.com/Loganavter/media_archive/1.5.2/Tkonverter/screenshots/screenshot_3.png" width="24%">
</div>

---

## 🧭 Quick links

- Install & run from source: <a href="docs/INSTALL.md">docs/INSTALL.md</a>
- CLI Documentation: <a href="docs/CLI.md">docs/CLI.md</a>
- Learn the app (Help): <a href="src/resources/help/en/introduction.md">EN Introduction</a> • <a href="src/resources/help/en/">EN All topics</a> • <a href="src/resources/help/ru/">RU Docs</a>
- Contribute: <a href="CONTRIBUTING.md">CONTRIBUTING.md</a>
- More: <a href="HISTORY.md">Development History</a> • <a href="VISION.md">Project Vision</a>

---

## 🧩 Overview

Tkonverter is a free and open-source desktop application designed to convert large Telegram JSON exports into a clean `.txt` format.

The project was initially created to preprocess chat data for use with Large Language Models (LLMs) like Gemini. Its features are centered around the need to manage LLM context windows effectively—either by compressing information (e.g., shortening quotes, truncating names) to save tokens, or by enriching it (e.g., including reactions, polls, Markdown) for higher-quality analysis.

While its primary goal is LLM pre-processing, it is a versatile tool that may be useful for any chat archiving or analysis needs.

---

## 🚀 Key Features

### 🔄 Advanced Conversion & Context Control
- **Flexible Profiles**: Supports group chats, personal conversations, channels, and posts. The app automatically detects the correct profile in most cases.
- **Context Saving Tools**: Reduce token count with options to automatically shorten replied-to message snippets and truncate long usernames.
- **Rich Context Options**: Choose to include detailed information like reactions, poll results, links, and full Markdown formatting for the highest quality input.
- **Fine-Grained Control**: Toggle the visibility of timestamps, service messages, and technical information.

### 📊 Analytics for LLM Pre-processing
- **Token & Character Counting**: Calculate the exact token count (using Hugging Face tokenizers) or character count to understand how formatting choices impact the final data size.
- **Interactive Chart**: Visualize message volume over time with a sunburst chart inspired by KDE Filelight.
- **Data Filtering**: Exclude irrelevant time periods from your export by clicking on chart segments, allowing you to refine the context sent to a model.

### 🤖 Optional AI Integration
- **Hugging Face Support**: For precise, model-specific token analysis.
- **Built-in Installer**: Install required Python libraries (`transformers`, `huggingface_hub`) and download models directly from the UI—no terminal needed.

### 🧑‍💻 User Experience & Tooling
- **Cross-Platform**: Built with Python and PyQt6.
- **Theming**: Supports light and dark modes, with auto-detection of your system's theme.
- **Powerful Launcher**: A `launcher.sh` script simplifies dependency management in a virtual environment, running, and debugging.
- **CLI Interface**: Full-featured command-line interface for automation and script integration.

---

## 🛠 Installation

Currently, the primary installation method is by running from the source code.

### 🐍 From Source (Linux/macOS)
The `launcher.sh` script will automatically create a virtual environment and install all dependencies.
```bash
git clone https://github.com/Loganavter/Tkonverter.git
cd Tkonverter
chmod +x launcher.sh
./launcher.sh run
```
Use `./launcher.sh --help` for a full list of commands (including `recreate`, `delete`, `profile`).

### 🪟 Windows, 🐧 Linux, 🍏 macOS
Installers and distribution packages are planned for the future. Contributions are welcome!

---

## 🧪 Usage

### Graphical Interface
1.  **Launch** the application: `./launcher.sh run`.
2.  **Drag and drop** your `result.json` file (from a Telegram export) into the application window.
3.  **Configure** the formatting options on the left panel.
4.  **(Optional)** Click **"Recalculate"** to analyze tokens and open the chart for visualization.
5.  **Click** **"Save to file..."** to export the result as a `.txt` file.

### Command Line Interface (CLI)
```bash
# Simple conversion
./tkonverter-cli.sh convert -i result.json -o output.txt

# Convert with custom settings
./tkonverter-cli.sh convert -i result.json -o output.txt --profile personal --no-time

# Analyze statistics
./tkonverter-cli.sh analyze -i result.json --chars-only

# Show file information
./tkonverter-cli.sh info -i result.json --detailed

# Get help
./tkonverter-cli.sh --help
./tkonverter-cli.sh convert --help
```

---

## 🤝 Contributing

Contributions are welcome! Please read <a href="CONTRIBUTING.md">CONTRIBUTING.md</a> for development setup, coding guidelines, and packaging notes. Report issues and propose PRs via GitHub.

---

## 📄 License

This project is licensed under the MIT License. See <a href="LICENSE.txt">LICENSE.txt</a> for details.

---

## ⭐ Star History

![Star History Chart](https://api.star-history.com/svg?repos=Loganavter/Tkonverter&type=Timeline)
