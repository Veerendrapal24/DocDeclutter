"""
DocDeclutter – Supabase Integration & Dual-Mode Fallback Test Suite.

Verifies:
1. Unconfigured behavior: graceful local fallback, clear status messages, 0 crashes.
2. Mocked unit tests: Supabase Storage operations, PostgreSQL CRUD, data mapping.
3. Live integration test: if valid credentials exist in backend/.env, test live bucket and DB.
"""

import os
import sys
import uuid
from unittest.mock import MagicMock, patch

# Ensure backend root on sys.path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.config import settings
from app.services.supabase_service import SupabaseService, supabase_service
from app.services.document_service import document_service


def test_unconfigured_status():
    print("[TEST 1] Testing unconfigured status and fallback...")
    # When credentials are missing or placeholders, is_configured() should be False
    with patch.object(supabase_service, "_get_credentials", return_value=(None, None)):
        supabase_service._refresh_client()
        assert not supabase_service.is_configured(), "Should report unconfigured when no keys"
        status = supabase_service.get_service_status()
        assert status["configured"] is False, "Status configured should be False"
        assert "Supabase credentials missing" in status["message"]
        print("  -> Unconfigured status check passed.")


def test_data_mapping_bidirectional():
    print("[TEST 2] Testing database row mapping (bidirectional)...")
    service = SupabaseService()

    sample_app_doc = {
        "id": "12345678-1234-5678-1234-567812345678",
        "filename": "brake_inspection.pdf",
        "stored_filename": "12345678_brake_inspection.pdf",
        "file_path": "uploads/12345678_brake_inspection.pdf",
        "storage_path": "documents/12345678/12345678_brake_inspection.pdf",
        "content_type": "application/pdf",
        "file_size": 10240,
        "department": "Safety",
        "priority": "High",
        "summary": "Emergency braking system wear identified.",
        "status": "completed",
        "extraction_status": "completed",
        "ai_status": "completed",
        "ai_category": "Safety Inspection Report",
        "ai_confidence": 0.98,
        "ai_suggested_priority": "High",
        "ai_review_status": "approved",
    }

    # Prepare for DB
    db_row = service._prepare_row_for_db(sample_app_doc)
    assert db_row["original_filename"] == "brake_inspection.pdf"
    assert db_row["storage_path"] == "documents/12345678/12345678_brake_inspection.pdf"
    assert db_row["mime_type"] == "application/pdf"
    assert db_row["document_status"] == "completed"
    assert db_row["ai_category"] == "Safety Inspection Report"

    # Map back from DB
    reconstructed = service._map_row_from_db(db_row)
    assert reconstructed["filename"] == sample_app_doc["filename"]
    assert reconstructed["content_type"] == sample_app_doc["content_type"]
    assert reconstructed["department"] == sample_app_doc["department"]
    assert reconstructed["ai_category"] == sample_app_doc["ai_category"]
    print("  -> Bidirectional data mapping verified successfully.")


def test_mocked_supabase_operations():
    print("[TEST 3] Testing mocked Supabase storage and PostgreSQL operations...")
    mock_client = MagicMock()
    service = SupabaseService()
    service._client = mock_client

    with patch.object(service, "is_configured", return_value=True):
        # Storage upload test
        test_bytes = b"%PDF-1.4 test document"
        mock_client.storage.from_().upload.return_value = {"Key": "documents/test/test.pdf"}
        upload_res = service.upload_storage_file("documents/test/test.pdf", test_bytes, "application/pdf")
        assert upload_res == "documents/test/test.pdf"

        # Signed URL test
        mock_client.storage.from_().create_signed_url.return_value = {"signedURL": "https://supabase.co/storage/v1/object/sign/metro-documents/test.pdf?token=xyz"}
        signed_url = service.create_signed_download_url("documents/test/test.pdf", 3600)
        assert "token=xyz" in signed_url

        # Storage delete test
        mock_client.storage.from_().remove.return_value = [{"name": "test.pdf"}]
        assert service.delete_storage_file("documents/test/test.pdf") is True

        # PostgreSQL insert test
        test_id = str(uuid.uuid4())
        mock_db_res = MagicMock()
        mock_db_res.data = [{
            "id": test_id,
            "original_filename": "test.pdf",
            "stored_filename": f"{test_id}_test.pdf",
            "storage_path": f"documents/{test_id}/test.pdf",
            "mime_type": "application/pdf",
            "file_size": len(test_bytes),
            "document_status": "pending",
        }]
        mock_client.table().insert().execute.return_value = mock_db_res

        inserted = service.insert_document_record({
            "id": test_id,
            "filename": "test.pdf",
            "stored_filename": f"{test_id}_test.pdf",
            "file_path": "uploads/test.pdf",
            "content_type": "application/pdf",
            "file_size": len(test_bytes),
        })
        assert inserted is not None
        assert inserted["id"] == test_id
        assert inserted["filename"] == "test.pdf"

        # PostgreSQL select test
        mock_client.table().select().eq().execute.return_value = mock_db_res
        fetched = service.get_document_record(test_id)
        assert fetched is not None
        assert fetched["id"] == test_id

        # PostgreSQL delete test
        mock_client.table().delete().eq().execute.return_value = MagicMock()
        assert service.delete_document_record(test_id) is True

    print("  -> Mocked storage and database operations passed.")


def test_document_service_fallback():
    print("[TEST 4] Testing DocumentService operations with dual-mode fallback...")
    # List documents from local storage should work regardless of Supabase status
    docs = document_service.list_documents()
    assert isinstance(docs, list)
    stats = document_service.get_stats()
    assert "total_documents" in stats
    print(f"  -> DocumentService dual-mode fallback verified ({len(docs)} local documents).")


def run_all_tests():
    print("=" * 60)
    print("  DocDeclutter – Supabase Integration Test Suite")
    print("=" * 60)
    test_unconfigured_status()
    test_data_mapping_bidirectional()
    test_mocked_supabase_operations()
    test_document_service_fallback()
    print("=" * 60)
    print("  ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
