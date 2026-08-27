from __future__ import annotations

import csv
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import ClassificationResult, Config
from .parser import extract_text_metadata, get_supported_extensions, is_media_file
from .rules import classify_by_extension, generate_title_from_text

logger = logging.getLogger(__name__)


class FileScanResult:
    def __init__(
        self,
        path: str,
        extension: str,
        classification: Optional[ClassificationResult] = None,
        error: Optional[str] = None,
    ):
        self.path = path
        self.extension = extension
        self.classification = classification
        self.error = error

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "extension": self.extension,
            "classification": (
                self.classification.model_dump() if self.classification else None
            ),
            "error": self.error,
        }


class ScanStats:
    def __init__(self):
        self.total_files = 0
        self.supported_files = 0
        self.classified_files = 0
        self.media_files = 0
        self.by_extension: dict[str, int] = {}
        self.by_category: dict[str, int] = {}
        self.by_document_type: dict[str, int] = {}
        self.avg_confidence = 0.0
        self.total_time = 0.0
        self.by_category_time: dict[str, float] = {}

    def to_dict(self) -> dict:
        return {
            "total_files": self.total_files,
            "supported_files": self.supported_files,
            "classified_files": self.classified_files,
            "media_files": self.media_files,
            "by_extension": self.by_extension,
            "by_category": self.by_category,
            "by_document_type": self.by_document_type,
            "avg_confidence": round(self.avg_confidence, 3),
            "total_time": round(self.total_time, 3),
            "by_category_time": {k: round(v, 3) for k, v in self.by_category_time.items()},
        }


class ScanReport:
    def __init__(
        self,
        source_path: str,
        stats: ScanStats,
        files: list[FileScanResult],
    ):
        self.source_path = source_path
        self.timestamp = datetime.now().isoformat()
        self.stats = stats
        self.files = files

    def to_dict(self) -> dict:
        return {
            "source_path": self.source_path,
            "timestamp": self.timestamp,
            "stats": self.stats.to_dict(),
            "files": [f.to_dict() for f in self.files],
        }


def scan_directory(
    path: Path,
    config: Config,
    recursive: bool = True,
) -> ScanReport:
    all_files = list(path.rglob("*") if recursive else path.glob("*"))
    files = [f for f in all_files if f.is_file()]

    supported_exts = get_supported_extensions()

    stats = ScanStats()
    stats.total_files = len(files)
    results: list[FileScanResult] = []

    classified_count = 0
    confidence_sum = 0.0

    for file_path in files:
        file_start = time.time()
        ext = file_path.suffix.lower()
        stats.by_extension[ext] = stats.by_extension.get(ext, 0) + 1

        if is_media_file(file_path):
            stats.media_files += 1
            result = FileScanResult(
                path=str(file_path),
                extension=ext,
                error="Media file (skipped classification)",
            )
            results.append(result)
            stats.total_time += time.time() - file_start
            continue

        if ext not in supported_exts:
            result = FileScanResult(
                path=str(file_path),
                extension=ext,
                error="Unsupported file type",
            )
            results.append(result)
            stats.total_time += time.time() - file_start
            continue

        stats.supported_files += 1

        category = classify_by_extension(file_path, config.taxonomy)
        title_meta, text = extract_text_metadata(file_path)
        title = title_meta or generate_title_from_text(text, file_path.name)

        classification = ClassificationResult(
            title=title,
            document_type="other",
            main_category=category,
            document_date=None,
            suggested_filename=title,
            confidence=1.0,
            summary=f"Filed under {category}",
        )

        file_elapsed = time.time() - file_start
        stats.classified_files += 1
        classified_count += 1
        confidence_sum += classification.confidence

        cat = classification.main_category
        stats.by_category_time[cat] = stats.by_category_time.get(cat, 0.0) + file_elapsed
        stats.total_time += file_elapsed

        dtype = classification.document_type
        stats.by_category[cat] = stats.by_category.get(cat, 0) + 1
        stats.by_document_type[dtype] = stats.by_document_type.get(dtype, 0) + 1

        result = FileScanResult(
            path=str(file_path),
            extension=ext,
            classification=classification,
        )
        results.append(result)

    if classified_count > 0:
        stats.avg_confidence = confidence_sum / classified_count

    return ScanReport(str(path), stats, results)


def write_report_json(report: ScanReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False, default=str)


def write_report_csv(report: ScanReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "path",
                "extension",
                "category",
                "document_type",
                "title",
                "confidence",
                "summary",
                "error",
            ]
        )
        for file_result in report.files:
            cl = file_result.classification
            if cl:
                writer.writerow(
                    [
                        file_result.path,
                        file_result.extension,
                        cl.main_category,
                        cl.document_type,
                        cl.title,
                        cl.confidence,
                        cl.summary,
                        "",
                    ]
                )
            else:
                writer.writerow(
                    [
                        file_result.path,
                        file_result.extension,
                        "",
                        "",
                        "",
                        "",
                        "",
                        file_result.error or "",
                    ]
                )
