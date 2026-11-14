"""
Document upload & retrieval endpoints.
Phase 1: Local filesystem storage + JSON metadata persistence.
         Supports upload (PDF/PNG/JPG/JPEG), list, get by ID,
         download original file, and delete.
"""

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentListResponse,
    DocumentResult,
    DeleteResponse,
    TextExtractionResponse,
    DocumentTextResponse,
    DocumentAnalysisResponse,
    AIAnalysisResult,
    HumanReviewRequest,
    HumanReviewResponse,
)
from app.services.document_service import document_service
from app.services.ocr_service import ocr_service, OCRError
from app.services.gemini_service import gemini_service, GeminiServiceError
from app.services.supabase_service import supabase_service
from app.agents.workflow import run_document_workflow, resume_document_workflow, get_workflow_snapshot

logger = logging.getLogger(__name__)

router = APIRouter()

# Allowed MIME types → magic byte signatures
ALLOWED_TYPES: dict[str, bytes] = {
    "application/pdf": b"%PDF",
    "image/png":       b"\x89PNG",
    "image/jpeg":      b"\xff\xd8\xff",
}

MAX_BYTES = settings.max_file_size_mb * 1024 * 1024  # e.g. 10 MB


def _check_magic(file_bytes: bytes, content_type: str) -> bool:
    """Verify the first bytes match the declared content-type."""
    signature = ALLOWED_TYPES.get(content_type)
    if signature is None:
        return False
    return file_bytes[:len(signature)] == signature


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DocumentUploadResponse,
)
async def upload_document(file: UploadFile = File(...)):
    """
    Accept a PDF, PNG, JPG, or JPEG file for processing.
    Saves the file to the local uploads/ directory and stores metadata.
    """
    # 1. MIME type check
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type '{file.content_type}'. "
                f"Allowed: PDF, PNG, JPG/JPEG."
            ),
        )

    # 2. Read file bytes
    file_bytes = await file.read()
    file_size = len(file_bytes)

    # 3. Empty file check
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty (0 bytes).",
        )

    # 4. Size limit check
    if file_size > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File size {file_size / (1024 * 1024):.2f} MB exceeds the "
                f"{settings.max_file_size_mb} MB limit."
            ),
        )

    # 5. Magic bytes validation
    if not _check_magic(file_bytes, file.content_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File content does not match its declared type. Upload aborted.",
        )

    # 6. Save file + metadata
    record = document_service.save_document_with_file(
        filename=file.filename or "unknown",
        content_type=file.content_type,
        file_size=file_size,
        file_bytes=file_bytes,
    )

    return DocumentUploadResponse(
        message="File received and saved. Processing will begin shortly.",
        id=record["id"],
        filename=record["filename"],
        content_type=record["content_type"],
        file_size=record["file_size"],
        status=record["status"],
        task_id=record["task_id"],
        created_at=record["created_at"],
    )


@router.get("", response_model=DocumentListResponse)
def list_documents():
    """Return list of all uploaded documents."""
    docs = document_service.list_documents()
    return DocumentListResponse(documents=docs, total=len(docs))


@router.get("/stats")
def get_stats():
    """Return dashboard statistics."""
    return document_service.get_stats()


@router.get("/ocr-status")
def get_ocr_status():
    """Return diagnostic status of the OCR subsystem (Tesseract availability, version, path)."""
    return ocr_service.get_tesseract_status()


@router.get("/ai-status")
def get_ai_status():
    """Return diagnostic status of the Gemini AI integration."""
    return gemini_service.get_service_status()


@router.get("/supabase-status")
def get_supabase_status():
    """Return diagnostic status of the Supabase Cloud Storage and Database integration."""
    return supabase_service.get_service_status()


