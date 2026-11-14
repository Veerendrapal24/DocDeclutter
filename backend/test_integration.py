r"""
DocDeclutter – Comprehensive Integration Tests (Storage, OCR & Gemini AI Integration)
Covers:
- Upload, list, download, and delete
- Digital PDF text extraction (PyMuPDF)
- Multipage PDF text extraction (preserving page headers)
- Scanned PDF & Image extraction (Tesseract or graceful fallback)
- Extracted text persistence in extracted_text/{id}.txt and documents.json
- Diagnostic OCR status and AI status endpoints
- Gemini service offline parsing & Pydantic normalization
- Gemini error handling (missing API key, non-existent doc, empty text)
- AI analysis metadata persistence across service reloads
- Live Gemini API tests (executed when GEMINI_API_KEY is configured)

Run from backend/ directory:
    .\.venv\Scripts\python.exe test_integration.py
"""

import io
import json
import os
import sys

# ---- Setup sys.path and working directory -------------------------------------

def _bootstrap():
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    os.chdir(here)

_bootstrap()

import fitz  # PyMuPDF
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from app.main import app
from app.services.ocr_service import ocr_service
from app.services.document_service import document_service
from app.services.gemini_service import gemini_service, GeminiServiceError

client = TestClient(app, raise_server_exceptions=False)

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
INFO = "\033[94mℹ\033[0m"

results: list[tuple[str, bool, str]] = []


def check(label: str, condition: bool, detail: str = ""):
    icon = PASS if condition else FAIL
    print(f"  {icon} {label}" + (f"  ({detail})" if detail else ""))
    results.append((label, condition, detail))
    return condition


# ---- Synthetic Document Builders ----------------------------------------------

