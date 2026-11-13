"""File validation + text extraction on real, generated PDF/DOCX files."""

import pytest

from app.pipeline.extract import (
    DOCX,
    MAX_FILE_BYTES,
    PDF,
    UnsupportedFileError,
    check_file,
    clean_text,
    extract_text,
)
from tests.fakes import fixture_text, make_docx, make_pdf

RESUME = fixture_text("resumes/priya_sharma.txt")


def test_pdf_is_detected_and_extracted() -> None:
    data = make_pdf(RESUME)
    checked = check_file(data)
    assert checked.mime_type == PDF
    assert len(checked.sha256) == 64
    text = extract_text(data, PDF)
    assert "Priya Sharma" in text and "priya.sharma@example.com" in text


def test_docx_paragraphs_and_tables_are_extracted() -> None:
    data = make_docx(
        [
            "Rahul Verma",
            "Data Engineer with 4 years of Spark and Airflow experience in production.",
        ],
        table=[["Skills", "Python, Spark, Airflow"]],
    )
    assert check_file(data).mime_type == DOCX
    text = extract_text(data, DOCX)
    assert "Rahul Verma" in text
    assert "Skills | Python, Spark, Airflow" in text  # table content isn't lost


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (b"", "empty"),
        (b"MZ\x90\x00 this is an exe renamed to cv.pdf", "Only PDF and DOCX"),
        (b"PK\x03\x04 not really a zip", "Only PDF and DOCX"),
        (b"%PDF-" + b"0" * MAX_FILE_BYTES, "larger than 5 MB"),
    ],
    ids=["empty", "exe-renamed", "fake-zip", "too-big"],
)
def test_bad_files_are_rejected_by_content(data: bytes, reason: str) -> None:
    with pytest.raises(UnsupportedFileError, match=reason):
        check_file(data)


def test_pdf_without_text_layer_is_rejected() -> None:
    blank = make_pdf("")  # like a scanned PDF: pages but no extractable text
    with pytest.raises(UnsupportedFileError, match="No readable text"):
        extract_text(blank, PDF)


def test_corrupt_pdf_is_rejected_cleanly() -> None:
    with pytest.raises(UnsupportedFileError, match="couldn't be read"):
        extract_text(b"%PDF-1.7 garbage garbage", PDF)


def test_clean_text_tidies_whitespace() -> None:
    assert clean_text("  a\t\t b \r\n\n\n\n c\x00 ") == "a b\n\nc"
