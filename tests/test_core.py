from __future__ import annotations

from pathlib import Path

import pytest

from doc_classifier.models import ClassificationResult, Config
from doc_classifier.rules import (
    classify_by_keywords,
    find_config_file,
    generate_target_filename,
    load_config,
    resolve_target_folder,
    sanitize_filename,
    save_config_paths,
    unique_path,
    write_default_config,
)


@pytest.fixture
def sample_classification() -> ClassificationResult:
    return ClassificationResult(
        title="Laporan Keuangan Q1 2024",
        document_type="report",
        main_category="Keuangan",
        document_date="2024-03-15",
        suggested_filename="Laporan_Keuangan_Q1_2024",
        confidence=0.92,
        summary="Laporan keuangan kuartal pertama tahun 2024",
    )


@pytest.fixture
def sample_config(tmp_path: Path) -> Config:
    config_data = {
        "classification": {
            "default_model": "ollama/llama3:8b",
            "max_chars": 2000,
            "temperature": 0.1,
        },
        "paths": {
            "source_dir": r"C:\Users\test\Downloads",
            "output_dir": r"D:\Organized",
        },
        "taxonomy": {
            "Keuangan": {"keywords": ["invoice"], "folder": "01_Keuangan"},
            "Lainnya": {"keywords": [], "folder": "09_Lainnya"},
        },
        "file_naming": {
            "pattern": "{date}_{title}_{type}",
            "date_format": "%Y-%m-%d",
            "max_length": 120,
            "sanitize_chars": True,
        },
    }
    config_file = tmp_path / "config.yaml"
    import yaml

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
    def test_generates_correct_name(self, sample_classification, sample_config):
        name = generate_target_filename(
            sample_classification, ".pdf", sample_config.file_naming
        )
        assert name.endswith(".pdf")
        assert "Laporan_Keuangan_Q1_2024" in name
        assert "2024-03-15" in name

    def test_uses_current_date_if_none(self, sample_config):
        classification = ClassificationResult(
            title="Test",
            document_type="report",
            main_category="Lainnya",
            suggested_filename="test",
        )
        name = generate_target_filename(classification, ".txt", sample_config.file_naming)
        assert name.endswith(".txt")


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
    def test_known_category(self, sample_classification, sample_config):
        folder = resolve_target_folder(
            sample_classification, sample_config.taxonomy, "/base"
        )
        assert "01_Keuangan" in str(folder)

    def test_unknown_category_falls_back(self, sample_config):
        classification = ClassificationResult(
            title="Test",
            document_type="other",
            main_category="UnknownCategory",
            suggested_filename="test",
        )
        folder = resolve_target_folder(classification, sample_config.taxonomy, "/base")
        assert "09_Lainnya" in str(folder)


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


class TestExtractText:
    def test_txt_file(self, tmp_path):
        from doc_classifier.parser import extract_text

        txt_file = tmp_path / "sample.txt"
        txt_file.write_text("Hello World ini adalah dokumen test", encoding="utf-8")
        result = extract_text(str(txt_file))
        assert result is not None
        assert "Hello World" in result

    def test_nonexistent_file(self):
        from doc_classifier.parser import extract_text

        result = extract_text("/nonexistent/file.pdf")
        assert result is None

    def test_unsupported_extension(self, tmp_path):
        from doc_classifier.parser import extract_text

        f = tmp_path / "test.xyz"
        f.touch()
        result = extract_text(str(f))
        assert result is None


