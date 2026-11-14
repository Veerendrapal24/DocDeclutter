"""
DocDeclutter – Pre-Deployment Comprehensive Verification Script.

Tests all key application flows in local-only mode (without requiring Supabase):
1. Server startup & health endpoints (/, /api/health).
2. Diagnostic endpoints (/ocr-status, /ai-status, /supabase-status, /stats).
3. Document Upload (PDF & PNG).
4. Document Listing & Retrieval.
5. Text Extraction (PyMuPDF digital extraction).
6. File Download (local file streaming).
7. Document Deletion & Cleanup.
8. Persistence verification across simulated backend restart.
"""

import io
import json
import os
import sys

# Ensure backend directory is in path and working dir is backend
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

import fitz  # PyMuPDF
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.services.document_service import DocumentService, document_service

client = TestClient(app, raise_server_exceptions=False)

PASS = "[PASS]"
FAIL = "[FAIL]"

def make_digital_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

def make_image_png() -> bytes:
    img = Image.new("RGB", (100, 100), color=(73, 109, 137))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def run_audit():
    print("=" * 70)
    print("  DocDeclutter – Pre-Deployment Integration Audit")
    print("=" * 70)

    # 1. Health & Diagnostics
    print("\n[Step 1] Checking Core & Diagnostic Endpoints...")
    res = client.get("/")
    assert res.status_code == 200, f"Root returned {res.status_code}"
    print(f"  {PASS} Root '/' endpoint healthy: {res.json()}")

    res = client.get("/api/health")
    assert res.status_code == 200, f"Health returned {res.status_code}"
    print(f"  {PASS} '/api/health' endpoint healthy: {res.json()}")

    res = client.get("/api/v1/documents/ocr-status")
    assert res.status_code == 200
    print(f"  {PASS} OCR status endpoint: available={res.json().get('available')}")

    res = client.get("/api/v1/documents/ai-status")
    assert res.status_code == 200
    print(f"  {PASS} AI status endpoint: configured={res.json().get('configured')}, model={res.json().get('model')}")

    res = client.get("/api/v1/documents/supabase-status")
    assert res.status_code == 200
    print(f"  {PASS} Supabase status endpoint: configured={res.json().get('configured')} (Local fallback active)")

    res = client.get("/api/v1/documents/stats")
    assert res.status_code == 200
    print(f"  {PASS} Stats endpoint: total={res.json().get('total_documents')}")

    # 2. Upload Digital PDF
    print("\n[Step 2] Testing PDF Document Upload...")
    pdf_text = "METRO OPERATIONAL SAFETY REPORT\nLine: Blue Line\nStation: Central\nTrack 3 maintenance verified."
    pdf_bytes = make_digital_pdf(pdf_text)
    upload_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("audit_metro_report.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == 202, f"Upload failed: {upload_res.text}"
    pdf_doc = upload_res.json()
    pdf_id = pdf_doc["id"]
    print(f"  {PASS} PDF uploaded successfully (ID: {pdf_id})")

    # 3. Upload PNG Image
    print("\n[Step 3] Testing PNG Image Upload...")
    png_bytes = make_image_png()
    upload_png_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("audit_track_photo.png", png_bytes, "image/png")},
    )
    assert upload_png_res.status_code == 202, f"PNG Upload failed: {upload_png_res.text}"
    png_doc = upload_png_res.json()
    png_id = png_doc["id"]
    print(f"  {PASS} PNG uploaded successfully (ID: {png_id})")

    # 4. List Documents
    print("\n[Step 4] Testing Document Listing & Retrieval...")
    list_res = client.get("/api/v1/documents")
    assert list_res.status_code == 200
    docs = list_res.json()["documents"]
    doc_ids = [d["id"] for d in docs]
    assert pdf_id in doc_ids, "Uploaded PDF not in documents list"
    assert png_id in doc_ids, "Uploaded PNG not in documents list"
    print(f"  {PASS} Both uploaded files present in repository (total: {len(docs)})")

    get_res = client.get(f"/api/v1/documents/{pdf_id}")
    assert get_res.status_code == 200
    assert get_res.json()["filename"] == "audit_metro_report.pdf"
    print(f"  {PASS} Single document retrieval verified by ID")

    # 5. Extract Text (PyMuPDF)
    print("\n[Step 5] Testing Text Extraction...")
    ext_res = client.post(f"/api/v1/documents/{pdf_id}/extract")
    assert ext_res.status_code == 200
    ext_data = ext_res.json()
    assert ext_data["extraction_status"] == "completed"
    assert "METRO OPERATIONAL SAFETY REPORT" in ext_data["extracted_text"]
    print(f"  {PASS} Extraction endpoint completed with PyMuPDF: {len(ext_data['extracted_text'])} chars extracted")

    # 6. File Download
    print("\n[Step 6] Testing Document Download...")
    dl_res = client.get(f"/api/v1/documents/{pdf_id}/download")
    assert dl_res.status_code == 200
    assert dl_res.content == pdf_bytes
    print(f"  {PASS} PDF binary stream downloaded and validated (matches original bytes)")

    # 7. Document Deletion
    print("\n[Step 7] Testing Document Deletion...")
    del_res = client.delete(f"/api/v1/documents/{pdf_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True
    print(f"  {PASS} PDF successfully deleted")

    del_png_res = client.delete(f"/api/v1/documents/{png_id}")
    assert del_png_res.status_code == 200
    print(f"  {PASS} PNG successfully deleted")

    # Verify deleted
    assert client.get(f"/api/v1/documents/{pdf_id}").status_code == 404
    print(f"  {PASS} Deleted documents return 404 Not Found")

    # 8. Local Persistence Across Service Reload
    print("\n[Step 8] Verifying Local Storage & Reload Resilience...")
    temp_rec = document_service.save_document_with_file(
        filename="persistence_test.pdf",
        content_type="application/pdf",
        file_size=len(pdf_bytes),
        file_bytes=pdf_bytes,
    )
    temp_id = temp_rec["id"]

    # Instantiate fresh DocumentService simulating app reboot
    reloaded_service = DocumentService(
        storage_file=document_service.storage_file,
        upload_dir=document_service.upload_dir,
    )
    found_rec = reloaded_service.get_document(temp_id)
    assert found_rec is not None, "Document missing after reload!"
    assert found_rec["filename"] == "persistence_test.pdf"
    print(f"  {PASS} Persistence verified: reloaded metadata matches perfectly from documents.json")

    # Cleanup temp
    reloaded_service.delete_document(temp_id)
    print(f"  {PASS} Cleaned up temporary test document")

    print("\n" + "=" * 70)
    print("  ALL AUDIT WORKFLOW STEPS PASSED WITHOUT ERRORS!")
    print("=" * 70)

if __name__ == "__main__":
    run_audit()
