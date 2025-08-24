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
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/Loganavter/Tkonverter?style=flat-square">
  </a>
  <a href="https://github.com/Loganavter/Tkonverter/issues">
    <img src="https://img.shields.io/github/issues/Loganavter/Tkonverter?style=flat-square">
  </a>
</p>

<p align="center"><strong>An intuitive, open-source tool for advanced image comparison and interaction.</strong></p>

---

## 📸 Screenshot

<div align="center">
  <img src="https://raw.githubusercontent.com/Loganavter/media_archive/1.5.2/Tkonverter/screenshots/screenshot_2.png" width="24%">
  <img src="https://raw.githubusercontent.com/Loganavter/media_archive/1.5.2/Tkonverter/screenshots/screenshot_1.png" width="50%">
  <img src="https://raw.githubusercontent.com/Loganavter/media_archive/1.5.2/Tkonverter/screenshots/screenshot_3.png" width="24%">
</div>

---

## 📖 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Installation](#installation)
- [Usage](#usage)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Development Story](#development-story)
- [License](#license)

---

## 🧩 Overview <a name="overview"></a>

Tkonverter is a free and open-source desktop application designed to convert large Telegram JSON exports into a clean `.txt` format.

The project was initially created to preprocess chat data for use with Large Language Models (LLMs) like Gemini. Its features are centered around the need to manage LLM context windows effectively—either by compressing information (e.g., shortening quotes, truncating names) to save tokens, or by enriching it (e.g., including reactions, polls, Markdown) for higher-quality analysis.

While its primary goal is LLM pre-processing, it is a versatile tool that may be useful for any chat archiving or analysis needs.

---

## 🚀 Key Features <a name="key-features"></a>

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

---

## 🛠️ Installation <a name="installation"></a>

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

## 🧪 Usage <a name="usage"></a>

1.  **Launch** the application: `./launcher.sh run`.
2.  **Drag and drop** your `result.json` file (from a Telegram export) into the application window.
3.  **Configure** the formatting options on the left panel.
4.  **(Optional)** Click **"Recalculate"** to analyze tokens and open the chart for visualization.
5.  **Click** **"Save to file..."** to export the result as a `.txt` file.

---

## 🗺️ Roadmap <a name="roadmap"></a>

The core application is complete and stable. The primary focus now is on making it easily accessible to users. Creation of installers for **Windows** and packages for **Linux (AUR, Flatpak)** is the next major milestone.

---

## 🤝 Contributing <a name="contributing"></a>

This project is in its early stages, so all contributions are highly welcome! Feel free to create [Issues](https://github.com/[YourUsername]/Tkonverter/issues) with bug reports or feature suggestions, and submit [Pull Requests](https://github.com/[YourUsername]/Tkonverter/pulls).

---

## 📄 License <a name="license"></a>

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## 🧠 Development Story <a name="development-story"></a>
<details>
<summary>Show Development Story</summary>
This project was born out of a personal need: to convert Telegram chats into a text format for analysis with AI models. What started as a simple script was transformed into a full-featured GUI application in just one week.

Mid-late August 2025:
The initial development was conducted entirely with Google's Gemini. We started with the intention of building the application on a Model-View-Presenter (MVP) architecture. However, as development progressed rapidly, I failed to strictly enforce the pattern. We quickly turned the "Model-View-Presenter" into a "Minimum-Viable-Product" with spaghetti code. I realized this about 80% of the way through (on day 4 or 5) when I started fighting race conditions that made adding the final features impossible.

A full-scale refactoring was necessary. Gemini analyzed the entire project context and proposed a solid, high-level plan for rebuilding it. The plan was then executed using CursorAI with the Sonnet 4 Thinking model. In a single night, about 80% of the application was refactored into a clean, dependency-injected MVP architecture.

For the final 20%—plus a few features adapted from my previous project, Improve-ImgSLI—I returned to Gemini. While Sonnet 4 is brilliant for executing large, well-defined tasks almost autonomously, it's less cost-effective for the meticulous process of debugging subtle issues. The final 2-3 days were an exhausting but necessary process of chasing down very elusive, often single-line bugs hidden within the new, clean architecture. It was a tedious process of analyzing loggers to find the root cause.

Ultimately, the application was ready after about a week. This process also resulted in the creation of a reusable Fluent Design UI toolkit, which will significantly speed up future projects. Furthermore, it was a valuable experience in integrating AI components into desktop software. Now, only distribution remains.
</details>

---

## ⭐ Star History

![Star History Chart](https://api.star-history.com/svg?repos=Loganavter/Tkonverter&type=Timeline)
