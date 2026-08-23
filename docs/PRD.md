# Product Requirement Document (PRD)

## Project Name: `doc-classifier-cli`

**Tagline:** *A Privacy-First, Local-AI Powered CLI Tool & Web UI for Smart Document Organization.*

**License:** MIT License

**Target Audience:** Developer, Peneliti, Pekerja Kantor, dan Tim ICT yang mengelola repositori dokumen digital secara mandiri.

---

## 1. Overview & Problem Statement

### 1.1 Problem Statement

Penataan dokumen di lingkungan digital kantor maupun personal sering kali menjadi masalah kronis. Nama file seperti `Scan_001.pdf`, `Draft_Fix_Final.pdf`, atau `dmaiwjdiwj.pdf` membuat pencarian informasi menjadi sangat lambat. Di sisi lain, menggunakan layanan cloud AI publik untuk mengklasifikasikan dokumen berisiko memunculkan isu kebocoran data sensitif (*data privacy & compliance*).

### 1.2 Proposed Solution

`doc-classifier-cli` adalah perkakas open-source yang secara otomatis membaca isi/konteks dokumen lokal, mengekstrak metadata menggunakan AI/LLM, lalu menata file ke dalam struktur folder yang rapi. Sistem ini dirancang berprinsip **Local-First**, memastikan seluruh pemrosesan data terjadi di komputer pengguna tanpa ada data yang terkirim ke internet.

---

## 2. Goals & Key Objectives

1. **Privacy-First Operations:** Memungkinkan klasifikasi dokumen secara 100% *offline* menggunakan LLM lokal (Ollama / Llama 3 / Qwen).
2. **Context-Aware Semantic Sorting:** Mengkategorikan file berdasarkan isi konten/makna teks, bukan sekadar ekstensi atau nama file.
3. **Developer & End-User Friendly:** Menyediakan antarmuka CLI visual yang informatif serta alternatif Web UI sederhana.
4. **Safety & Auditability:** Menyediakan fitur pemulihan (*undo*) dan mode simulasi (*dry-run*) untuk mencegah kehilangan atau salah pindah file.

---

## 3. User Personas

| Persona | Problem / Need | How `doc-classifier-cli` Helps |
| --- | --- | --- |
| **Pekerja Kantor / ICT Staff** | Penataan arsip SOP/Laporan di drive bersama sering berantakan. | Mengotomatisasi penataan taksonomi dokumen dengan cepat dan aman. |
| **Peneliti / Akademisi** | Menimbun ratusan paper penelitian dengan nama file acak di folder `Downloads`. | Mengubah nama file menjadi terstruktur (Tahun_Judul) dan mengelompokkannya per subjek. |
| **Privacy-Conscious User** | Ingin memanfaatkan AI untuk produktivitas tapi takut data internal bocor ke API Cloud. | Memungkinkan pemrosesan AI lokal tanpa koneksi internet. |

---

## 4. Functional Requirements

### 4.1 Core Features & Modules

#### F-01: Document Parsing & Text Extraction

* Membaca teks dari file `.pdf` (text-based), `.docx`, dan `.txt`.
* *Fallback Support:* Mendukung ekstrak teks berbasis OCR untuk PDF hasil scan/gambar (`.jpg`, `.png`).
* Mengekstrak 1.000-2.000 karakter awal untuk efisiensi analisis token AI.

#### F-02: Local-First AI Classification Engine

* Terintegrasi secara *default* dengan **Ollama** (`llama3:8b` / `qwen2.5`).
* Mengembalikan output berstruktur JSON yang mencakup: `title`, `document_type`, `main_category`, `document_date`, dan `suggested_filename`.
* *Cloud Fallback Option:* Menyediakan opsi opsional untuk memakai API External (OpenAI GPT-4o-mini / Gemini Flash) jika dikonfigurasi pengguna.

#### F-03: Rule Engine & Custom Taxonomy

* Membaca file konfigurasi `config.yaml` untuk menentukan folder target sesuai kategori.
* Penanganan konflik nama file (*auto-incrementing* jika file dengan nama serupa sudah ada).
* Pembersihan karakter ilegal pada nama file baru secara otomatis.

#### F-04: User Interfaces (CLI & Web)

* **CLI Interface (`rich` + `typer`):** Menampilkan *progress bar*, indikator status, dan tabel hasil ringkasan.
* **Web UI (Streamlit):** Antarmuka opsional berbasis *drag-and-drop* file dengan tombol konfirmasi satu-klik.

#### F-05: Safety & Recovery

* **Dry-Run Mode (`--dry-run`):** Menampilkan simulasi perubahan tanpa mengubah struktur direktori.
* **Undo System (`doc-classify undo`):** Mencatat log riwayat transaksi di `.doc_classifier_history.json` untuk mengembalikan file ke posisi awal jika terjadi kesalahan.

---

## 5. Non-Functional Requirements

1. **Security & Privacy:**
   * Tidak ada telemetri bawaan.
   * Parameter `--local-only` secara ketat memblokir outbound network request.

2. **Performance:**
   * Pemrosesan teks per dokumen di bawah 2 detik (pada Ollama dengan GPU terintegrasi/Dedicated).

3. **Compatibility:**
   * Lintas platform: Windows 10/11, macOS, dan Linux.
   * Kompatibel dengan Python versi 3.10 ke atas.

---

## 6. Technical Architecture & Tech Stack

```
           +---------------------------------------+
           |        CLI / Web UI (Streamlit)        |
           +---------------------------------------+
                               |
                               v
           +---------------------------------------+
           |             Parser Module             |
           |      (pdfplumber / python-docx)       |
           +---------------------------------------+
                               |
                               v
           +---------------------------------------+
           |       AI Classifier (LiteLLM)         |
           |   (Ollama Local  OR  Cloud API)       |
           +---------------------------------------+
                               |
                               v
           +---------------------------------------+
           |      Decision & File Ops Engine       |
           |    (shutil / config.yaml / JSON Log)   |
           +---------------------------------------+
```

* **CLI Framework:** `typer`, `rich`
* **Parsing:** `pdfplumber`, `python-docx`, `pytesseract`
* **AI Abstraction:** `litellm` (Mendukung Ollama, OpenAI, Gemini tanpa mengubah skrip utama)
* **Validation:** `pydantic`
* **Packaging:** `setuptools` (Siap di-publish ke PyPI)

---

## 7. Success Metrics (KPIs for GitHub Open-Source)

1. **User Safety:** 0 laporan kecelakaan file terhapus (*zero-data-loss execution*).
2. **GitHub Engagement:** Mencapai 50+ Stars dalam 3 bulan pertama.
3. **Installability:** Berhasil di-install via `pip install doc-classifier-cli` tanpa isu pembatasan dependensi.

---

## 8. Implementation Status

| Module | File | Status |
| --- | --- | --- |
| Pydantic Models | `src/doc_classifier/models.py` | Done |
| Document Parser | `src/doc_classifier/parser.py` | Done |
| AI Classification | `src/doc_classifier/ai.py` | Done |
| Rule Engine & File Ops | `src/doc_classifier/rules.py` | Done |
| CLI Interface | `src/doc_classifier/cli.py` | Done |
| Web UI (Streamlit) | `src/doc_classifier/web.py` | Done |
| Unit Tests | `tests/test_core.py` | Done |
| Config | `config.yaml` | Done |
| Package Config | `pyproject.toml` | Done |
