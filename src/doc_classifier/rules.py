from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from .models import (
    ClassificationResult,
    Config,
    FileNamingConfig,
    FileOperation,
    TaxonomyEntry,
)

logger = logging.getLogger(__name__)

HISTORY_FILE = ".doc_classifier_history.json"

GLOBAL_CONFIG_DIR = Path.home() / ".doc-classifier"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.yaml"

DEFAULT_TAXONOMY: dict[str, dict] = {
    "Keuangan": {
        "keywords": ["invoice", "faktur", "kwitansi", "laporan keuangan", "anggaran", "budget"],
        "folder": "01_Keuangan",
    },
    "Surat_Menyurat": {
        "keywords": ["surat", "memo", "nota dinas", "undangan", "pengumuman"],
        "folder": "02_Surat_Menyurat",
    },
    "Laporan": {
        "keywords": ["laporan", "report", "evaluasi", "monitoring", "progress"],
        "folder": "03_Laporan",
    },
    "Kontrak": {
        "keywords": ["kontrak", "perjanjian", "MoU", "agreement", "addendum"],
        "folder": "04_Kontrak",
    },
    "SDM": {
        "keywords": ["CV", "resume", "SK", "absensi", "cuti", "payroll"],
        "folder": "05_SDM",
    },
    "Penelitian": {
        "keywords": ["jurnal", "paper", "skripsi", "tesis", "disertasi", "research"],
        "folder": "06_Penelitian",
    },
    "Teknis": {
        "keywords": ["SOP", "manual", "prosedur", "spesifikasi", "blueprint"],
        "folder": "07_Teknis",
    },
    "Legal": {
        "keywords": ["hukum", "peraturan", "undang-undang", "regulasi", "legal"],
        "folder": "08_Legal",
    },
    "Lainnya": {"keywords": [], "folder": "09_Lainnya"},
}


def find_config_file(
    explicit: str | Path | None = None,
    cwd: Path | None = None,
    home: Path | None = None,
) -> Optional[Path]:
    """Resolve config path: explicit flag -> ./config.yaml -> ~/.doc-classifier/config.yaml."""
    if explicit:
        return Path(explicit)

    base_cwd = cwd or Path.cwd()
    local_candidate = base_cwd / "config.yaml"
    if local_candidate.exists():
        return local_candidate

    base_home = home or Path.home()
    global_candidate = base_home / ".doc-classifier" / "config.yaml"
    if global_candidate.exists():
        return global_candidate

    return None


def load_config(config_path: str | Path = "config.yaml") -> Config:
    path = Path(config_path)
    if not path.exists():
        logger.warning("Config file not found at %s, using defaults", path)
        return Config()

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    return Config(**raw)


def write_default_config(
    target_path: str | Path,
    source_dir: str | None = None,
    output_dir: str | None = None,
) -> Path:
    """Write a complete default config (taxonomy included) to target_path."""
    raw = Config().model_dump()
    raw["taxonomy"] = DEFAULT_TAXONOMY
    if source_dir is not None:
        raw["paths"]["source_dir"] = source_dir
    if output_dir is not None:
        raw["paths"]["output_dir"] = output_dir

    path = Path(target_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False)
    return path


def classify_by_keywords(
    text: str,
    taxonomy: dict[str, TaxonomyEntry],
    original_name: str = "",
) -> ClassificationResult:
    """Rule-based fallback classification using taxonomy keywords (no AI needed)."""
    lower_text = (text or "").lower()
    best_category: str | None = None
    best_hits = 0

    for name, entry in taxonomy.items():
        hits = sum(1 for kw in entry.keywords if kw and kw.lower() in lower_text)
        if hits > best_hits:
            best_hits = hits
            best_category = name

    if best_category is None:
        best_category = "Lainnya" if "Lainnya" in taxonomy else next(iter(taxonomy), "Lainnya")

    stem = sanitize_filename(Path(original_name).stem, max_length=60)
    title = stem or "Untitled Document"

    summary = (
        f"Diklasifikasi via keyword rules ({best_hits} cocok)"
        if best_hits
        else "Tanpa kecocokan keyword; dimasukkan ke Lainnya"
    )

    return ClassificationResult(
        title=title,
        document_type="other",
        main_category=best_category,
        document_date=None,
        suggested_filename=stem or "document",
        confidence=0.3,
        summary=summary,
    )


