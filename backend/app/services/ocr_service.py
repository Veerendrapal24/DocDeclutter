"""
OCR and Text Extraction Service for DocDeclutter.
Supports:
- Digital PDFs: selectable text extraction via PyMuPDF (fitz)
- Scanned PDFs: page rendering to image + OCR via Tesseract (if available)
- Images (PNG, JPG, JPEG): OCR via Tesseract (if available)
- Multipage preservation with page headers (--- Page X ---)
- Automatic detection of digital vs scanned PDFs
- File persistence under backend/extracted_text/
"""

import io
import os
import shutil
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image
import pytesseract

from app.core.config import settings


BACKEND_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class OCRError(Exception):
    """Custom exception raised during text extraction failure."""
    pass


class OCRService:
    def __init__(
        self,
        extracted_text_dir: str = "extracted_text",
    ):
        if not os.path.isabs(extracted_text_dir):
            if not os.path.exists(extracted_text_dir) and os.path.exists(os.path.join(BACKEND_BASE_DIR, extracted_text_dir)):
                extracted_text_dir = os.path.join(BACKEND_BASE_DIR, extracted_text_dir)
            elif not os.path.exists(extracted_text_dir):
                extracted_text_dir = os.path.join(BACKEND_BASE_DIR, extracted_text_dir)

        self.extracted_text_dir = extracted_text_dir
        os.makedirs(self.extracted_text_dir, exist_ok=True)
        self._tesseract_path: Optional[str] = None
        self._configure_tesseract()

    def _configure_tesseract(self) -> Optional[str]:
        """
        Detect and configure the Tesseract executable path.
        Checks config, environment variable, PATH, and common Windows locations.
        """
        candidates = []

        # 1. Configured path from settings
        if getattr(settings, "tesseract_cmd", None):
            candidates.append(settings.tesseract_cmd)

        # 2. Environment variable
        env_cmd = os.environ.get("TESSERACT_CMD")
        if env_cmd:
            candidates.append(env_cmd)

        # 3. In system PATH
        which_path = shutil.which("tesseract")
        if which_path:
            candidates.append(which_path)

        # 4. Standard Windows install locations
        candidates.extend([
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
            r"C:\tools\tesseract\tesseract.exe",
        ])

        for path in candidates:
            if path and os.path.isfile(path):
                try:
                    pytesseract.pytesseract.tesseract_cmd = path
                    self._tesseract_path = path
                    return path
                except Exception:
                    continue

        self._tesseract_path = None
        return None

    def is_tesseract_available(self) -> bool:
        """Check if Tesseract binary is available and executable."""
        if not self._tesseract_path:
            self._configure_tesseract()
        if not self._tesseract_path:
            return False
        try:
            # Quick check
            _ = pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def get_tesseract_status(self) -> Dict[str, Optional[str]]:
        """Return diagnostic status of the Tesseract engine."""
        available = self.is_tesseract_available()
        version = None
        if available:
            try:
                version = str(pytesseract.get_tesseract_version())
            except Exception:
                version = "installed"
        return {
            "available": available,
            "path": self._tesseract_path,
            "version": version,
        }

    # ------------------------------------------------------------------
    # Extraction Logic
    # ------------------------------------------------------------------

    def extract_text_from_file(
        self,
        doc_id: str,
        file_path: str,
        content_type: str,
    ) -> Dict:
        """
        Extract text from an uploaded document (PDF, PNG, JPG, JPEG).
        Saves the extracted text to extracted_text/{doc_id}.txt.
        Returns a dict with extraction metadata:
          - text: str
          - page_count: int
          - extraction_method: str ('pymupdf' | 'tesseract')
          - extracted_text_path: str (relative path)
          - extracted_at: str (ISO timestamp)
        """
        if not os.path.exists(file_path):
            raise OCRError(f"Document file not found at: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise OCRError("Document file is empty (0 bytes).")

        content_type = (content_type or "").lower()
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        if content_type == "application/pdf" or ext == ".pdf":
            text, page_count, method = self._process_pdf(file_path)
        elif content_type in ("image/png", "image/jpeg", "image/jpg") or ext in (".png", ".jpg", ".jpeg"):
            text, page_count, method = self._process_image(file_path)
        else:
            raise OCRError(f"Unsupported file format '{content_type}' for text extraction.")

        # Save extracted text to backend/extracted_text/{doc_id}.txt
        now = datetime.now(timezone.utc).isoformat()
        txt_filename = f"{doc_id}.txt"
        abs_txt_path = os.path.join(self.extracted_text_dir, txt_filename)
        with open(abs_txt_path, "w", encoding="utf-8") as f:
            f.write(text)

        relative_txt_path = os.path.join(self.extracted_text_dir, txt_filename).replace("\\", "/")

        return {
            "text": text,
            "page_count": page_count,
            "extraction_method": method,
            "extracted_text_path": relative_txt_path,
            "extracted_at": now,
        }

    def _process_pdf(self, file_path: str) -> Tuple[str, int, str]:
        """
        Extract text from a PDF file.
        1. Attempt digital text extraction via PyMuPDF.
        2. If extracted text is empty or near-empty (scanned PDF), fallback to OCR.
        """
        try:
            doc = fitz.open(file_path)
        except Exception as e:
            raise OCRError(f"Failed to open PDF document: {e}")

        page_count = len(doc)
        if page_count == 0:
            raise OCRError("PDF document contains 0 pages.")

        # Attempt digital extraction page by page
        digital_pages = []
        total_chars = 0

        for i, page in enumerate(doc):
            page_text = page.get_text() or ""
            digital_pages.append(page_text.strip())
            total_chars += len(page_text.strip())

        # Heuristic: If we extracted non-trivial text (> 20 chars), treat as digital PDF
        if total_chars > 20:
            doc.close()
            # Format multipage text with clean page headers
            formatted_text = self._format_multipage_text(digital_pages)
            return formatted_text, page_count, "pymupdf"

        # If digital text is missing/empty, fallback to OCR on pages
        if not self.is_tesseract_available():
            doc.close()
            # If there was a tiny amount of digital text, use it rather than failing
            if total_chars > 0:
                formatted_text = self._format_multipage_text(digital_pages)
                return formatted_text, page_count, "pymupdf"

            raise OCRError(
                "Document appears to be a scanned image-based PDF with no digital text. "
                "Tesseract-OCR is required to process scanned documents, but is not installed or configured on the server."
            )

        # Perform OCR on each page using Tesseract
        ocr_pages = []
        try:
            for i, page in enumerate(doc):
                # Render page to an image pixmap at 200 DPI for good OCR accuracy
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                page_ocr_text = pytesseract.image_to_string(img)
                ocr_pages.append(page_ocr_text.strip())
        except Exception as e:
            doc.close()
            raise OCRError(f"OCR error while processing scanned PDF: {e}")

        doc.close()
        formatted_text = self._format_multipage_text(ocr_pages)
        return formatted_text, page_count, "tesseract"

    def _process_image(self, file_path: str) -> Tuple[str, int, str]:
        """Extract text from an image file (PNG, JPG, JPEG) using Tesseract."""
        if not self.is_tesseract_available():
            raise OCRError(
                "Tesseract-OCR is required to extract text from images, "
                "but is not installed or configured on the server."
            )

        try:
            with Image.open(file_path) as img:
                # Convert palette/RGBA if necessary
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                text = pytesseract.image_to_string(img)
        except Exception as e:
            raise OCRError(f"Failed to extract text from image: {e}")

        cleaned_text = text.strip()
        return cleaned_text, 1, "tesseract"

    @staticmethod
    def _format_multipage_text(pages: list[str]) -> str:
        """Format multipage text preserving page numbers."""
        if len(pages) == 1:
            return pages[0]

        output = []
        for i, text in enumerate(pages, start=1):
            output.append(f"--- Page {i} ---\n{text}")
        return "\n\n".join(output)

    def read_extracted_text(self, relative_path: str) -> Optional[str]:
        """Read the extracted text file from disk."""
        if not relative_path:
            return None
        # Safe path check
        base = os.path.realpath(self.extracted_text_dir)
        full_path = os.path.realpath(relative_path)
        if not full_path.startswith(base) and not os.path.exists(full_path):
            # Try combining with base
            full_path = os.path.realpath(os.path.join(self.extracted_text_dir, os.path.basename(relative_path)))

        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def delete_extracted_text(self, relative_path: str) -> bool:
        """Delete an extracted text file from disk."""
        if not relative_path:
            return False
        try:
            full_path = os.path.realpath(relative_path)
            if not os.path.exists(full_path):
                full_path = os.path.realpath(os.path.join(self.extracted_text_dir, os.path.basename(relative_path)))
            if os.path.exists(full_path):
                os.remove(full_path)
                return True
        except Exception:
            pass
        return False


# Singleton service instance
ocr_service = OCRService()
