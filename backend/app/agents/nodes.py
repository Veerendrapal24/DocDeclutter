"""
Agent node implementations for DocDeclutter LangGraph workflow.
Each node performs a focused, specialized task reusing the unified Gemini service.
"""

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langgraph.types import interrupt

from app.agents.prompts import (
    CLASSIFICATION_PROMPT,
    EXTRACTION_PROMPT,
    PRIORITY_PROMPT,
    ROUTING_PROMPT,
)
from app.agents.state import AgenticDocumentState
from app.schemas.document import Department, DocumentCategory, PriorityLevel
from app.services.gemini_service import gemini_service

logger = logging.getLogger("docdeclutter.agents")

VALID_CATEGORIES = [c.value for c in DocumentCategory]
VALID_PRIORITIES = [p.value for p in PriorityLevel]
VALID_DEPARTMENTS = [d.value for d in Department]


def _truncate_text(text: str, max_chars: int = 30000) -> str:
    """Safely truncate text to keep LLM calls fast and within limits."""
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[... Text truncated for optimal processing ...]"
    return text


def classification_agent(state: AgenticDocumentState) -> Dict[str, Any]:
    """
    Agent 1: Document Classification Agent.
    Analyzes document text and categorizes it into one of 7 official metro categories.
    """
    start_time = time.time()
    logger.info("Executing Classification Agent for doc %s", state.get("document_id"))

    doc_text = _truncate_text(state.get("document_text", ""))
    prompt = CLASSIFICATION_PROMPT.replace("__DOCUMENT_TEXT__", doc_text)

    try:
        data, model_name = gemini_service.generate_json(prompt)
    except Exception as e:
        logger.error("Classification Agent failed: %s", e)
        return {
            "category": "Other",
            "classification_confidence": 0.5,
            "classification_reason": f"Automated classification fallback due to error: {e}",
            "errors": [f"ClassificationAgent: {e}"],
            "workflow_history": [{
                "agent": "Classification Agent",
                "action": "fallback_classified",
                "category": "Other",
                "confidence": 0.5,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

    # Normalize Category
    raw_cat = str(data.get("category", "Other")).strip()
    category = "Other"
    for valid in VALID_CATEGORIES:
        if valid.lower() == raw_cat.lower() or valid.lower() in raw_cat.lower():
            category = valid
            break

    # Normalize Confidence
    try:
        confidence = float(data.get("confidence", 0.9))
        confidence = max(0.0, min(1.0, confidence))
    except (ValueError, TypeError):
        confidence = 0.9

    duration_ms = int((time.time() - start_time) * 1000)
    history_entry = {
        "agent": "Classification Agent",
        "action": "classified",
        "category": category,
        "confidence": confidence,
        "duration_ms": duration_ms,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "category": category,
        "classification_confidence": confidence,
        "classification_reason": str(data.get("classification_reason") or "Classified based on document content."),
        "model_used": model_name,
        "workflow_history": [history_entry],
    }


def extraction_agent(state: AgenticDocumentState) -> Dict[str, Any]:
    """
    Agent 2: Information Extraction Agent.
    Extracts structured fields, generates keywords, and creates an executive summary.
    Runs in parallel with Priority Assessment Agent.
    """
    start_time = time.time()
    category = state.get("category", "Other")
    logger.info("Executing Information Extraction Agent for doc %s (category=%s)", state.get("document_id"), category)

    doc_text = _truncate_text(state.get("document_text", ""))
    prompt = EXTRACTION_PROMPT.replace("__CATEGORY__", category).replace("__DOCUMENT_TEXT__", doc_text)

    try:
        data, model_name = gemini_service.generate_json(prompt)
    except Exception as e:
        logger.error("Extraction Agent failed: %s", e)
        return {
            "summary": "Summary extraction temporarily unavailable.",
            "extracted_fields": {},
            "keywords": [],
            "errors": [f"ExtractionAgent: {e}"],
            "workflow_history": [{
                "agent": "Information Extraction Agent",
                "action": "fallback_extracted",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

    # Normalize Fields
    fields = data.get("extracted_fields")
    if not isinstance(fields, dict):
        fields = {}

    # Normalize Keywords
    raw_keywords = data.get("keywords") or []
    keywords = [str(k).strip() for k in raw_keywords if str(k).strip()] if isinstance(raw_keywords, list) else []

    summary = str(data.get("summary") or "Summary unavailable.").strip()

    duration_ms = int((time.time() - start_time) * 1000)
    history_entry = {
        "agent": "Information Extraction Agent",
        "action": "extracted_information",
        "field_count": len(fields),
        "duration_ms": duration_ms,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "summary": summary,
        "extracted_fields": fields,
        "keywords": keywords,
        "workflow_history": [history_entry],
    }


def priority_agent(state: AgenticDocumentState) -> Dict[str, Any]:
    """
    Agent 3: Priority Assessment Agent.
    Evaluates life-safety risks, schedule delays, and operational critical paths.
    Runs in parallel with Information Extraction Agent.
    """
    time.sleep(0.3)  # Small stagger to avoid simultaneous burst limits on free-tier API
    start_time = time.time()
    category = state.get("category", "Other")
    logger.info("Executing Priority Assessment Agent for doc %s (category=%s)", state.get("document_id"), category)

    doc_text = _truncate_text(state.get("document_text", ""))
    prompt = PRIORITY_PROMPT.replace("__CATEGORY__", category).replace("__DOCUMENT_TEXT__", doc_text)

    try:
        data, model_name = gemini_service.generate_json(prompt)
    except Exception as e:
        logger.error("Priority Assessment Agent failed: %s", e)
        return {
            "suggested_priority": "Medium",
            "priority_explanation": f"Automated priority assessment fallback: {e}",
            "action_items": [],
            "errors": [f"PriorityAgent: {e}"],
            "workflow_history": [{
                "agent": "Priority Assessment Agent",
                "action": "fallback_priority",
                "priority": "Medium",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

    # Normalize Priority
    raw_pri = str(data.get("suggested_priority", "Medium")).strip().capitalize()
    priority = "Medium"
    for valid in VALID_PRIORITIES:
        if valid.lower() == raw_pri.lower():
            priority = valid
            break

    # Normalize Action Items
    raw_actions = data.get("action_items") or []
    actions = [str(a).strip() for a in raw_actions if str(a).strip()] if isinstance(raw_actions, list) else []

    duration_ms = int((time.time() - start_time) * 1000)
    history_entry = {
        "agent": "Priority Assessment Agent",
        "action": "assessed_priority",
        "priority": priority,
        "duration_ms": duration_ms,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "suggested_priority": priority,
        "priority_explanation": str(data.get("priority_explanation") or "Standard operational triage assessment."),
        "action_items": actions,
        "workflow_history": [history_entry],
    }


def routing_agent(state: AgenticDocumentState) -> Dict[str, Any]:
    """
    Agent 4: Department Routing Agent.
    Maps document to target department based on category, priority, and extracted details.
    Runs after Extraction and Priority agents complete (Fan-in).
    """
    start_time = time.time()
    category = state.get("category", "Other")
    priority = state.get("suggested_priority", "Medium")
    fields = json.dumps(state.get("extracted_fields", {}))

    logger.info("Executing Department Routing Agent for doc %s (cat=%s, priority=%s)", state.get("document_id"), category, priority)

    prompt = (
        ROUTING_PROMPT.replace("__CATEGORY__", category)
        .replace("__PRIORITY__", priority)
        .replace("__EXTRACTED_FIELDS__", fields)
    )

    try:
        data, model_name = gemini_service.generate_json(prompt)
    except Exception as e:
        logger.error("Routing Agent failed: %s", e)
        # Default mapping based on category
        default_dept = "Administration"
        if category in ("Maintenance Report", "Safety Inspection Report"):
            default_dept = "Technical"
        elif category == "Incident Report":
            default_dept = "Operations"
        elif category == "Vendor Invoice":
            default_dept = "Finance"
        elif category == "Employee Application":
            default_dept = "Human Resources"

        return {
            "target_department": default_dept,
            "routing_reason": f"Fallback routing based on category: {e}",
            "escalation_required": priority == "Critical",
            "errors": [f"RoutingAgent: {e}"],
            "workflow_history": [{
                "agent": "Department Routing Agent",
                "action": "fallback_routed",
                "target_department": default_dept,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

    raw_dept = str(data.get("target_department", "Administration")).strip()
    target_dept = "Administration"
    for valid in VALID_DEPARTMENTS:
        if valid.lower() == raw_dept.lower() or valid.lower() in raw_dept.lower():
            target_dept = valid
            break

    escalation = bool(data.get("escalation_required", False)) or (priority == "Critical")

    duration_ms = int((time.time() - start_time) * 1000)
    history_entry = {
        "agent": "Department Routing Agent",
        "action": "routed_department",
        "target_department": target_dept,
        "escalation_required": escalation,
        "duration_ms": duration_ms,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "target_department": target_dept,
        "routing_reason": str(data.get("routing_reason") or f"Routed to {target_dept} based on document category."),
        "escalation_required": escalation,
        "workflow_history": [history_entry],
    }


SAFETY_HAZARD_PATTERNS = [
    r"emergency\s+brak(e|ing)",
    r"brake\s+trip",
    r"emergency\s+stop",
    r"\bfire\b",
    r"\bsmoke\b",
    r"gas\s+leak",
    r"\bcollision\b",
    r"\bderail(ment)?\b",
    r"track\s+blockage",
    r"obstruction\s+on\s+(rail|track)",
    r"unauthorized\s+track\s+access",
    r"third\s+rail",
    r"traction\s+power",
    r"life[- ]safety",
    r"\bevacuat(e|ion)\b",
    r"\belectrocut(e|ion)\b",
    r"passenger\s+injury",
    r"\bcasualt(y|ies)\b",
    r"power\s+failure",
]


def human_review_node(state: AgenticDocumentState) -> Dict[str, Any]:
    """
    Step 5: Human-in-the-Loop Review Node.
    Evaluates review triggers. If review is required, pauses execution using LangGraph interrupt().
    Upon resumption via Command(resume=decision), records the authorized review decision.
    """
    # If document has already been reviewed, do not re-interrupt
    if state.get("review_status") in ("approved", "rejected", "auto_approved"):
        return {}

    category = state.get("category", "Other")
    priority = state.get("suggested_priority", "Medium")
    confidence = state.get("classification_confidence", 1.0)
    reasons: List[str] = []

    # 1. Critical operational priority
    if priority == "Critical":
        reasons.append("Critical operational priority requires mandatory human sign-off.")

    # 2. Low classification confidence (< 0.75)
    if confidence < 0.75:
        reasons.append(f"Low classification confidence ({confidence:.2f} < 0.75) requires verification.")

    # 3. Department escalation flag
    if state.get("escalation_required"):
        reasons.append("Department escalation flagged for executive review.")

    # 4. Safety category-based conditions: All Incident Reports require human review
    if category == "Incident Report":
        reasons.append("Safety Incident Reports require mandatory human-in-the-loop review and sign-off.")
    elif category == "Safety Inspection Report" and priority in ("High", "Critical"):
        reasons.append("Safety Inspection Report with elevated operational priority requires verification.")

    # 5. Serious safety hazard content check (regardless of priority label or confidence)
    doc_text = (state.get("document_text") or "").lower()
    summary = (state.get("summary") or "").lower()
    priority_exp = (state.get("priority_explanation") or "").lower()
    keywords = " ".join([str(k).lower() for k in (state.get("keywords") or [])])
    combined_content = f"{doc_text} {summary} {priority_exp} {keywords}"

    for pattern in SAFETY_HAZARD_PATTERNS:
        if re.search(pattern, combined_content, re.IGNORECASE):
            reasons.append("Document involves life-safety or critical operational hazard (e.g. emergency braking, collision, track obstruction, fire, or life-safety risk) requiring human approval.")
            break

    # Deduplicate reasons while preserving order
    reasons = list(dict.fromkeys(reasons))

    # If no conditions triggered review, auto-approve immediately
    if not reasons:
        history_entry = {
            "agent": "Human Review Decision Node",
            "action": "auto_approved",
            "reason": "Standard document passed automated validation criteria.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return {
            "requires_human_review": False,
            "review_status": "auto_approved",
            "review_trigger_reasons": [],
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "workflow_history": [history_entry],
        }

    # Review is REQUIRED. Prepare the review payload to present to human reviewer
    review_request = {
        "document_id": state.get("document_id"),
        "filename": state.get("filename"),
        "category": state.get("category"),
        "priority": priority,
        "target_department": state.get("target_department"),
        "reasons": reasons,
    }

    logger.info("Human review required for doc %s (reasons=%s). Pausing workflow via interrupt().", state.get("document_id"), reasons)

    # 🛑 LangGraph Interrupt: pauses workflow execution and saves checkpoint
    decision_payload = interrupt(review_request)

    # 🟢 Resumed via Command(resume=decision_payload)
    logger.info("Resumed doc %s after human review: %s", state.get("document_id"), decision_payload)

    decision = str(decision_payload.get("decision", "approved")).lower()
    if decision not in ("approved", "rejected"):
        decision = "approved"

    notes = str(decision_payload.get("notes") or "")
    adjusted_department = decision_payload.get("target_department") or state.get("target_department")
    adjusted_priority = decision_payload.get("priority") or state.get("suggested_priority")

    history_entry = {
        "agent": "Human Review Decision Node",
        "action": f"human_{decision}",
        "notes": notes,
        "adjusted_department": adjusted_department,
        "adjusted_priority": adjusted_priority,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "requires_human_review": True,
        "review_status": decision,
        "review_trigger_reasons": reasons,
        "reviewer_notes": notes,
        "target_department": adjusted_department,
        "suggested_priority": adjusted_priority,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "workflow_history": [history_entry],
    }