def save_config_paths(
    source_dir: str | None,
    output_dir: str | None,
    config_path: str | Path = "config.yaml",
) -> Config:
    path = Path(config_path)
    if not path.exists():
        logger.warning("Config file not found at %s, creating new", path)
        raw: dict = {}
    else:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    raw.setdefault("paths", {})
    if source_dir is not None:
        raw["paths"]["source_dir"] = source_dir
    if output_dir is not None:
        raw["paths"]["output_dir"] = output_dir

    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False)

    return Config(**raw)


def sanitize_filename(name: str, max_length: int = 120) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = re.sub(r"\s+", "_", name.strip())
    name = re.sub(r"_+", "_", name)
    name = name.strip("._")
    if len(name) > max_length:
        name = name[:max_length]
    return name


def generate_target_filename(
    classification: ClassificationResult,
    original_ext: str,
    naming_config: FileNamingConfig,
) -> str:
    date_str = classification.document_date or datetime.now().strftime(naming_config.date_format)
    title = sanitize_filename(classification.title, max_length=60)
    if not title or not re.search(r"[a-z0-9]", title, re.IGNORECASE):
        title = sanitize_filename(classification.suggested_filename, max_length=60)
    if not title:
        title = "document"
    doc_type = sanitize_filename(classification.document_type, max_length=20)

    filename = naming_config.pattern.format(
        date=date_str,
        title=title,
        type=doc_type,
    )

    if naming_config.sanitize_chars:
        filename = sanitize_filename(filename, max_length=naming_config.max_length)

    return f"{filename}{original_ext}"


def resolve_target_folder(
    classification: ClassificationResult,
    taxonomy: dict[str, TaxonomyEntry],
    base_dir: str | Path = ".",
) -> Path:
    category = classification.main_category
    if category in taxonomy:
        folder_name = taxonomy[category].folder
    else:
        folder_name = taxonomy.get("Lainnya", TaxonomyEntry(folder="09_Lainnya")).folder

    return Path(base_dir) / folder_name


def unique_path(target: Path) -> Path:
    if not target.exists():
        return target

    stem = target.stem
    ext = target.suffix
    parent = target.parent
    counter = 1

    while True:
        candidate = parent / f"{stem}_{counter}{ext}"
        if not candidate.exists():
            return candidate
        counter += 1


def load_history(history_path: str | Path = HISTORY_FILE) -> list[FileOperation]:
    path = Path(history_path)
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        raw_list = json.load(f)

    return [FileOperation(**entry) for entry in raw_list]


def save_history(operations: list[FileOperation], history_path: str | Path = HISTORY_FILE) -> None:
    path = Path(history_path)
    data = [op.model_dump() for op in operations]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def apply_classification(
    file_path: str | Path,
    classification: ClassificationResult,
    config: Config,
    output_dir: str | Path = ".",
    dry_run: bool = False,
) -> FileOperation:
    file_path = Path(file_path)
    output_dir = Path(output_dir)

    target_folder = resolve_target_folder(classification, config.taxonomy, output_dir)
    new_filename = generate_target_filename(
        classification, file_path.suffix, config.file_naming
    )
    target_path = unique_path(target_folder / new_filename)

    action = "noop" if dry_run else "move"

    operation = FileOperation(
        original_path=str(file_path.resolve()),
        target_path=str(target_path.resolve()),
        action=action,
        classification=classification,
    )

    if not dry_run:
        target_folder.mkdir(parents=True, exist_ok=True)
        shutil.move(str(file_path), str(target_path))
        logger.info("Moved %s -> %s", file_path, target_path)

        history = load_history()
        history.append(operation)
        save_history(history)

    return operation


def undo_last(history_path: str | Path = HISTORY_FILE) -> Optional[FileOperation]:
    history = load_history(history_path)
    if not history:
        logger.warning("No operations to undo")
        return None

    last_op = history.pop()
    if last_op.action == "noop":
        logger.info("Last operation was dry-run, nothing to undo")
        return last_op

    target = Path(last_op.target_path)
    original = Path(last_op.original_path)

    if not target.exists():
        logger.error("Target file no longer exists: %s", target)
        return None

    original.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(target), str(original))
    logger.info("Undo: moved %s -> %s", target, original)

    save_history(history, history_path)
    return last_op


def undo_all(history_path: str | Path = HISTORY_FILE) -> list[FileOperation]:
    undone: list[FileOperation] = []
    while True:
        op = undo_last(history_path)
        if op is None:
            break
        undone.append(op)
    return undone
