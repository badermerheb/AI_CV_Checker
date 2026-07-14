"""Extract raw text from uploaded CV files (PDF via PyMuPDF, DOCX via docx2txt)."""

import os
import tempfile

import pymupdf


class ParseError(Exception):
    pass


def parse_document(data: bytes, filename: str) -> list[str]:
    """Return the document text as a list of page strings (DOCX = one page)."""
    ext = os.path.splitext(filename.lower())[1]
    if ext == ".pdf":
        try:
            with pymupdf.open(stream=data, filetype="pdf") as doc:
                return [page.get_text("text") for page in doc]
        except Exception as exc:
            raise ParseError(f"could not read PDF: {exc}") from exc
    if ext == ".docx":
        import docx2txt

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            return [docx2txt.process(tmp_path) or ""]
        except Exception as exc:
            raise ParseError(f"could not read DOCX: {exc}") from exc
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
    raise ParseError(f"unsupported file type: {ext}")
