import io
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - optional dependency
    PdfReader = None

ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".pdf"}


def normalize_document_text(text: str) -> str:
    cleaned = text.strip()
    return cleaned[:20000]


def extract_document_text(filename: str, file_bytes: bytes) -> str:
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. Supported types: txt, md, csv, json, pdf."
        )

    if extension in {".txt", ".md", ".csv", ".json"}:
        try:
            return normalize_document_text(file_bytes.decode("utf-8-sig"))
        except UnicodeDecodeError:
            return normalize_document_text(file_bytes.decode("latin-1"))

    if extension == ".pdf":
        if PdfReader is None:
            raise ValueError("PDF support requires the pypdf package to be installed.")

        reader = PdfReader(io.BytesIO(file_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text.strip())
        return normalize_document_text("\n\n".join(pages))

    raise ValueError(f"File type '{extension}' is not supported.")
