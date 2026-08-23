# doc-classifier-cli

A Privacy-First, Local-AI Powered CLI Tool & Web UI for Smart Document Organization.

## Features

- **Privacy-First:** 100% offline classification using local LLM (Ollama / Llama 3 / Qwen)
- **Context-Aware:** Classifies documents by content, not just file name or extension
- **Keyword Fallback:** Still organizes files even without AI (rule-based mode)
- **Safe Operations:** Dry-run mode and full undo support
- **Dual Interface:** CLI (`dclassify` + rich interactive menu) and Web UI (Streamlit)

## Installation

### Path A - pip / PowerShell / CMD users

Install directly from GitHub (no PyPI needed):

```powershell
pip install git+https://github.com/paqioo/dclassify.git
```

Then run from any folder:

```text
dclassify
```

First run includes a guided setup: it asks your source/target folders,
checks Ollama + model + Tesseract, and offers one-keypress fixes
(auto-install via winget, auto model pull). Nothing is downloaded
without your confirmation.

### Path B - Download repo / ZIP (beginner-friendly)

1. Download & extract this repository
2. Double-click **`Setup_Awal.bat`** (one time only) - it sets up Python env,
   installs dependencies, then launches the guided setup
3. Daily use:
   - **`Rapikan_Downloads.bat`** - auto-organize your source folder
   - **`Jalankan_Web_UI.bat`** - open the Web UI in browser

## Quick Start

### CLI

```bash
# Interactive menu (default command)
dclassify

# Classify a single file
dclassify classify document.pdf

# Classify all files in a directory
dclassify classify ./documents/ --recursive

# Dry-run (preview without moving files)
dclassify classify ./documents/ --dry-run

# Undo last operation
dclassify undo

# Check AI model connection
dclassify check
```

### Web UI

```bash
streamlit run src/doc_classifier/web.py
```
(or menu option [5], or `Jalankan_Web_UI.bat`)

## Requirements

| Component | Required? | Notes |
| --- | --- | --- |
| Python 3.10+ | Yes | Auto-checked by `Setup_Awal.bat` |
| [Ollama](https://ollama.com/download) | Yes (for AI mode) | `ollama pull llama3:8b` (~4.7 GB, once) |
| Tesseract OCR | Optional | Only for scanned PDF/images ([UB-Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki)) |

No Ollama yet? The tool still works using keyword-based classification
(`fallback_keywords: true` in config).

## Configuration

Config resolution order:

1. `--config/-c` flag
2. `./config.yaml` (current folder - used by the .bat shortcuts)
3. `%USERPROFILE%\.doc-classifier\config.yaml` (global default for pip installs)

See [`config.example.yaml`](config.example.yaml) for all options: taxonomy,
AI model, fallback mode, and file naming rules.

## License

MIT
