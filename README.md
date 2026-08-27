# doc-classifier-cli

A Privacy-First, Local-AI Powered CLI Tool & Web UI for Smart Document Organization.

## Features

- **Privacy-First:** 100% offline — everything runs locally (Ollama + Tesseract)
- **Two Classification Modes:**
  - `--model` flag → AI reads document content, categorizes & renames by context
  - Default (no flag) → instant keyword/extension-based sorting (0 RAM, <0.1s/file)
- **AI Mode:** Supports any Ollama model (`qwen2.5:1.5b` default, 1.5 GB RAM)
- **Keyword Fallback:** When AI fails, auto-falls back to rule-based mode. Use `--no-fallback` to skip instead.
- **Smart OCR:** Scanned PDFs & images are OCR'd via Tesseract. Low-confidence OCR falls back to original filename.
- **Full Office Support:** `.pdf`, `.docx`, `.xlsx`, `.csv`, `.ods`, `.odt`, `.pptx`, `.ppt`, `.txt`, `.tsv`
- **Safe Operations:** Dry-run mode (`--dry-run`) and full undo support (`dclassify undo --all`)
- **Scanner Module:** Analyze a folder dataset with `dclassify scan`, export JSON/CSV reports
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
2. Double-click **`dclassify.bat`** (one time only) - sets up Python env,
   installs dependencies, then launches the guided setup

## Quick Start

### Keyword Mode (default, instant — 0 AI RAM)

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

### AI Mode (content-aware — requires Ollama)

```bash
# AI classification of a folder
dclassify classify ./documents/ --model ollama/qwen2.5:1.5b

# AI only — skip file if AI fails (no keyword fallback)
dclassify classify ./documents/ --model ollama/llama3:8b --no-fallback

# Single file with AI
dclassify classify report.pdf --model ollama/qwen2.5:1.5b
```

### Scan Mode

```bash
# Scan a folder and show distribution stats
dclassify scan ./documents/

# Export report to JSON/CSV
dclassify scan ./documents/ --output-report report.json --output-csv report.csv
```

### Web UI

```bash
streamlit run src/doc_classifier/web.py
```
(or menu option [5], or `Jalankan_Web_UI.bat`)

## Requirements

| Component | Required? | Notes |
| --- | --- | --- |
| Python 3.10+ | Yes | Auto-checked by `.bat` script |
| [Ollama](https://ollama.com/download) | For AI mode | `ollama pull qwen2.5:1.5b` (~986 MB) for default light model |
| Tesseract OCR | Optional | For scanned PDF/images ([UB-Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki)) |

No Ollama? The tool works great in keyword mode — instant, 0 RAM. AI is optional.

## Configuration

Config resolution order:

1. `--config/-c` flag
2. `./config.yaml` (current folder - used by the .bat shortcuts)
3. `%USERPROFILE%\.doc-classifier\config.yaml` (global default for pip installs)

See [`config.example.yaml`](config.example.yaml) for all options: taxonomy,
AI model, keyword fallback, and file naming rules.

## License

MIT
