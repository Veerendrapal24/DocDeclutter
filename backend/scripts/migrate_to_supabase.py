"""
DocDeclutter – Safe Supabase Cloud Migration Script.

Migrates existing local files from:
- backend/uploads/ -> Supabase Storage ('metro-documents' private bucket)
- backend/extracted_text/ -> Supabase Storage ('metro-documents' private bucket)
- backend/data/documents.json -> Supabase PostgreSQL ('documents' table)

Safety Guarantees:
1. Creates an automated timestamped backup of documents.json before any operation.
2. Prevents duplicate migrations by verifying existing IDs in Supabase PostgreSQL.
3. Never deletes local files or local JSON records.
4. Provides clear progress logging and a detailed final migration report.
"""

import json
import os
import shutil
import sys
from datetime import datetime, timezone

# Ensure project root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.config import settings
from app.services.supabase_service import supabase_service


def run_migration():
    print("=" * 70)
    print("  DocDeclutter – Supabase Cloud Migration Utility")
    print("=" * 70)

    # 1. Verify Supabase configuration
    if not supabase_service.is_configured():
        print("\n[ERROR] Supabase credentials are not configured or invalid.")
        print("Please check your backend/.env file and ensure the following are set:")
        print("  SUPABASE_URL=https://<your-project-ref>.supabase.co")
        print("  SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>")
        print("\nTo obtain these credentials:")
        print("1. Go to your Supabase Dashboard: https://supabase.com/dashboard")
        print("2. Open your project -> Settings -> API")
        print("3. Copy 'Project URL' to SUPABASE_URL")
        print("4. Copy 'service_role' secret key to SUPABASE_SERVICE_ROLE_KEY")
        print("=" * 70)
        sys.exit(1)

    print("\n[OK] Connected to Supabase at:", getattr(settings, "supabase_url", None) or os.environ.get("SUPABASE_URL"))

    # 2. Verify / Ensure Bucket Exists
    print("[*] Verifying private Supabase Storage bucket 'metro-documents'...")
    supabase_service.ensure_bucket_exists()
    print("[OK] Supabase Storage bucket ready.")

    # 3. Locate documents.json and create backup
    data_file = os.path.join(BACKEND_DIR, "data", "documents.json")
    if not os.path.exists(data_file):
        print(f"[NOTICE] No existing documents.json found at {data_file}. Nothing to migrate.")
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = f"{data_file}.bak.{timestamp}"
    shutil.copy2(data_file, backup_file)
    print(f"[OK] Created backup of metadata: {backup_file}")

    # 4. Load existing documents
    try:
        with open(data_file, "r", encoding="utf-8") as fh:
            documents_dict = json.load(fh)
    except Exception as e:
        print(f"[ERROR] Failed to read {data_file}: {e}")
        sys.exit(1)

    total_docs = len(documents_dict)
    print(f"\n[*] Found {total_docs} document(s) in local storage to process.\n")

    migrated_count = 0
    skipped_count = 0
    failed_count = 0
    errors = []

    uploads_dir = os.path.join(BACKEND_DIR, "uploads")
    extracted_text_dir = os.path.join(BACKEND_DIR, "extracted_text")

    for idx, (doc_id, doc_data) in enumerate(documents_dict.items(), start=1):
        filename = doc_data.get("filename") or "unknown"
        stored_filename = doc_data.get("stored_filename") or f"{doc_id}_{filename}"
        print(f"[{idx}/{total_docs}] Checking document {doc_id} ({filename})...")

        # 5. Check if document already exists in Supabase PostgreSQL
        try:
            existing_record = supabase_service.get_document_record(doc_id)
            if existing_record:
                print(f"    -> Already exists in Supabase. Skipping database insert.")
                skipped_count += 1
                continue
        except Exception as e:
            print(f"    [WARN] Notice checking Supabase record: {e}")

        # 6. Upload file to Supabase Storage if found locally
        storage_path = doc_data.get("storage_path") or f"documents/{doc_id}/{stored_filename}"
        local_file_path = os.path.join(uploads_dir, stored_filename)

        if os.path.exists(local_file_path):
            try:
                content_type = doc_data.get("content_type") or "application/pdf"
                with open(local_file_path, "rb") as fh:
                    file_bytes = fh.read()
                supabase_service.upload_storage_file(
                    storage_path=storage_path,
                    file_bytes=file_bytes,
                    content_type=content_type,
                )
                print(f"    -> Uploaded binary ({len(file_bytes)} bytes) to Supabase Storage: {storage_path}")
            except Exception as e:
                print(f"    [WARN] Failed uploading binary to storage: {e}")
        else:
            print(f"    [WARN] Local file not found at {local_file_path}, proceeding with metadata.")

        # 7. Upload extracted text file if exists
        local_txt_path = os.path.join(extracted_text_dir, f"{doc_id}.txt")
        if os.path.exists(local_txt_path):
            try:
                with open(local_txt_path, "r", encoding="utf-8", errors="ignore") as fh:
                    txt_content = fh.read()
                txt_storage_path = f"extracted_text/{doc_id}.txt"
                supabase_service.upload_storage_file(
                    storage_path=txt_storage_path,
                    file_bytes=txt_content.encode("utf-8"),
                    content_type="text/plain",
                )
                print(f"    -> Uploaded extracted text ({len(txt_content)} chars) to Supabase Storage.")
            except Exception as e:
                print(f"    [WARN] Failed uploading extracted text to storage: {e}")

        # 8. Insert metadata into Supabase PostgreSQL
        doc_data["storage_path"] = storage_path
        try:
            supabase_service.insert_document_record(doc_data)
            print(f"    -> Inserted metadata record into Supabase PostgreSQL.")
            migrated_count += 1
        except Exception as e:
            print(f"    [ERROR] Failed inserting record into Supabase PostgreSQL: {e}")
            failed_count += 1
            errors.append({"doc_id": doc_id, "filename": filename, "error": str(e)})

    # 9. Summary Report
    print("\n" + "=" * 70)
    print("  Supabase Migration Summary")
    print("=" * 70)
    print(f"  Total Local Documents Scanned : {total_docs}")
    print(f"  Successfully Migrated        : {migrated_count}")
    print(f"  Skipped (Already in Supabase) : {skipped_count}")
    print(f"  Failed                       : {failed_count}")
    print(f"  Local JSON Backup            : {backup_file}")
    print("=" * 70)

    if errors:
        print("\nFailed documents:")
        for err in errors:
            print(f"  - ID: {err['doc_id']} ({err['filename']}): {err['error']}")


if __name__ == "__main__":
    run_migration()