@router.post("/{document_id}/extract", response_model=TextExtractionResponse)
def extract_document_text(document_id: str):
    """
    Extract text from an uploaded document using PyMuPDF (digital PDF)
    or Tesseract OCR (scanned PDF / image).
    """
    doc = document_service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    file_path = doc.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="The file for this document no longer exists on the server.",
        )

    content_type = doc.get("content_type", "")
    document_service.update_extraction_result(
        document_id=document_id,
        extraction_status="processing",
    )

    try:
        result = ocr_service.extract_text_from_file(
            doc_id=document_id,
            file_path=file_path,
            content_type=content_type,
        )
        updated = document_service.update_extraction_result(
            document_id=document_id,
            extraction_status="completed",
            text=result["text"],
            page_count=result["page_count"],
            extraction_method=result["extraction_method"],
            extracted_text_path=result["extracted_text_path"],
            extracted_at=result["extracted_at"],
        )
        return TextExtractionResponse(
            id=document_id,
            filename=doc["filename"],
            status=updated["status"],
            extraction_status="completed",
            extraction_method=result["extraction_method"],
            page_count=result["page_count"],
            extracted_text_path=result["extracted_text_path"],
            extracted_at=result["extracted_at"],
            extracted_text=result["text"],
        )
    except OCRError as e:
        document_service.update_extraction_result(
            document_id=document_id,
            extraction_status="failed",
            error_message=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        document_service.update_extraction_result(
            document_id=document_id,
            extraction_status="failed",
            error_message=f"Unexpected extraction error: {e}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Text extraction failed: {e}",
        )


@router.get("/{document_id}/text", response_model=DocumentTextResponse)
def get_extracted_text(document_id: str):
    """
    Retrieve the extracted text content and metadata for a document.
    """
    doc = document_service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    ext_status = doc.get("extraction_status", "pending")
    if ext_status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Text has not been extracted for this document yet. Current extraction status: {ext_status}",
        )

    text = None
    if doc.get("extracted_text_path"):
        text = ocr_service.read_extracted_text(doc["extracted_text_path"])
    if not text:
        text = doc.get("extracted_text") or ""

    return DocumentTextResponse(
        id=document_id,
        filename=doc["filename"],
        extraction_status="completed",
        extraction_method=doc.get("extraction_method"),
        page_count=doc.get("page_count"),
        extracted_at=doc.get("extracted_at"),
        text=text,
    )


