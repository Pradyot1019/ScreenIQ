"""File validation and text extraction for resumes (FR-20, FR-22).

Validation trusts the file's own bytes, not its name or the browser's Content-Type:
both are client-supplied and trivially faked ("cv.pdf" can be an .exe).
"""

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass

import docx
import pymupdf

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB (FR-20)
MAX_FILES_PER_BATCH = 50

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
EXTENSION = {PDF: "pdf", DOCX: "docx"}


class UnsupportedFileError(ValueError):
    """The upload isn't a usable PDF/DOCX. The message is shown to the recruiter."""


@dataclass(frozen=True)
class CheckedFile:
    mime_type: str
    sha256: str


def check_file(data: bytes) -> CheckedFile:
    """Size + magic-byte check. Raises UnsupportedFileError with a user-facing reason."""
    if not data:
        raise UnsupportedFileError("The file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise UnsupportedFileError("The file is larger than 5 MB.")
    if data.startswith(b"%PDF-"):
        mime = PDF
    elif data.startswith(b"PK\x03\x04") and _is_docx(data):
        mime = DOCX  # a DOCX is a ZIP archive containing word/document.xml
    else:
        raise UnsupportedFileError("Only PDF and DOCX files are supported.")
    return CheckedFile(mime, hashlib.sha256(data).hexdigest())


def _is_docx(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return "word/document.xml" in z.namelist()
    except zipfile.BadZipFile:
        return False


def extract_text(data: bytes, mime_type: str) -> str:
    """Plain text with whitespace tidied. Raises UnsupportedFileError if nothing readable."""
    try:
        text = _extract_pdf(data) if mime_type == PDF else _extract_docx(data)
    except UnsupportedFileError:
        raise
    except Exception as e:  # corrupt or encrypted files raise library-specific errors
        raise UnsupportedFileError(
            "The file couldn't be read (corrupt or password-protected?)."
        ) from e
    text = clean_text(text)
    if len(text) < 50:
        # Scanned PDFs are images with no text layer; OCR is out of scope (FR-22 P2).
        raise UnsupportedFileError("No readable text found. Scanned PDFs aren't supported yet.")
    return text


def _extract_pdf(data: bytes) -> str:
    with pymupdf.open(stream=data, filetype="pdf") as doc:  # type: ignore[no-untyped-call]
        if doc.needs_pass:
            raise UnsupportedFileError("The PDF is password-protected.")
        return "\n".join(page.get_text() for page in doc)


def _extract_docx(data: bytes) -> str:
    document = docx.Document(io.BytesIO(data))
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:  # many resume templates lay out content in tables
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def clean_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\r", "\n")
    text = re.sub(r"[ \t ]+", " ", text)  # collapse runs of spaces/tabs
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)  # at most one blank line
    return text.strip()
