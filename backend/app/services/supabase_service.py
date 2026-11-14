"""
DocDeclutter – Supabase Cloud Storage & Database Service.
Uses the official Supabase Python SDK to interact with:
1. Supabase Storage (Private 'metro-documents' bucket)
2. Supabase PostgreSQL ('documents' table)
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from supabase import Client, create_client

from app.core.config import settings

logger = logging.getLogger("docdeclutter.supabase")


class SupabaseService:
    def __init__(self):
        self._client: Optional[Client] = None
        self._url: Optional[str] = None
        self._key: Optional[str] = None
        self._bucket: str = getattr(settings, "supabase_bucket", "metro-documents") or "metro-documents"
        self._refresh_client()

    def _get_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """Retrieve Supabase URL and Key from settings or environment."""
        url = getattr(settings, "supabase_url", None) or os.environ.get("SUPABASE_URL")
        # Prefer service role key for backend administrative access, fallback to anon or general key
        key = (
            getattr(settings, "supabase_service_role_key", None)
            or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
            or getattr(settings, "supabase_anon_key", None)
            or os.environ.get("SUPABASE_ANON_KEY")
            or getattr(settings, "supabase_key", None)
            or os.environ.get("SUPABASE_KEY")
        )
        url_clean = url.strip() if url and url.strip() and not url.strip().startswith("https://your-project") else None
        key_clean = key.strip() if key and key.strip() and not key.strip().startswith("your_") else None
        return url_clean, key_clean

    def _refresh_client(self):
        url, key = self._get_credentials()
        self._url = url
        self._key = key
        self._bucket = getattr(settings, "supabase_bucket", "metro-documents") or "metro-documents"

        if url and key:
            try:
                self._client = create_client(url, key)
                logger.info("Supabase client initialized successfully.")
            except Exception as e:
                logger.error("Failed to initialize Supabase client: %s", e)
                self._client = None
        else:
            self._client = None

    def is_configured(self) -> bool:
        """Check if valid Supabase credentials are configured."""
        self._refresh_client()
        return self._client is not None

    def get_service_status(self) -> Dict[str, Any]:
        """Diagnostic status for healthcheck and settings inspection."""
        configured = self.is_configured()
        url, _ = self._get_credentials()
        return {
            "configured": configured,
            "url": url if url else None,
            "bucket": self._bucket,
            "provider": "supabase-cloud",
            "message": "Supabase Cloud Storage & Database connected."
            if configured
            else "Supabase credentials missing. Enter SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in backend/.env",
        }

    # ------------------------------------------------------------------
    # Storage Operations (Private 'metro-documents' bucket)
    # ------------------------------------------------------------------

    def ensure_bucket_exists(self) -> bool:
        """Verify or create the private 'metro-documents' bucket."""
        if not self.is_configured():
            return False
        try:
            buckets = self._client.storage.list_buckets()
            existing = [b.name for b in buckets] if buckets else []
            if self._bucket not in existing:
                self._client.storage.create_bucket(
                    self._bucket,
                    options={
                        "public": False,
                        "file_size_limit": 10485760,  # 10 MB
                        "allowed_mime_types": [
                            "application/pdf",
                            "image/png",
                            "image/jpeg",
                            "image/jpg",
                            "text/plain",
                        ],
                    },
                )
                logger.info("Created private Supabase Storage bucket: %s", self._bucket)
            return True
        except Exception as e:
            logger.warning("Bucket verification notice: %s", e)
            return True

    def upload_storage_file(
        self,
        storage_path: str,
        file_bytes: bytes,
        content_type: str = "application/pdf",
    ) -> Optional[str]:
        """
        Upload binary data to the private Supabase Storage bucket.
        Returns the storage path on success.
        """
        if not self.is_configured():
            return None
        try:
            self._client.storage.from_(self._bucket).upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": content_type, "upsert": "true"},
            )
            return storage_path
        except Exception as e:
            logger.error("Supabase storage upload failed for %s: %s", storage_path, e)
            raise e

    def download_storage_file(self, storage_path: str) -> Optional[bytes]:
        """Download binary content from private Supabase Storage bucket."""
        if not self.is_configured():
            return None
        try:
            data = self._client.storage.from_(self._bucket).download(storage_path)
            return data
        except Exception as e:
            logger.error("Supabase storage download failed for %s: %s", storage_path, e)
            return None

    def create_signed_download_url(self, storage_path: str, expires_in: int = 3600) -> Optional[str]:
        """Generate a time-limited signed download URL for private documents."""
        if not self.is_configured():
            return None
        try:
            res = self._client.storage.from_(self._bucket).create_signed_url(
                path=storage_path,
                expires_in=expires_in,
            )
            if isinstance(res, dict) and "signedURL" in res:
                return res["signedURL"]
            elif hasattr(res, "signed_url"):
                return res.signed_url
            return None
        except Exception as e:
            logger.error("Failed to generate signed URL for %s: %s", storage_path, e)
            return None

    def delete_storage_file(self, storage_path: str) -> bool:
        """Delete an object from the private Supabase Storage bucket."""
        if not self.is_configured():
            return False
        try:
            self._client.storage.from_(self._bucket).remove([storage_path])
            return True
        except Exception as e:
            logger.warning("Supabase storage file removal error for %s: %s", storage_path, e)
            return False

    # ------------------------------------------------------------------
    # Database Operations ('documents' table in PostgreSQL)
    # ------------------------------------------------------------------

    def insert_document_record(self, doc_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Insert a document record into the PostgreSQL 'documents' table."""
        if not self.is_configured():
            return None
        try:
            # Prepare data conforming to PostgreSQL table column names
            row = self._prepare_row_for_db(doc_data)
            res = self._client.table("documents").insert(row).execute()
            if res.data and len(res.data) > 0:
                return self._map_row_from_db(res.data[0])
            return None
        except Exception as e:
            logger.error("Failed to insert document into Supabase PostgreSQL: %s", e)
            raise e

    def get_document_record(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single document metadata record from PostgreSQL."""
        if not self.is_configured():
            return None
        try:
            res = self._client.table("documents").select("*").eq("id", doc_id).execute()
            if res.data and len(res.data) > 0:
                return self._map_row_from_db(res.data[0])
            return None
        except Exception as e:
            logger.error("Failed to fetch document %s from Supabase: %s", doc_id, e)
            return None

    def list_document_records(self) -> List[Dict[str, Any]]:
        """List all documents from PostgreSQL ordered by created_at descending."""
        if not self.is_configured():
            return []
        try:
            res = self._client.table("documents").select("*").order("created_at", desc=True).execute()
            if res.data:
                return [self._map_row_from_db(r) for r in res.data]
            return []
        except Exception as e:
            logger.error("Failed to list documents from Supabase: %s", e)
            return []

    def update_document_record(self, doc_id: str, update_fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update metadata fields for a document in PostgreSQL."""
        if not self.is_configured():
            return None
        try:
            row = self._prepare_row_for_db(update_fields, is_update=True)
            res = self._client.table("documents").update(row).eq("id", doc_id).execute()
            if res.data and len(res.data) > 0:
                return self._map_row_from_db(res.data[0])
            return None
        except Exception as e:
            logger.error("Failed to update document %s in Supabase: %s", doc_id, e)
            return None

    def delete_document_record(self, doc_id: str) -> bool:
        """Delete document record from PostgreSQL."""
        if not self.is_configured():
            return False
        try:
            self._client.table("documents").delete().eq("id", doc_id).execute()
            return True
        except Exception as e:
            logger.error("Failed to delete document %s from Supabase: %s", doc_id, e)
            return False

    # ------------------------------------------------------------------
    # Data Mapping Helpers (Pydantic / Frontend compatibility)
    # ------------------------------------------------------------------

    def _prepare_row_for_db(self, data: Dict[str, Any], is_update: bool = False) -> Dict[str, Any]:
        """Convert application document dict to PostgreSQL row fields."""
        row: Dict[str, Any] = {}
        mapping = {
            "id": "id",
            "filename": "original_filename",
            "stored_filename": "stored_filename",
            "storage_path": "storage_path",
            "content_type": "mime_type",
            "file_size": "file_size",
            "department": "department",
            "priority": "priority",
            "summary": "summary",
            "status": "document_status",
            "extraction_status": "extraction_status",
            "extraction_method": "extraction_method",
            "page_count": "page_count",
            "extracted_text_path": "extracted_text_path",
            "extracted_text": "extracted_text",
            "extracted_at": "extracted_at",
            "error_message": "error_message",
            "ai_status": "ai_status",
            "ai_category": "ai_category",
            "ai_confidence": "ai_confidence",
            "ai_classification_reason": "ai_classification_reason",
            "ai_summary": "ai_summary",
            "ai_extracted_fields": "ai_extracted_fields",
            "ai_keywords": "ai_keywords",
            "ai_suggested_priority": "ai_suggested_priority",
            "ai_priority_explanation": "ai_priority_explanation",
            "ai_action_items": "ai_action_items",
            "ai_model": "ai_model",
            "ai_analyzed_at": "ai_analyzed_at",
            "ai_error_message": "ai_error_message",
            "ai_review_status": "ai_review_status",
            "ai_review_reasons": "ai_review_reasons",
            "ai_reviewer_notes": "ai_reviewer_notes",
            "ai_reviewed_at": "ai_reviewed_at",
            "ai_routing": "ai_routing",
            "ai_workflow_history": "ai_workflow_history",
            "task_id": "task_id",
            "created_at": "created_at",
            "processed_at": "processed_at",
        }

        for app_k, db_k in mapping.items():
            if app_k in data:
                val = data[app_k]
                row[db_k] = val

        # Storage path fallback to file_path if not explicitly provided
        if "storage_path" not in row and "file_path" in data and data["file_path"]:
            row["storage_path"] = data["file_path"]

        # Handle priority sync
        if "ai_suggested_priority" in row and not row.get("priority"):
            row["priority"] = row["ai_suggested_priority"]

        # Ensure timestamps are ISO strings
        now_iso = datetime.now(timezone.utc).isoformat()
        if not is_update and "created_at" not in row:
            row["created_at"] = now_iso
        row["updated_at"] = now_iso

        return row

    def _map_row_from_db(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert PostgreSQL row back to application document dict format."""
        doc: Dict[str, Any] = {
            "id": str(row.get("id")),
            "filename": row.get("original_filename") or "",
            "stored_filename": row.get("stored_filename") or "",
            "file_path": row.get("storage_path") or "",
            "storage_path": row.get("storage_path") or "",
            "content_type": row.get("mime_type") or "application/pdf",
            "file_size": row.get("file_size") or 0,
            "department": row.get("department"),
            "priority": row.get("priority") or row.get("ai_suggested_priority"),
            "summary": row.get("summary") or row.get("ai_summary"),
            "status": row.get("document_status") or "pending",
            "extraction_status": row.get("extraction_status") or "pending",
            "extraction_method": row.get("extraction_method"),
            "page_count": row.get("page_count"),
            "extracted_text_path": row.get("extracted_text_path"),
            "extracted_text": row.get("extracted_text"),
            "extracted_at": row.get("extracted_at"),
            "error_message": row.get("error_message"),
            "ai_status": row.get("ai_status") or "pending",
            "ai_category": row.get("ai_category"),
            "ai_confidence": float(row["ai_confidence"]) if row.get("ai_confidence") is not None else None,
            "ai_classification_reason": row.get("ai_classification_reason"),
            "ai_summary": row.get("ai_summary"),
            "ai_extracted_fields": row.get("ai_extracted_fields") or {},
            "ai_keywords": row.get("ai_keywords") or [],
            "ai_suggested_priority": row.get("ai_suggested_priority") or row.get("priority"),
            "ai_priority_explanation": row.get("ai_priority_explanation"),
            "ai_action_items": row.get("ai_action_items") or [],
            "ai_model": row.get("ai_model"),
            "ai_analyzed_at": row.get("ai_analyzed_at"),
            "ai_error_message": row.get("ai_error_message"),
            "ai_review_status": row.get("ai_review_status") or "not_required",
            "ai_review_reasons": row.get("ai_review_reasons") or [],
            "ai_reviewer_notes": row.get("ai_reviewer_notes"),
            "ai_reviewed_at": row.get("ai_reviewed_at"),
            "ai_routing": row.get("ai_routing") or {},
            "ai_workflow_history": row.get("ai_workflow_history") or [],
            "task_id": row.get("task_id"),
            "created_at": row.get("created_at"),
            "processed_at": row.get("processed_at"),
        }
        return doc


# Singleton instance
supabase_service = SupabaseService()