@router.post("/{document_id}/analyze", response_model=DocumentAnalysisResponse)
def analyze_document(document_id: str, force: bool = False):
    """
    Analyze document text using Gemini AI to classify category, extract structured fields,
    generate summary, and recommend operational priority.
    """
    doc = document_service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    # If already analyzed and force=False, return existing analysis with review metadata
    if not force and doc.get("ai_status") == "completed" and doc.get("ai_category"):
        analysis = AIAnalysisResult(
            category=doc.get("ai_category") or "Other",
            confidence=doc.get("ai_confidence") if doc.get("ai_confidence") is not None else 0.9,
            classification_reason=doc.get("ai_classification_reason") or "Classified by LangGraph Classification Agent.",
            summary=doc.get("ai_summary") or "Summary unavailable.",
            extracted_fields=doc.get("ai_extracted_fields") or {},
            keywords=doc.get("ai_keywords") or [],
            suggested_priority=doc.get("ai_suggested_priority") or doc.get("priority") or "Medium",
            priority_explanation=doc.get("ai_priority_explanation") or "Standard operational triage assessment.",
            action_items=doc.get("ai_action_items") or [],
            analyzed_at=doc.get("ai_analyzed_at"),
            model=doc.get("ai_model"),
        )
        saved_review_status = doc.get("ai_review_status", "auto_approved")
        return DocumentAnalysisResponse(
            id=document_id,
            filename=doc["filename"],
            ai_status="completed",
            analysis=analysis,
            review_status=saved_review_status,
            requires_human_review=(saved_review_status == "pending_review"),
            review_trigger_reasons=doc.get("ai_review_reasons") or [],
            routing=doc.get("ai_routing"),
            workflow_history=doc.get("ai_workflow_history") or [],
        )

    # 1. Check/Retrieve extracted text
    text = ""
    if doc.get("extracted_text_path"):
        text = ocr_service.read_extracted_text(doc["extracted_text_path"]) or ""
    if not text:
        text = doc.get("extracted_text") or ""

    # If OCR was not executed yet, attempt OCR extraction first
    if not text:
        file_path = doc.get("file_path")
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Original file for this document is missing from the server.",
            )
        try:
            ocr_res = ocr_service.extract_text_from_file(
                doc_id=document_id,
                file_path=file_path,
                content_type=doc.get("content_type", ""),
            )
            document_service.update_extraction_result(
                document_id=document_id,
                extraction_status="completed",
                text=ocr_res["text"],
                page_count=ocr_res["page_count"],
                extraction_method=ocr_res["extraction_method"],
                extracted_text_path=ocr_res["extracted_text_path"],
                extracted_at=ocr_res["extracted_at"],
            )
            text = ocr_res["text"]
        except OCRError as oe:
            document_service.update_extraction_result(
                document_id=document_id,
                extraction_status="failed",
                error_message=str(oe),
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"OCR text extraction failed: {oe}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to extract document text prior to AI analysis: {e}",
            )

    if not text or not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document text is empty. Cannot perform AI analysis on blank documents.",
        )

    # 2. Check API key configuration upfront
    if not gemini_service.is_api_key_configured():
        document_service.update_ai_analysis_result(
            document_id=document_id,
            ai_status="failed",
            error_message="Gemini API key is not configured. Please set GEMINI_API_KEY in backend/.env (obtain a free key from https://aistudio.google.com/app/apikey).",
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Gemini API key is not configured. Please set GEMINI_API_KEY in backend/.env (obtain a free key from https://aistudio.google.com/app/apikey).",
        )

    # 3. Mark AI status as processing
    document_service.update_ai_analysis_result(
        document_id=document_id,
        ai_status="processing",
    )

    # 3. Call LangGraph Multi-Agent Orchestrator
    try:
        logger.info("Executing LangGraph Multi-Agent Workflow for doc %s", document_id)
        graph_output = run_document_workflow(
            document_id=document_id,
            filename=doc["filename"],
            document_text=text,
        )

        # Inspect if workflow paused on interrupt (human review required)
        snapshot = get_workflow_snapshot(document_id)
        has_interrupt = bool(snapshot and snapshot.get("tasks"))

        review_status = graph_output.get("review_status") or ("pending_review" if has_interrupt else "auto_approved")
        requires_review = graph_output.get("requires_human_review", has_interrupt)
        review_reasons = graph_output.get("review_trigger_reasons", [])
        if has_interrupt and not review_reasons and snapshot:
            for task in snapshot.get("tasks", []):
                for int_val in task.get("interrupts", []):
                    if isinstance(int_val, dict) and int_val.get("reasons"):
                        review_reasons.extend(int_val["reasons"])
            if not review_reasons:
                if graph_output.get("suggested_priority") == "Critical":
                    review_reasons.append("Critical operational priority requires mandatory human sign-off.")
                if graph_output.get("classification_confidence", 1.0) < 0.75:
                    review_reasons.append("Low classification confidence requires verification.")
                if graph_output.get("category") == "Incident Report":
                    review_reasons.append("Safety Incident Reports require mandatory human-in-the-loop review and sign-off.")
        review_reasons = list(dict.fromkeys(review_reasons))

        now_iso = datetime.now(timezone.utc).isoformat()
        analysis_result = AIAnalysisResult(
            category=graph_output.get("category", "Other"),
            confidence=graph_output.get("classification_confidence", 0.9),
            classification_reason=graph_output.get("classification_reason", "Classified by LangGraph Classification Agent."),
            summary=graph_output.get("summary", "Summary unavailable."),
            extracted_fields=graph_output.get("extracted_fields") or {},
            keywords=graph_output.get("keywords") or [],
            suggested_priority=graph_output.get("suggested_priority", "Medium"),
            priority_explanation=graph_output.get("priority_explanation", "Standard operational triage assessment."),
            action_items=graph_output.get("action_items") or [],
            analyzed_at=now_iso,
            model=graph_output.get("model_used") or gemini_service._model,
        )

        routing_data = {
            "target_department": graph_output.get("target_department", "Administration"),
            "routing_reason": graph_output.get("routing_reason", "Routed by LangGraph Routing Agent."),
            "escalation_required": graph_output.get("escalation_required", False),
        }

        document_service.update_ai_analysis_result(
            document_id=document_id,
            ai_status="completed",
            category=analysis_result.category,
            confidence=analysis_result.confidence,
            classification_reason=analysis_result.classification_reason,
            summary=analysis_result.summary,
            extracted_fields=analysis_result.extracted_fields,
            keywords=analysis_result.keywords,
            suggested_priority=analysis_result.suggested_priority,
            priority_explanation=analysis_result.priority_explanation,
            action_items=analysis_result.action_items,
            analyzed_at=now_iso,
            model=analysis_result.model,
            review_status=review_status,
            review_reasons=review_reasons,
            reviewer_notes=graph_output.get("reviewer_notes"),
            reviewed_at=graph_output.get("reviewed_at"),
            routing=routing_data,
            workflow_history=graph_output.get("workflow_history", []),
            target_department=routing_data["target_department"],
            error_message=None,
        )
        return DocumentAnalysisResponse(
            id=document_id,
            filename=doc["filename"],
            ai_status="completed",
            analysis=analysis_result,
            review_status=review_status,
            requires_human_review=requires_review,
            review_trigger_reasons=review_reasons,
            routing=routing_data,
            workflow_history=graph_output.get("workflow_history", []),
        )
    except GeminiServiceError as ge:
        logger.warning("Gemini analysis error for document %s: %s", document_id, ge)
        document_service.update_ai_analysis_result(
            document_id=document_id,
            ai_status="failed",
            error_message=str(ge),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ge),
        )
    except Exception as e:
        logger.exception("Unexpected error during AI analysis for doc %s", document_id)
        clean_error = f"AI analysis failed: {type(e).__name__} - {str(e)}"
        document_service.update_ai_analysis_result(
            document_id=document_id,
            ai_status="failed",
            error_message=clean_error,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=clean_error,
        )


