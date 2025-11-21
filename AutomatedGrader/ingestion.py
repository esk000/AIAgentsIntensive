import os
from typing import Tuple, Dict, Any


def extract_text(file_path: str) -> Tuple[str, Dict[str, Any]]:
    """Return plain text and metadata from a PDF or image file.

    Attempts PDF extraction via pypdf. For images, attempts OCR via
    Pillow + pytesseract. Gracefully degrades with informative metadata
    when dependencies are missing.
    """
    if not os.path.exists(file_path):
        return "", {"ok": False, "error": "file_not_found", "path": file_path}

    ext = os.path.splitext(file_path)[1].lower()
    meta: Dict[str, Any] = {"ok": True, "path": file_path, "ext": ext}

    if ext == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore
            reader = PdfReader(file_path)
            pages = [p.extract_text() or "" for p in reader.pages]
            text = "\n".join(pages).strip()
            meta["pages"] = len(reader.pages)
            return text, meta
        except Exception as e:
            meta.update({"ok": False, "error": "pdf_extract_failed", "detail": str(e)})
            return "", meta

    if ext in {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
        try:
            from PIL import Image  # type: ignore
            import pytesseract  # type: ignore
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img)
            meta["ocr"] = True
            return text.strip(), meta
        except Exception as e:
            meta.update({"ok": False, "error": "ocr_failed", "detail": str(e)})
            return "", meta

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        meta["fallback_read"] = True
        return text.strip(), meta
    except Exception as e:
        meta.update({"ok": False, "error": "unsupported_or_read_failed", "detail": str(e)})
        return "", meta