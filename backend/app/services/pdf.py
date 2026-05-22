from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PDFValidationError(ValueError):
    pass


def validate_pdf_file(pdf_path: Path, *, max_pages: int) -> list[dict]:
    if pdf_path.suffix.lower() != ".pdf":
        raise PDFValidationError("Only .pdf files are supported.")
    with pdf_path.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise PDFValidationError("Uploaded file is not a valid PDF.")
    try:
        reader = PdfReader(str(pdf_path))
    except PdfReadError as exc:
        raise PDFValidationError("PDF could not be read.") from exc
    if reader.is_encrypted:
        raise PDFValidationError("Encrypted PDFs are not supported.")
    if len(reader.pages) > max_pages:
        raise PDFValidationError(f"PDF exceeds the page limit of {max_pages}.")
    pages = extract_pages(pdf_path)
    if not pages:
        raise PDFValidationError("PDF does not contain extractable text.")
    return pages


def extract_pages(pdf_path: Path) -> list[dict]:
    reader = PdfReader(str(pdf_path))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        cleaned = " ".join(text.split())
        if cleaned:
            pages.append({"page": index, "text": cleaned})
    return pages


def chunk_pages(pages: list[dict], chunk_words: int = 220, overlap: int = 35) -> list[dict]:
    chunks: list[dict] = []
    for page in pages:
        words = page["text"].split()
        if not words:
            continue
        start = 0
        while start < len(words):
            end = min(start + chunk_words, len(words))
            text = " ".join(words[start:end])
            chunks.append({"page": page["page"], "text": text})
            if end == len(words):
                break
            start = max(end - overlap, start + 1)
    return chunks