@router.get("/{document_id}/analysis", response_model=DocumentAnalysisResponse)
def get_document_analysis(document_id: str):
    """
    Retrieve previously saved Gemini AI analysis for a document.
    """
    doc = document_service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    ai_status = doc.get("ai_status", "pending")
    if ai_status != "completed" or not doc.get("ai_category"):
        return DocumentAnalysisResponse(
            id=document_id,
            filename=doc["filename"],
            ai_status=ai_status,
            analysis=None,
            error_message=doc.get("ai_error_message"),
        )

    analysis = AIAnalysisResult(
        category=doc.get("ai_category") or "Other",
        confidence=doc.get("ai_confidence") if doc.get("ai_confidence") is not None else 0.9,
        classification_reason=doc.get("ai_classification_reason") or "Classified by LangGraph Classification Agent.",
        summary=doc.get("ai_summary") or "Summary unavailable.",
        extracted_fields=doc.get("ai_extracted_fields") or {},
        keywords=doc.get("ai_keywords") or [],
        suggested_priority=doc.get("ai_suggested_priority") or doc.get("priority") or "Medium",
        priority_explanation=doc.get("ai_priority_explanation") or "Standard operational triage assessment.",
        action_items=doc.get("ai_action_items") or [],
        analyzed_at=doc.get("ai_analyzed_at"),
        model=doc.get("ai_model"),
    )

    routing_data = doc.get("ai_routing")
    review_status = doc.get("ai_review_status", "auto_approved")

    return DocumentAnalysisResponse(
        id=document_id,
        filename=doc["filename"],
        ai_status="completed",
        analysis=analysis,
        review_status=review_status,
        requires_human_review=review_status == "pending_review",
        review_trigger_reasons=doc.get("ai_review_reasons") or [],
        routing=routing_data,
        workflow_history=doc.get("ai_workflow_history") or [],
    )


