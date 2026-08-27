from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from doc_classifier.models import ClassificationResult, Config
from doc_classifier.rules import (
    classify_by_extension,
    find_config_file,
    generate_target_filename,
    generate_title_from_text,
    load_config,
    resolve_target_folder,
    sanitize_filename,
    save_config_paths,
    unique_path,
    write_default_config,
)


@pytest.fixture
def sample_config(tmp_path: Path) -> Config:
    config_data = {
        "classification": {
            "default_model": "ollama/qwen2.5:1.5b",
            "max_chars": 2000,
            "temperature": 0.1,
        },
        "paths": {
            "source_dir": r"C:\Users\test\Downloads",
            "output_dir": r"D:\Organized",
        },
        "taxonomy": {
            "Documents": {"keywords": [], "folder": "Documents"},
            "Spreadsheets": {"keywords": [], "folder": "Spreadsheets"},
            "Images": {"keywords": [], "folder": "Images"},
            "Audio": {"keywords": [], "folder": "Audio"},
        },
        "file_naming": {
            "pattern": "{title}",
            "date_format": "%Y-%m-%d",
            "max_length": 255,
            "sanitize_chars": True,
        },
    }
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(config_data), encoding="utf-8")
    return load_config(str(config_file))


class TestPathsConfig:
    def test_paths_loaded(self, sample_config):
        assert sample_config.paths.source_dir == r"C:\Users\test\Downloads"
        assert sample_config.paths.output_dir == r"D:\Organized"

    def test_paths_default_empty(self):
        config = Config()
        assert config.paths.source_dir is None
        assert config.paths.output_dir is None


class TestSanitizeFilename:
    def test_removes_special_chars(self):
        assert sanitize_filename('he<ll>o:"world"') == "helloworld"

    def test_replaces_spaces(self):
        assert sanitize_filename("hello world test") == "hello_world_test"

    def test_collapses_underscores(self):
        assert sanitize_filename("hello___world") == "hello_world"

    def test_max_length(self):
        result = sanitize_filename("a" * 200, max_length=50)
        assert len(result) <= 50

    def test_empty_string(self):
        assert sanitize_filename("") == ""


class TestGenerateTargetFilename:
    def test_uses_title_pattern(self, sample_config):
        name = generate_target_filename("Financial_Report", ".pdf", sample_config.file_naming)
        assert name == "Financial_Report.pdf"

    def test_custom_title(self, sample_config):
        name = generate_target_filename("my_document", ".txt", sample_config.file_naming)
        assert name == "my_document.txt"


class TestGenerateTitleFromText:
    def test_uses_metadata_first(self):
        title = generate_title_from_text(None, "my_file.pdf")
        assert "my_file" in title

    def test_uses_content_line(self):
        title = generate_title_from_text("This is a financial report for Q1 2024", "x.pdf")
        assert "financial" in title.lower() or "report" in title.lower() or "This" in title

    def test_fallback_to_stem(self):
        title = generate_title_from_text("", "my_document.pdf")
        assert "my_document" in title

    def test_strips_urls(self):
        title = generate_title_from_text("Check http://www.example.com for details", "doc.pdf")
        assert "http" not in title


