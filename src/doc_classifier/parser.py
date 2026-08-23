from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SUPPORTED_TEXT = {".pdf", ".docx", ".doc", ".txt"}
SUPPORTED_IMAGE = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
SUPPORTED_OFFICE = {".xlsx", ".csv", ".ods", ".odt"}
MAX_CHARS = 2000

_TESSERACT_PATHS = [
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
]


def _configure_tesseract() -> bool:
    """Locate tesseract.exe and wire it into pytesseract (Windows autodetect)."""
    try:
        import pytesseract
    except ImportError:
        logger.warning("pytesseract not installed")
        return False

    current = pytesseract.pytesseract.tesseract_cmd
    if current not in ("tesseract", ""):
        return True

    found = shutil.which("tesseract")
    if not found:
        found = next((str(p) for p in _TESSERACT_PATHS if p.exists()), None)
    if found:
        pytesseract.pytesseract.tesseract_cmd = found
        logger.info("Using tesseract at %s", found)
        return True

    logger.warning(
        "tesseract executable not found in PATH or %s", ", ".join(str(p) for p in _TESSERACT_PATHS)
    )
    return False


def parse_pdf(file_path: Path) -> str:
    import pdfplumber

    text_parts: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages[:5]:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
            if sum(len(t) for t in text_parts) >= MAX_CHARS:
                break

    combined = "\n".join(text_parts)
    if not combined.strip():
        return _ocr_pdf_fallback(file_path)
    return combined[:MAX_CHARS]


def _render_pdf_pages(file_path: Path, max_pages: int = 3):
    """Render PDF pages to PIL images using pdf2image (poppler) or pdfplumber fallback."""
    try:
        import pdf2image

        return pdf2image.convert_from_path(
            str(file_path), first_page=1, last_page=max_pages
        )
    except Exception as exc:
        logger.info("pdf2image unavailable (%s) – using pdfplumber renderer", exc)

    import pdfplumber

    with pdfplumber.open(file_path) as pdf:
        return [page.to_image().original for page in pdf.pages[:max_pages]]


def _ocr_pdf_fallback(file_path: Path) -> str:
    if not _configure_tesseract():
        logger.warning("Tesseract not configured – skipping OCR fallback for %s", file_path)
        return ""
    try:
        import pytesseract

        images = _render_pdf_pages(file_path)
        text_parts = [pytesseract.image_to_string(img) for img in images]
        return "\n".join(text_parts)[:MAX_CHARS]
    except Exception as exc:
        logger.warning("OCR fallback failed for %s: %s", file_path, exc)
        return ""


def parse_docx(file_path: Path) -> str:
    import docx

    doc = docx.Document(str(file_path))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return text[:MAX_CHARS]


def parse_txt(file_path: Path) -> str:
    encodings = ["utf-8", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            return file_path.read_text(encoding=enc)[:MAX_CHARS]
        except (UnicodeDecodeError, LookupError):
            continue
    return ""


def parse_csv(file_path: Path) -> str:
    import csv

    text_parts: list[str] = []
    with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            text_parts.append(", ".join(cell for cell in row if cell.strip()))
            if sum(len(t) for t in text_parts) >= MAX_CHARS:
                break
    return "\n".join(text_parts)[:MAX_CHARS]


def parse_xlsx(file_path: Path) -> str:
    import openpyxl

    wb = openpyxl.load_workbook(str(file_path), read_only=True, data_only=True)
    text_parts: list[str] = []
    try:
        for sheet in wb.worksheets[:3]:
            text_parts.append(f"[Sheet: {sheet.title}]")
            for row in sheet.iter_rows(max_row=50, values_only=True):
                line = ", ".join(str(c) for c in row if c is not None and str(c).strip())
                if line:
                    text_parts.append(line)
                if sum(len(t) for t in text_parts) >= MAX_CHARS:
                    break
            if sum(len(t) for t in text_parts) >= MAX_CHARS:
                break
    finally:
        wb.close()
    return "\n".join(text_parts)[:MAX_CHARS]


def parse_odt(file_path: Path) -> str:
    from odf import opendocument, teletype

    doc = opendocument.load(str(file_path))
    parts: list[str] = []
    for element in doc.text.childNodes:
        try:
            content = teletype.extractText(element)
        except Exception:
            continue
        if content.strip():
            parts.append(content.strip())
    return "\n".join(parts)[:MAX_CHARS]


def parse_ods(file_path: Path) -> str:
    from odf import opendocument, teletype
    from odf.table import TableCell, TableRow

    doc = opendocument.load(str(file_path))
    text_parts: list[str] = []
    rows = doc.spreadsheet.getElementsByType(TableRow)
    for row in rows[:100]:
        cells = row.getElementsByType(TableCell)
        values: list[str] = []
        for cell in cells:
            repeat_raw = cell.getAttribute("numbercolumnsrepeated")
            try:
                repeat = min(int(repeat_raw or 1), 20)
            except (TypeError, ValueError):
                repeat = 1
            value = teletype.extractText(cell).strip()
            if value:
                values.extend([value] * repeat)
        line = ", ".join(values)
        if line:
            text_parts.append(line)
        if sum(len(t) for t in text_parts) >= MAX_CHARS:
            break
    return "\n".join(text_parts)[:MAX_CHARS]


def parse_office(file_path: Path) -> str:
    ext = file_path.suffix.lower()
    if ext == ".csv":
        return parse_csv(file_path)
    if ext == ".xlsx":
        return parse_xlsx(file_path)
    if ext == ".ods":
        return parse_ods(file_path)
    if ext == ".odt":
        return parse_odt(file_path)
    raise ValueError(f"Unsupported office extension: {ext}")


def parse_image(file_path: Path) -> str:
    if not _configure_tesseract():
        logger.warning("Tesseract not configured – cannot OCR %s", file_path)
        return ""
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(file_path)
        text = pytesseract.image_to_string(img)
        return text.strip()[:MAX_CHARS]
    except ImportError:
        logger.warning("pytesseract/Pillow not installed – cannot OCR %s", file_path)
        return ""
    except Exception as exc:
        logger.warning("OCR failed for %s: %s", file_path, exc)
        return ""


def extract_text(file_path: str | Path) -> Optional[str]:
    path = Path(file_path)
    if not path.exists():
        logger.error("File not found: %s", path)
        return None

    ext = path.suffix.lower()
    text = ""

    try:
        if ext == ".pdf":
            text = parse_pdf(path)
        elif ext in (".docx", ".doc"):
            text = parse_docx(path)
        elif ext == ".txt":
            text = parse_txt(path)
        elif ext in SUPPORTED_OFFICE:
            text = parse_office(path)
        elif ext in SUPPORTED_IMAGE:
            text = parse_image(path)
        else:
            logger.warning("Unsupported file type: %s", ext)
            return None
    except Exception as exc:
        logger.error("Error parsing %s: %s", path, exc)
        return None

    if not text or not text.strip():
        logger.warning("No text extracted from %s", path)
        return None

    return text.strip()


def get_supported_extensions() -> set[str]:
    return SUPPORTED_TEXT | SUPPORTED_IMAGE | SUPPORTED_OFFICE