@router.post("/{document_id}/review", response_model=HumanReviewResponse)
def submit_human_review(document_id: str, payload: HumanReviewRequest):
    """
    Submit a human review decision (approve or reject) for a document that paused for review.
    Resumes the LangGraph workflow via Command(resume=payload) using checkpoints in checkpoints.sqlite.
    """
    doc = document_service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    decision_dict = {
        "decision": payload.decision.value,
        "notes": payload.notes or "",
        "target_department": payload.target_department.value if payload.target_department else None,
        "priority": payload.priority.value if payload.priority else None,
    }

    try:
        resume_document_workflow(document_id, decision_dict)
    except Exception as e:
        logger.warning("Graph resume encountered notice: %s", e)

    dept = payload.target_department.value if payload.target_department else doc.get("department")
    pri = payload.priority.value if payload.priority else doc.get("ai_suggested_priority")

    document_service.apply_human_review_decision(
        document_id=document_id,
        decision=payload.decision.value,
        notes=payload.notes or "",
        target_department=dept,
        priority=pri,
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    return HumanReviewResponse(
        id=document_id,
        filename=doc["filename"],
        review_status=payload.decision.value,
        decision=payload.decision.value,
        department=dept,
        priority=pri,
        reviewer_notes=payload.notes,
        reviewed_at=now_iso,
        message=f"Human review decision successfully recorded: {payload.decision.value.upper()}",
    )


@router.get("/{document_id}/download")
def download_document(document_id: str):
    """
    Stream the original uploaded file back to the client.
    Serves from local disk if available; otherwise falls back to
    retrieving from private Supabase Storage.
    """
    doc = document_service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    file_path = doc.get("file_path")
    # 1. If file exists on local filesystem, stream it directly
    if file_path and os.path.exists(file_path):
        return FileResponse(
            path=file_path,
            filename=doc["filename"],
            media_type=doc.get("content_type", "application/octet-stream"),
        )

    # 2. If missing locally (e.g. ephemeral Render container restart), check Supabase Storage
    if supabase_service.is_configured():
        storage_path = doc.get("storage_path") or f"documents/{document_id}/{doc.get('stored_filename')}"
        file_bytes = supabase_service.download_storage_file(storage_path)
        if file_bytes:
            # Self-healing: cache to local filesystem for fast subsequent access
            try:
                if file_path:
                    os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
                    with open(file_path, "wb") as fh:
                        fh.write(file_bytes)
                    return FileResponse(
                        path=file_path,
                        filename=doc["filename"],
                        media_type=doc.get("content_type", "application/octet-stream"),
                    )
            except Exception:
                pass

            from fastapi.responses import Response
            return Response(
                content=file_bytes,
                media_type=doc.get("content_type", "application/octet-stream"),
                headers={"Content-Disposition": f'attachment; filename="{doc["filename"]}"'},
            )

    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="The file for this document is no longer available on the server.",
    )


@router.get("/{document_id}", response_model=DocumentResult)
def get_document(document_id: str):
    """Return a single document's metadata by ID."""
    doc = document_service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    return doc


@router.delete("/{document_id}", response_model=DeleteResponse)
def delete_document(document_id: str):
    """
    Delete a document's metadata and its file from disk.
    Returns 404 if the document does not exist.
    """
    deleted = document_service.delete_document(document_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    return DeleteResponse(
        id=document_id,
        message="Document deleted successfully.",
        deleted=True,
    )