class TestOfficeParsing:
    def test_csv_file(self, tmp_path):
        from doc_classifier.parser import extract_text

        csv_file = tmp_path / "invoice.csv"
        csv_file.write_text(
            "item,qty,price\nKertas A4,10,50000\nTinta Printer,2,150000\n",
            encoding="utf-8",
        )
        result = extract_text(str(csv_file))
        assert result is not None
        assert "Kertas A4" in result

    def test_xlsx_file(self, tmp_path):
        openpyxl = pytest.importorskip("openpyxl")
        from doc_classifier.parser import extract_text

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Nama", "Gaji"])
        ws.append(["Andi", 5000000])
        xlsx_file = tmp_path / "payroll.xlsx"
        wb.save(str(xlsx_file))

        result = extract_text(str(xlsx_file))
        assert result is not None
        assert "Andi" in result

    def test_odt_file(self, tmp_path):
        odf_opendocument = pytest.importorskip("odf.opendocument")
        from odf import text as odf_text

        from doc_classifier.parser import extract_text

        doc = odf_opendocument.OpenDocumentText()
        doc.text.addElement(odf_text.P(text="Surat Perjanjian Kerja Sama"))
        doc.text.addElement(odf_text.P(text="Nomor: 001/2026"))
        odt_file = tmp_path / "surat.odt"
        doc.save(str(odt_file))

        result = extract_text(str(odt_file))
        assert result is not None
        assert "Perjanjian" in result

    def test_supported_extensions_include_office(self):
        from doc_classifier.parser import get_supported_extensions

        exts = get_supported_extensions()
        for ext in (".xlsx", ".csv", ".ods", ".odt"):
            assert ext in exts


class TestClassificationNormalization:
    def test_junk_date_becomes_none(self):
        classification = ClassificationResult(
            title="Test Doc",
            document_type="other",
            main_category="Lainnya",
            document_date="null",
            suggested_filename="test_doc",
        )
        assert classification.document_date is None

    def test_valid_date_kept(self, sample_classification):
        assert sample_classification.document_date == "2024-03-15"

    def test_empty_title_fallback(self):
        classification = ClassificationResult(
            title="   ",
            document_type="other",
            main_category="Lainnya",
            suggested_filename="test",
        )
        assert classification.title == "Untitled Document"


class TestFilenameFallbacks:
    def test_null_date_uses_current_date(self, sample_config):
        classification = ClassificationResult(
            title="Dokumen Tanpa Tanggal",
            document_type="report",
            main_category="Lainnya",
            document_date="null",
            suggested_filename="dokumen_tanpa_tanggal",
        )
        name = generate_target_filename(classification, ".pdf", sample_config.file_naming)
        assert not name.startswith("null")
        assert "_null_" not in name

    def test_symbol_only_title_falls_back_to_suggested(self, sample_config):
        classification = ClassificationResult(
            title="»& ??? ***",
            document_type="other",
            main_category="Lainnya",
            suggested_filename="nama_file_bagus",
        )
        name = generate_target_filename(classification, ".png", sample_config.file_naming)
        assert "nama_file_bagus" in name


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
        assert len(config.taxonomy) == 9
        assert config.paths.source_dir == "C:/src"
        assert config.paths.output_dir == "C:/out"

    def test_default_taxonomy_has_folders(self):
        from doc_classifier.rules import DEFAULT_TAXONOMY

        for entry in DEFAULT_TAXONOMY.values():
            assert "folder" in entry


class TestKeywordFallback:
    def test_matches_keyword_category(self, sample_config):
        classification = classify_by_keywords(
            "Ini adalah invoice untuk pembayaran", sample_config.taxonomy, "tagihan.pdf"
        )
        assert classification.main_category == "Keuangan"

    def test_no_match_goes_to_lainnya(self, sample_config):
        classification = classify_by_keywords(
            "teks acak tanpa kata kunci", sample_config.taxonomy, "acak.pdf"
        )
        assert classification.main_category == "Lainnya"

    def test_empty_text_still_classified(self, sample_config):
        classification = classify_by_keywords("", sample_config.taxonomy, "scan_001.pdf")
        assert classification.main_category == "Lainnya"

    def test_title_from_original_name(self, sample_config):
        classification = classify_by_keywords(
            "", sample_config.taxonomy, "Laporan Bulanan Maret.pdf"
        )
        assert classification.title == "Laporan_Bulanan_Maret"

    def test_low_confidence_marks_rule_based(self, sample_config):
        classification = classify_by_keywords("invoice", sample_config.taxonomy, "x.pdf")
        assert classification.confidence <= 0.5