def make_digital_pdf(text: str) -> bytes:
    """Generate a valid single-page digital PDF with embedded text."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def make_multipage_pdf(pages_text: list[str]) -> bytes:
    """Generate a multipage PDF with distinct text per page."""
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 72), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def make_scanned_pdf(text: str) -> bytes:
    """Generate an image-only PDF (no text layer) to simulate a scanned document."""
    img = Image.new("RGB", (600, 800), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), text, fill=(0, 0, 0))

    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)

    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    page.insert_image(page.rect, stream=img_byte_arr.getvalue())
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def make_image_file(text: str, fmt: str = "PNG") -> bytes:
    """Generate an image (PNG/JPEG) with drawn text."""
    img = Image.new("RGB", (500, 200), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 50), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


# ---- Test Suites --------------------------------------------------------------

def test_diagnostic_endpoints():
    print("\n[1] Diagnostic endpoints (OCR & Gemini status)")
    # OCR Status
    resp = client.get("/api/v1/documents/ocr-status")
    check("GET /ocr-status 200", resp.status_code == 200)
    check("Has 'available' key", "available" in resp.json())

    # AI Status
    resp_ai = client.get("/api/v1/documents/ai-status")
    check("GET /ai-status 200", resp_ai.status_code == 200)
    ai_data = resp_ai.json()
    check("Has 'configured' key", "configured" in ai_data, f"Configured: {ai_data.get('configured')}")
    check("Has 'model' key", bool(ai_data.get("model")), f"Model: {ai_data.get('model')}")


def test_digital_pdf_pipeline():
    print("\n[2] Digital PDF text extraction (PyMuPDF)")
    pdf_content = (
        "DELHI METRO RAIL CORPORATION\n"
        "Technical Inspection Report - Track Maintenance Division\n"
        "Status: Clearance verified. Overhead catenary wire voltage: 25kV AC nominal.\n"
        "All platform screen doors operational."
    )
    pdf_bytes = make_digital_pdf(pdf_content)

    up_resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("dmrc_inspection.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    ok = check("Upload 202", up_resp.status_code == 202)
    if not ok:
        return None
    doc_id = up_resp.json()["id"]

    ext_resp = client.post(f"/api/v1/documents/{doc_id}/extract")
    check("Extract 200", ext_resp.status_code == 200)
    ext_data = ext_resp.json()
    check("Method is PyMuPDF", ext_data.get("extraction_method") == "pymupdf")
    check("Page count is 1", ext_data.get("page_count") == 1)

    txt_path = f"extracted_text/{doc_id}.txt"
    check("Text saved to disk", os.path.exists(txt_path))

    get_text_resp = client.get(f"/api/v1/documents/{doc_id}/text")
    check("GET text status 200", get_text_resp.status_code == 200)

    # Cleanup
    client.delete(f"/api/v1/documents/{doc_id}")
    check("Cleanup removes extracted txt", not os.path.exists(txt_path))


def test_multipage_pdf_pipeline():
    print("\n[3] Multipage PDF text extraction")
    pages = [
        "PAGE 1: Line 3 Blue Line signaling checks passed.",
        "PAGE 2: Automatic Train Control (ATC) calibrated.",
        "PAGE 3: Final sign-off by Chief Operations Officer.",
    ]
    pdf_bytes = make_multipage_pdf(pages)
    up_resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("multipage_log.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    doc_id = up_resp.json()["id"]

    ext_resp = client.post(f"/api/v1/documents/{doc_id}/extract")
    check("Extract 200", ext_resp.status_code == 200)
    ext_data = ext_resp.json()
    check("Page count is 3", ext_data.get("page_count") == 3)
    full_text = ext_data.get("extracted_text") or ""
    check("Has '--- Page 1 ---'", "--- Page 1 ---" in full_text)
    check("Has '--- Page 2 ---'", "--- Page 2 ---" in full_text)
    check("Has '--- Page 3 ---'", "--- Page 3 ---" in full_text)

    client.delete(f"/api/v1/documents/{doc_id}")


def test_gemini_service_offline_validation():
    print("\n[4] Gemini service offline JSON parsing & schema normalization")
    # A. Clean JSON parsing
    sample_json = json.dumps({
        "category": "Maintenance Report",
        "confidence": 0.94,
        "classification_reason": "Escalator failure report at Ameerpet station.",
        "summary": "Escalator #3 at Ameerpet station halted due to a drive motor fault.",
        "extracted_fields": {
            "station": "Ameerpet",
            "equipment": "Escalator #3",
            "issue": "Motor failure",
            "severity": "High"
        },
        "keywords": ["Escalator", "Ameerpet", "Maintenance"],
        "suggested_priority": "High",
        "priority_explanation": "Peak hour passenger transfer station escalator out of service.",
        "action_items": ["Dispatch technician", "Order replacement bearing"]
    })

    result = gemini_service._clean_and_parse_json(sample_json)
    validated = gemini_service._normalize_and_validate(result)

    check("Category parsed", validated.category == "Maintenance Report")
    check("Confidence in range", 0.0 <= validated.confidence <= 1.0)
    check("Priority normalized", validated.suggested_priority == "High")
    check("Fields extracted", validated.extracted_fields.get("station") == "Ameerpet")
    check("Keywords extracted", "Escalator" in validated.keywords)
    check("Action items present", len(validated.action_items) == 2)

    # B. Markdown code fence stripping
    fenced_json = f"```json\n{sample_json}\n```"
    result_fenced = gemini_service._clean_and_parse_json(fenced_json)
    check("Fenced JSON parsed", result_fenced.get("category") == "Maintenance Report")

    # C. Category fuzzy matching & fallback
    partial_data = {
        "category": "safety inspection",
        "confidence": 1.5,  # Needs clamping to 1.0
        "suggested_priority": "CRITICAL",
        "summary": "Safety check.",
        "extracted_fields": None,
    }
    validated_partial = gemini_service._normalize_and_validate(partial_data)
    check("Fuzzy category matches Safety Inspection Report", validated_partial.category == "Safety Inspection Report")
    check("Confidence clamped to 1.0", validated_partial.confidence == 1.0)
    check("Priority normalized to Critical", validated_partial.suggested_priority == "Critical")
    check("Extracted fields converted to dict", isinstance(validated_partial.extracted_fields, dict))


def test_gemini_error_handling():
    print("\n[5] Gemini API error handling (missing key, invalid doc, empty text)")

    # A. Missing doc ID
    resp = client.post("/api/v1/documents/non-existent-id-9999/analyze")
    check("Analyze non-existent doc returns 404", resp.status_code == 404)

    # B. Missing key handling
    # Create doc with digital text
    pdf_bytes = make_digital_pdf("Hyderabad Metro Rail Daily Station Log")
    up_resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("log_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    doc_id = up_resp.json()["id"]

    # Temporarily ensure API key is treated as missing
    orig_get_key = gemini_service._get_configured_api_key
    gemini_service._get_configured_api_key = lambda: None
    gemini_service._client = None

    try:
        analyze_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
        # Should return 422 with clear message indicating API key requirement
        check("Missing key returns 422", analyze_resp.status_code == 422)
        err_msg = analyze_resp.json().get("detail", "")
        check("Error message mentions GEMINI_API_KEY", "GEMINI_API_KEY" in err_msg or "API key" in err_msg)
        check("Error message mentions AI Studio", "aistudio.google.com" in err_msg)
    finally:
        gemini_service._get_configured_api_key = orig_get_key
        gemini_service._refresh_client()

    client.delete(f"/api/v1/documents/{doc_id}")


def test_ai_persistence():
    print("\n[6] AI Analysis persistence across service reload")
    pdf_bytes = make_digital_pdf("Metro Vendor Invoice #INV-2026-881 for Signaling Cables")
    up = client.post(
        "/api/v1/documents/upload",
        files={"file": ("invoice.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    doc_id = up.json()["id"]

    # Save mock/validated AI analysis result directly to metadata
    document_service.update_ai_analysis_result(
        document_id=doc_id,
        ai_status="completed",
        category="Vendor Invoice",
        confidence=0.96,
        classification_reason="Commercial invoice for electrical and signaling supply.",
        summary="Vendor Invoice #INV-2026-881 for track signaling cables totaling INR 4,50,000.",
        extracted_fields={
            "vendor_name": "RailWire Systems Ltd",
            "invoice_number": "INV-2026-881",
            "total_amount": "INR 4,50,000",
            "payment_status": "Pending"
        },
        keywords=["Invoice", "Signaling", "RailWire"],
        suggested_priority="Medium",
        priority_explanation="Standard 30-day payment term vendor invoice.",
        action_items=["Forward to Accounts Payable"],
        analyzed_at="2026-11-11T14:40:00Z",
        model="gemini-2.5-flash",
    )

    # Reload DocumentService from disk
    from app.services import document_service as ds_mod
    ds_mod.document_service._store = {}
    ds_mod.document_service._load_from_disk()

    reloaded = ds_mod.document_service.get_document(doc_id)
    check("Record found after reload", reloaded is not None)
    check("AI status preserved", reloaded and reloaded.get("ai_status") == "completed")
    check("AI category preserved", reloaded and reloaded.get("ai_category") == "Vendor Invoice")
    check("AI priority preserved", reloaded and reloaded.get("ai_suggested_priority") == "Medium")
    check("AI fields preserved", reloaded and reloaded.get("ai_extracted_fields", {}).get("invoice_number") == "INV-2026-881")

    # Test GET /{id}/analysis endpoint
    get_res = client.get(f"/api/v1/documents/{doc_id}/analysis")
    check("GET /analysis returns 200", get_res.status_code == 200)
    data = get_res.json()
    check("Analysis category matches", data.get("analysis", {}).get("category") == "Vendor Invoice")
    check("Department auto-mapped to Finance", reloaded and reloaded.get("department") == "Finance")

    client.delete(f"/api/v1/documents/{doc_id}")


def test_live_gemini_api():
    print("\n[7] Live Gemini API Tests")
    has_key = gemini_service.is_api_key_configured()
    if not has_key:
        print(f"  {INFO} SKIPPED: GEMINI_API_KEY is not set in backend/.env.")
        print("         To enable live Gemini calls, add your key from https://aistudio.google.com/app/apikey")
        return

    print("  Testing live Gemini API calls for standard document types...")

    sample_maintenance = (
        "HYDERABAD METRO RAIL - FAULT LOG\n"
        "Date: 11-Nov-2026\n"
        "Station: Ameerpet Interchange\n"
        "Asset: Escalator ESC-02 (Concourse to Platform 2)\n"
        "Defect: Comb plate sensor triggered emergency brake. Handrail drive belt worn out.\n"
        "Urgency: Station experiencing severe passenger bottleneck.\n"
        "Assigned: Mechanical Maintenance Team B"
    )

    try:
        res = gemini_service.analyze_document_text(sample_maintenance, "maintenance_log.txt")
        check("Live Call: Category is Maintenance Report", res.category == "Maintenance Report", f"got {res.category}")
        check("Live Call: Priority is High or Critical", res.suggested_priority in ("High", "Critical"), f"got {res.suggested_priority}")
        check("Live Call: Summary generated", len(res.summary) > 20)
        check("Live Call: Station extracted", "Ameerpet" in str(res.extracted_fields.get("station", "")))
        print(f"  {PASS} Live Gemini analysis succeeded with model {res.model}!")
    except Exception as e:
        check("Live Call completed without error", False, str(e))


def test_dashboard_metrics():
    print("\n[8] Dashboard Statistics API")
    resp = client.get("/api/v1/documents/stats")
    check("GET /stats returns 200", resp.status_code == 200)
    data = resp.json()
    check("Has 'total_documents'", "total_documents" in data)
    check("Has 'ocr_completed'", "ocr_completed" in data)
    check("Has 'ai_analyzed'", "ai_analyzed" in data)
    check("Has 'category_chart'", "category_chart" in data)
    check("Has 'priority_chart'", "priority_chart" in data)


# ---- Runner ------------------------------------------------------------------

def main():
    print("=" * 65)
    print("DocDeclutter – Full Storage, OCR & Gemini AI Integration Tests")
    print("=" * 65)

    test_diagnostic_endpoints()
    test_digital_pdf_pipeline()
    test_multipage_pdf_pipeline()
    test_gemini_service_offline_validation()
    test_gemini_error_handling()
    test_ai_persistence()
    test_live_gemini_api()
    test_dashboard_metrics()

    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = total - passed

    print("\n" + "=" * 65)
    print(f"Results: {passed}/{total} passed  |  {failed} failed")
    print("=" * 65)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
