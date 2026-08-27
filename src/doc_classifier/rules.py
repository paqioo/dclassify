from __future__ import annotations

import json
import logging
import re
import shutil
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

DOCUMENT_EXTENSIONS = {".pdf", ".txt", ".docx", ".doc", ".ppt", ".pptx", ".pot"}
SPREADSHEET_EXTENSIONS = {".xls", ".xlsx", ".csv", ".tsv", ".ods", ".xlb"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".jpe", ".png", ".bmp", ".tiff", ".gif"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".wma", ".ogg", ".au", ".mp2", ".mid", ".ram", ".rm"}

DEFAULT_TAXONOMY: dict[str, dict] = {
    "Documents": {"keywords": [], "folder": "Documents"},
    "Spreadsheets": {"keywords": [], "folder": "Spreadsheets"},
    "Images": {"keywords": [], "folder": "Images"},
    "Audio": {"keywords": [], "folder": "Audio"},
}

URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
FONT_NAMES = {"arial", "calibri", "times new roman", "verdana", "tahoma", "century gothic",
              "garamond", "gill sans", "zapfhumnst", "courier", "helvetica", "symbol"}


def find_config_file(
    explicit: str | Path | None = None,
    cwd: Path | None = None,
    home: Path | None = None,
) -> Optional[Path]:
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


def classify_by_extension(
    file_path: str | Path,
    taxonomy: dict[str, TaxonomyEntry],
) -> str:
    ext = Path(file_path).suffix.lower()

    if ext in DOCUMENT_EXTENSIONS:
        return "Documents"
    elif ext in SPREADSHEET_EXTENSIONS:
        return "Spreadsheets"
    elif ext in IMAGE_EXTENSIONS:
        return "Images"
    elif ext in AUDIO_EXTENSIONS:
        return "Audio"

    for name in taxonomy:
        return name
    return "Documents"


def _is_boilerplate_line(text: str) -> bool:
    lower = text.lower()
    if "online service" in lower and "e-mail" in lower:
        return True
    if "http" in lower and ("e-mail" in lower or "email" in lower):
        return True
    if "federal register" in lower and "vol" in lower:
        return True
    return False


def _is_readable_title(text: str) -> bool:
    if not text or len(text) < 4:
        return False
    url_count = len(URL_PATTERN.findall(text))
    if url_count > 0:
        return False
    non_ascii = sum(1 for c in text if ord(c) > 127)
    if non_ascii > len(text) * 0.3:
        return False
    font_hits = sum(1 for f in FONT_NAMES if f in text.lower())
    if font_hits > 0:
        return False
    alpha = sum(1 for c in text if c.isalpha())
    if len(text) > 0 and alpha / len(text) < 0.4:
        return False
    return True


def generate_title_from_text(
    text: str | None,
    original_name: str,
) -> str:
    stem = Path(original_name).stem
    clean_stem = sanitize_filename(stem, max_length=120)

    if not text:
        return clean_stem

    text = URL_PATTERN.sub("", text)

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    lines = [line for line in lines if len(line) > 15]
    lines = [line for line in lines if not _is_boilerplate_line(line)]

    for line in lines:
        words = line.split()[:8]
        candidate = " ".join(words)
        if _is_readable_title(candidate):
            return sanitize_filename(candidate, max_length=120)

    if lines:
        longest = max(lines, key=len)
        words = longest.split()[:8]
        candidate = " ".join(words)
        if _is_readable_title(candidate):
            return sanitize_filename(candidate, max_length=120)

    return clean_stem


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


def sanitize_filename(name: str, max_length: int = 255) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = re.sub(r"\s+", "_", name.strip())
    name = re.sub(r"_+", "_", name)
    name = name.strip("._")
    if len(name) > max_length:
        name = name[:max_length]
    return name


def generate_target_filename(
    title: str,
    original_ext: str,
    naming_config: FileNamingConfig,
) -> str:
    safe_title = sanitize_filename(title, max_length=200)
    if not safe_title or not re.search(r"[a-zA-Z0-9]", safe_title):
        safe_title = "document"

    filename = naming_config.pattern.format(title=safe_title)

    if naming_config.sanitize_chars:
        filename = sanitize_filename(filename, max_length=naming_config.max_length)

    return f"{filename}{original_ext}"


def resolve_target_folder(
    category: str,
    taxonomy: dict[str, TaxonomyEntry],
    base_dir: str | Path = ".",
) -> Path:
    if category in taxonomy:
        folder_name = taxonomy[category].folder
    else:
        first_key = next(iter(taxonomy), "Documents")
        folder_name = taxonomy[first_key].folder

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

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            raw_list = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return []

    return [FileOperation(**entry) for entry in raw_list]


def save_history(operations: list[FileOperation], history_path: str | Path = HISTORY_FILE) -> None:
    path = Path(history_path)
    data = [op.model_dump() for op in operations]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def apply_classification(
    file_path: str | Path,
    category: str,
    title: str,
    config: Config,
    output_dir: str | Path = ".",
    dry_run: bool = False,
) -> FileOperation:
    file_path = Path(file_path)
    output_dir = Path(output_dir)

    target_folder = resolve_target_folder(category, config.taxonomy, output_dir)
    new_filename = generate_target_filename(
        title, file_path.suffix, config.file_naming
    )
    target_path = unique_path(target_folder / new_filename)

    action = "noop" if dry_run else "move"

    classification = ClassificationResult(
        title=title,
        document_type="other",
        main_category=category,
        document_date=None,
        suggested_filename=title,
        confidence=1.0,
        summary=f"Filed under {category}",
    )

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
