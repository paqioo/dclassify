from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

_JUNK_DATE_VALUES = {"null", "none", "unknown", "n/a", "na", "-", "--", "tidak ada", ""}


class ClassificationResult(BaseModel):
    title: str = Field(..., description="Judul atau topik utama dokumen")
    document_type: str = Field(
        ...,
        description=(
            "Tipe dokumen: report, article, letter, contract, "
            "invoice, resume, research, other"
        ),
    )
    main_category: str = Field(..., description="Main category matching config taxonomy")
    document_date: Optional[str] = Field(None, description="Tanggal dokumen jika terdeteksi")
    suggested_filename: str = Field(..., description="Nama file yang disarankan")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score 0-1")
    summary: str = Field(default="", description="Ringkasan singkat isi dokumen")

    @field_validator("document_date", mode="before")
    @classmethod
    def _normalize_date(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().lower() in _JUNK_DATE_VALUES:
            return None
        return value

    @field_validator("title", mode="before")
    @classmethod
    def _normalize_title(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return "Untitled Document"
        return value


class FileOperation(BaseModel):
    original_path: str
    target_path: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    action: str = Field(default="move", description="move | copy | rename | noop")
    classification: Optional[ClassificationResult] = None


class AppConfig(BaseModel):
    default_model: str = "ollama/qwen2.5:1.5b"
    max_chars: int = 2000
    temperature: float = 0.1
    fallback_keywords: bool = Field(
        default=True,
        description="Jika AI tidak tersedia, klasifikasi memakai keyword taxonomy",
    )
    enable_ai_title: bool = Field(
        default=True,
        description="Jika true, generate judul file via AI (tetap keyword-only untuk kategori)",
    )


class PathsConfig(BaseModel):
    source_dir: Optional[str] = None
    output_dir: Optional[str] = None


class TaxonomyEntry(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    folder: str


class FileNamingConfig(BaseModel):
    pattern: str = "{date}_{title}_{type}"
    date_format: str = "%Y-%m-%d"
    max_length: int = 120
    sanitize_chars: bool = True


class Config(BaseModel):
    classification: AppConfig = Field(default_factory=AppConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    taxonomy: dict[str, TaxonomyEntry] = Field(default_factory=dict)
    file_naming: FileNamingConfig = Field(default_factory=FileNamingConfig)