class TestSaveConfigPaths:
    def test_updates_paths(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("taxonomy: {}\n", encoding="utf-8")

        config = save_config_paths("C:/src", "D:/out", config_file)
        assert config.paths.source_dir == "C:/src"
        assert config.paths.output_dir == "D:/out"

        reloaded = load_config(config_file)
        assert reloaded.paths.source_dir == "C:/src"
        assert reloaded.paths.output_dir == "D:/out"

    def test_partial_update_keeps_existing(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "paths:\n  source_dir: C:/old\n  output_dir: D:/old\n", encoding="utf-8"
        )

        save_config_paths("C:/new", None, config_file)
        reloaded = load_config(config_file)
        assert reloaded.paths.source_dir == "C:/new"
        assert reloaded.paths.output_dir == "D:/old"


class TestResolveTargetFolder:
    def test_known_category(self, sample_config):
        folder = resolve_target_folder("Documents", sample_config.taxonomy, "/base")
        assert "Documents" in str(folder)

    def test_unknown_category_falls_back(self, sample_config):
        folder = resolve_target_folder("UnknownCategory", sample_config.taxonomy, "/base")
        folder_str = str(folder)
        assert any(name in folder_str for name in ["Documents", "Spreadsheets", "Images", "Audio"])


class TestUniquePath:
    def test_returns_same_if_not_exists(self, tmp_path):
        target = tmp_path / "test.pdf"
        assert unique_path(target) == target

    def test_increments_if_exists(self, tmp_path):
        target = tmp_path / "test.pdf"
        target.touch()
        result = unique_path(target)
        assert result.name == "test_1.pdf"

    def test_increments_multiple(self, tmp_path):
        for i in ["test.pdf", "test_1.pdf", "test_2.pdf"]:
            (tmp_path / i).touch()
        result = unique_path(tmp_path / "test.pdf")
        assert result.name == "test_3.pdf"


class TestClassifyByExtension:
    def test_pdf_to_documents(self, tmp_path):
        f = tmp_path / "report.pdf"
        f.touch()
        config = Config()
        config.taxonomy = {
            "Documents": {"keywords": [], "folder": "Documents"},
            "Spreadsheets": {"keywords": [], "folder": "Spreadsheets"},
        }
        result = classify_by_extension(f, config.taxonomy)
        assert result == "Documents"

    def test_csv_to_spreadsheets(self, tmp_path):
        f = tmp_path / "data.csv"
        f.touch()
        config = Config()
        config.taxonomy = {
            "Documents": {"keywords": [], "folder": "Documents"},
            "Spreadsheets": {"keywords": [], "folder": "Spreadsheets"},
        }
        result = classify_by_extension(f, config.taxonomy)
        assert result == "Spreadsheets"

    def test_jpg_to_images(self, tmp_path):
        f = tmp_path / "photo.jpg"
        f.touch()
        config = Config()
        config.taxonomy = {
            "Documents": {"keywords": [], "folder": "Documents"},
            "Images": {"keywords": [], "folder": "Images"},
        }
        result = classify_by_extension(f, config.taxonomy)
        assert result == "Images"

    def test_mp3_to_audio(self, tmp_path):
        f = tmp_path / "song.mp3"
        f.touch()
        config = Config()
        config.taxonomy = {
            "Documents": {"keywords": [], "folder": "Documents"},
            "Audio": {"keywords": [], "folder": "Audio"},
        }
        result = classify_by_extension(f, config.taxonomy)
        assert result == "Audio"


class TestFindConfigFile:
    def test_explicit_flag_wins(self, tmp_path):
        result = find_config_file(explicit=tmp_path / "custom.yaml")
        assert result == tmp_path / "custom.yaml"

    def test_local_config_found_in_cwd(self, tmp_path):
        (tmp_path / "config.yaml").write_text("paths: {}", encoding="utf-8")
        empty_home = tmp_path / "home"
        empty_home.mkdir()
        result = find_config_file(cwd=tmp_path, home=empty_home)
        assert result == tmp_path / "config.yaml"

    def test_falls_back_to_global(self, tmp_path):
        empty_cwd = tmp_path / "cwd"
        empty_cwd.mkdir()
        fake_home = tmp_path / "home"
        global_dir = fake_home / ".doc-classifier"
        global_dir.mkdir(parents=True)
        (global_dir / "config.yaml").write_text("paths: {}", encoding="utf-8")

        result = find_config_file(cwd=empty_cwd, home=fake_home)
        assert result == global_dir / "config.yaml"

    def test_returns_none_when_missing(self, tmp_path):
        empty_cwd = tmp_path / "cwd"
        empty_cwd.mkdir()
        empty_home = tmp_path / "home"
        empty_home.mkdir()
        result = find_config_file(cwd=empty_cwd, home=empty_home)
        assert result is None


class TestWriteDefaultConfig:
    def test_creates_complete_config(self, tmp_path):
        target = tmp_path / "nested" / "config.yaml"
        write_default_config(target, source_dir="C:/src", output_dir="C:/out")

        config = load_config(str(target))
        assert len(config.taxonomy) == 4
        assert config.paths.source_dir == "C:/src"
        assert config.paths.output_dir == "C:/out"

    def test_default_taxonomy_has_folders(self):
        from doc_classifier.rules import DEFAULT_TAXONOMY

        for entry in DEFAULT_TAXONOMY.values():
            assert "folder" in entry


class TestClassificationNormalization:
    def test_junk_date_becomes_none(self):
        classification = ClassificationResult(
            title="Test Doc",
            document_type="other",
            main_category="Documents",
            document_date="null",
            suggested_filename="test_doc",
        )
        assert classification.document_date is None

    def test_empty_title_fallback(self):
        classification = ClassificationResult(
            title="   ",
            document_type="other",
            main_category="Documents",
            suggested_filename="test",
        )
        assert classification.title == "Untitled Document"


class TestFilenameFallbacks:
    def test_clean_title(self, sample_config):
        name = generate_target_filename("Clean_Title", ".pdf", sample_config.file_naming)
        assert name == "Clean_Title.pdf"

    def test_symbol_only_falls_back(self, sample_config):
        name = generate_target_filename("document", ".png", sample_config.file_naming)
        assert name == "document.png"


class TestNoFallbackOption:
    def test_run_classify_accepts_no_fallback_flag(self, sample_config, tmp_path):
        from doc_classifier.cli import run_classify

        (tmp_path / "doc.txt").write_text("Sample content", encoding="utf-8")
        out_dir = tmp_path / "out"
        code = run_classify(
            path=str(tmp_path / "doc.txt"),
            output_dir=str(out_dir),
            dry_run=True,
            no_fallback=True,
        )
        assert code == 0
