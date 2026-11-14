"""
Document service – orchestrates upload, storage, and retrieval.
Phase 1: Saves actual files to the local filesystem (backend/uploads/)
         and persists metadata to backend/data/documents.json.
         Fully synchronous; no asyncio required.
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.schemas.document import DocumentStatus
from app.services.supabase_service import supabase_service

logger = logging.getLogger("docdeclutter.service")


class DocumentService:
    def __init__(
        self,
        storage_file: str = "data/documents.json",
        upload_dir: str = "uploads",
    ):
        self.storage_file = storage_file
        self.upload_dir = upload_dir
        self._store: Dict[str, dict] = {}

        # Ensure directories exist on startup
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.storage_file) or ".", exist_ok=True)

        self._load_from_disk()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_from_disk(self):
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    self._store = json.load(f)
        except Exception:
            self._store = {}

    def _save_to_disk(self):
        try:
            os.makedirs(os.path.dirname(self.storage_file) or ".", exist_ok=True)
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self._store, f, indent=2)
        except Exception:
            pass

    @staticmethod
    def _safe_filename(filename: str) -> str:
        """
        Sanitise the original filename to prevent path traversal and
        remove characters that cause issues on Windows/Linux filesystems.
        Returns just the basename with unsafe chars replaced by underscores.
        """
        # Strip directory components
        name = os.path.basename(filename)
        # Replace anything that isn't alphanumeric, dash, dot, or underscore
        name = re.sub(r"[^\w\-.]", "_", name)
        # Collapse multiple underscores
        name = re.sub(r"_+", "_", name)
        return name or "document"

    def _resolve_upload_path(self, stored_filename: str) -> str:
        """
        Return the absolute path for a stored file, verifying it stays
        inside upload_dir (path traversal protection).
        """
        base = os.path.realpath(self.upload_dir)
        target = os.path.realpath(os.path.join(self.upload_dir, stored_filename))
        if not target.startswith(base + os.sep) and target != base:
            raise ValueError("Path traversal detected.")
        return target

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_document_with_file(
        self,
        filename: str,
        content_type: str,
        file_size: int,
        file_bytes: bytes,
    ) -> dict:
        """
        Persist the uploaded file to disk and store its metadata.
        Returns the metadata record dict.
        """
        doc_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        task_id = f"task-{doc_id[:8]}"

        # Determine extension from original filename
        safe_name = self._safe_filename(filename)
        _, ext = os.path.splitext(safe_name)
        ext = ext.lower()  # e.g. ".pdf"

        # Unique stored filename: <uuid>_<safe_original>
        stored_filename = f"{doc_id}_{safe_name}"

        # Write file bytes to disk
        abs_path = self._resolve_upload_path(stored_filename)
        with open(abs_path, "wb") as fh:
            fh.write(file_bytes)

        # Relative path stored in metadata (portable across OS)
        relative_path = os.path.join(self.upload_dir, stored_filename).replace("\\", "/")
        storage_path = f"documents/{doc_id}/{stored_filename}"

        record = {
            "id": doc_id,
            "filename": filename,          # original name shown to user
            "stored_filename": stored_filename,
            "file_extension": ext,
            "content_type": content_type,
            "file_size": file_size,
            "file_path": relative_path,    # relative to backend working dir
            "storage_path": storage_path,  # Supabase Storage path
            "status": DocumentStatus.PENDING.value,
            "department": None,
            "priority": None,
            "summary": None,
            "extracted_text": None,
            "extraction_status": "pending",
            "extraction_method": None,
            "page_count": None,
            "extracted_text_path": None,
            "extracted_at": None,
            "error_message": None,
            # AI Analysis fields
            "ai_status": "pending",
            "ai_category": None,
            "ai_confidence": None,
            "ai_classification_reason": None,
            "ai_summary": None,
            "ai_extracted_fields": None,
            "ai_keywords": None,
            "ai_suggested_priority": None,
            "ai_priority_explanation": None,
            "ai_action_items": None,
            "ai_analyzed_at": None,
            "ai_model": None,
            "ai_error_message": None,
            "created_at": now,
            "processed_at": None,
            "task_id": task_id,
        }

        self._store[doc_id] = record
        self._save_to_disk()

        # Cloud upload & database sync if Supabase is configured
        if supabase_service.is_configured():
            try:
                supabase_service.ensure_bucket_exists()
                supabase_service.upload_storage_file(
                    storage_path=storage_path,
                    file_bytes=file_bytes,
                    content_type=content_type,
                )
                supabase_service.insert_document_record(record)
                logger.info("Synchronized uploaded document %s with Supabase.", doc_id)
            except Exception as e:
                logger.warning("Supabase upload/insert fallback to local for %s: %s", doc_id, e)

        return record

    def get_document(self, document_id: str) -> Optional[dict]:
        if supabase_service.is_configured():
            try:
                cloud_record = supabase_service.get_document_record(document_id)
                if cloud_record:
                    self._store[document_id] = cloud_record
                    return cloud_record
            except Exception as e:
                logger.warning("Supabase get_document error for %s (using local): %s", document_id, e)
        return self._store.get(document_id)

    def list_documents(self) -> List[dict]:
        if supabase_service.is_configured():
            try:
                cloud_docs = supabase_service.list_document_records()
                if cloud_docs is not None and len(cloud_docs) > 0:
                    for doc in cloud_docs:
                        self._store[doc["id"]] = doc
                    return cloud_docs
            except Exception as e:
                logger.warning("Supabase list_documents error (using local): %s", e)

        docs = list(self._store.values())
        docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
        return docs

    def update_extraction_result(
        self,
        document_id: str,
        extraction_status: str,
        text: Optional[str] = None,
        page_count: Optional[int] = None,
        extraction_method: Optional[str] = None,
        extracted_text_path: Optional[str] = None,
        extracted_at: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[dict]:
        """Update extraction results for a document and persist to disk."""
        record = self._store.get(document_id)
        if not record:
            return None

        record["extraction_status"] = extraction_status
        record["extraction_method"] = extraction_method
        record["page_count"] = page_count
        record["extracted_text_path"] = extracted_text_path
        record["extracted_text"] = text
        record["extracted_at"] = extracted_at
        record["error_message"] = error_message

        if extraction_status == "completed":
            record["status"] = DocumentStatus.COMPLETED.value
            record["processed_at"] = extracted_at or datetime.now(timezone.utc).isoformat()
        elif extraction_status == "failed":
            record["status"] = DocumentStatus.FAILED.value
        elif extraction_status == "processing":
            record["status"] = DocumentStatus.PROCESSING.value

        self._save_to_disk()

        # Update cloud record if Supabase is configured
        if supabase_service.is_configured():
            try:
                if text:
                    text_storage_path = f"extracted_text/{document_id}.txt"
                    supabase_service.upload_storage_file(
                        storage_path=text_storage_path,
                        file_bytes=text.encode("utf-8"),
                        content_type="text/plain",
                    )
                supabase_service.update_document_record(document_id, record)
            except Exception as e:
                logger.warning("Supabase update_extraction_result notice for %s: %s", document_id, e)

        return record

    def update_ai_analysis_result(
        self,
        document_id: str,
        ai_status: str,
        category: Optional[str] = None,
        confidence: Optional[float] = None,
        classification_reason: Optional[str] = None,
        summary: Optional[str] = None,
        extracted_fields: Optional[dict] = None,
        keywords: Optional[list] = None,
        suggested_priority: Optional[str] = None,
        priority_explanation: Optional[str] = None,
        action_items: Optional[list] = None,
        analyzed_at: Optional[str] = None,
        model: Optional[str] = None,
        error_message: Optional[str] = None,
        review_status: Optional[str] = None,
        review_reasons: Optional[list] = None,
        reviewer_notes: Optional[str] = None,
        reviewed_at: Optional[str] = None,
        routing: Optional[dict] = None,
        workflow_history: Optional[list] = None,
        target_department: Optional[str] = None,
    ) -> Optional[dict]:
        """Update AI analysis results for a document and persist to disk."""
        record = self._store.get(document_id)
        if not record:
            return None

        record["ai_status"] = ai_status
        record["ai_category"] = category
        record["ai_confidence"] = confidence
        record["ai_classification_reason"] = classification_reason
        record["ai_summary"] = summary
        record["ai_extracted_fields"] = extracted_fields
        record["ai_keywords"] = keywords
        record["ai_suggested_priority"] = suggested_priority
        record["ai_priority_explanation"] = priority_explanation
        record["ai_action_items"] = action_items
        record["ai_analyzed_at"] = analyzed_at
        record["ai_model"] = model
        record["ai_error_message"] = error_message

        # Agentic AI & Human Review fields
        if review_status is not None:
            record["ai_review_status"] = review_status
        if review_reasons is not None:
            record["ai_review_reasons"] = review_reasons
        if reviewer_notes is not None:
            record["ai_reviewer_notes"] = reviewer_notes
        if reviewed_at is not None:
            record["ai_reviewed_at"] = reviewed_at
        if routing is not None:
            record["ai_routing"] = routing
        if workflow_history is not None:
            record["ai_workflow_history"] = workflow_history

        # Sync top-level summary if available
        if summary:
            record["summary"] = summary

        # Sync top-level priority with suggested_priority
        if suggested_priority:
            record["priority"] = suggested_priority

        # Set or infer department
        if target_department:
            record["department"] = target_department
        elif routing and routing.get("target_department"):
            record["department"] = routing["target_department"]
        elif category and not record.get("department"):
            cat_dept_map = {
                "Maintenance Report": "Technical",
                "Safety Inspection Report": "Safety",
                "Incident Report": "Operations",
                "Employee Application": "Human Resources",
                "Vendor Invoice": "Finance",
                "Passenger Complaint": "Operations",
                "Other": "Administration",
            }
            if category in cat_dept_map:
                record["department"] = cat_dept_map[category]

        self._save_to_disk()

        # Update cloud record if Supabase is configured
        if supabase_service.is_configured():
            try:
                supabase_service.update_document_record(document_id, record)
            except Exception as e:
                logger.warning("Supabase update_ai_analysis_result notice for %s: %s", document_id, e)

        return record

    def apply_human_review_decision(
        self,
        document_id: str,
        decision: str,
        notes: str = "",
        target_department: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> Optional[dict]:
        """Apply an approved or rejected human review decision to a document."""
        record = self._store.get(document_id)
        if not record:
            return None
        now = datetime.now(timezone.utc).isoformat()
        record["ai_review_status"] = decision
        record["ai_reviewer_notes"] = notes
        record["ai_reviewed_at"] = now
        if target_department:
            record["department"] = target_department
            if "ai_routing" in record and isinstance(record["ai_routing"], dict):
                record["ai_routing"]["target_department"] = target_department
        if priority:
            record["ai_suggested_priority"] = priority
            record["priority"] = priority

        # Append to workflow history
        history = record.get("ai_workflow_history") or []
        history.append({
            "agent": "Human Review Decision Node",
            "action": f"decision_{decision}",
            "notes": notes,
            "department": target_department or record.get("department"),
            "priority": priority or record.get("ai_suggested_priority"),
            "timestamp": now,
        })
        record["ai_workflow_history"] = history
        self._save_to_disk()

        # Update cloud record if Supabase is configured
        if supabase_service.is_configured():
            try:
                supabase_service.update_document_record(document_id, record)
            except Exception as e:
                logger.warning("Supabase update_ai_analysis_result notice for %s: %s", document_id, e)

        return record

    def delete_document(self, document_id: str) -> bool:
        """
        Remove a document's metadata, its uploaded file, and its extracted text file.
        Returns True if the document existed, False otherwise.
        """
        record = self._store.get(document_id)
        if record is None:
            return False

        # Remove uploaded file from disk if it exists
        stored_filename = record.get("stored_filename")
        if stored_filename:
            try:
                abs_path = self._resolve_upload_path(stored_filename)
                if os.path.exists(abs_path):
                    os.remove(abs_path)
            except Exception:
                pass

        # Remove extracted text file from disk if it exists
        extracted_path = record.get("extracted_text_path")
        if extracted_path and os.path.exists(extracted_path):
            try:
                os.remove(extracted_path)
            except Exception:
                pass

        # Remove metadata from local store
        del self._store[document_id]
        self._save_to_disk()

        # Delete from Supabase Storage and PostgreSQL if configured
        if supabase_service.is_configured():
            try:
                storage_path = record.get("storage_path") or f"documents/{document_id}/{stored_filename}"
                supabase_service.delete_storage_file(storage_path)
                supabase_service.delete_storage_file(f"extracted_text/{document_id}.txt")
                supabase_service.delete_document_record(document_id)
                logger.info("Deleted document %s from Supabase Storage and PostgreSQL.", document_id)
            except Exception as e:
                logger.warning("Supabase delete_document error for %s: %s", document_id, e)

        return True

    def get_stats(self) -> dict:
        docs = self.list_documents()
        total = len(docs)
        today = datetime.now(timezone.utc).date().isoformat()

        processed_today = sum(
            1 for d in docs
            if (d.get("created_at") or "").startswith(today)
            and d.get("status") == DocumentStatus.COMPLETED.value
        )
        pending = sum(
            1 for d in docs
            if d.get("status") == DocumentStatus.PENDING.value
        )

        ocr_completed = sum(
            1 for d in docs
            if d.get("extraction_status") == "completed" or d.get("extracted_text")
        )

        ai_analyzed = sum(
            1 for d in docs
            if d.get("ai_status") == "completed"
        )

        pending_ai = sum(
            1 for d in docs
            if d.get("ai_status") in ("pending", "processing") or not d.get("ai_status")
        )

        departments = {d["department"] for d in docs if d.get("department")}

        dept_map = {
            "OPS": 0, "HR": 0, "FIN": 0, "TECH": 0, "SAFE": 0,
            "LEGAL": 0, "ADMIN": 0,
        }
        full_to_abbr = {
            "Operations": "OPS",
            "Human Resources": "HR",
            "Finance": "FIN",
            "Technical": "TECH",
            "Safety": "SAFE",
            "Legal": "LEGAL",
            "Administration": "ADMIN",
        }
        for d in docs:
            dept = d.get("department")
            abbr = full_to_abbr.get(dept, dept)
            if abbr in dept_map:
                dept_map[abbr] += 1

        chart_data = [{"dept": k, "docs": v} for k, v in dept_map.items()]

        # Category distribution
        category_map = {
            "Maintenance Report": 0,
            "Safety Inspection Report": 0,
            "Incident Report": 0,
            "Vendor Invoice": 0,
            "Passenger Complaint": 0,
            "Employee Application": 0,
            "Other": 0,
        }
        for d in docs:
            cat = d.get("ai_category")
            if cat in category_map:
                category_map[cat] += 1
            elif cat:
                category_map["Other"] += 1

        category_chart = [{"category": k, "count": v} for k, v in category_map.items()]

        # Priority distribution
        priority_map = {
            "Critical": 0,
            "High": 0,
            "Medium": 0,
            "Low": 0,
        }
        for d in docs:
            pri = d.get("ai_suggested_priority")
            if pri in priority_map:
                priority_map[pri] += 1

        priority_chart = [{"priority": k, "count": v} for k, v in priority_map.items()]

        return {
            "total_documents": total,
            "processed_today": processed_today,
            "pending_review": pending,
            "ocr_completed": ocr_completed,
            "ai_analyzed": ai_analyzed,
            "pending_ai": pending_ai,
            "departments_active": len(departments),
            "chart_data": chart_data,
            "category_chart": category_chart,
            "priority_chart": priority_chart,
        }


# Singleton service instance
document_service = DocumentService()
