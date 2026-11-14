"""
Agentic Document State schema for LangGraph workflow.
Represents the shared mutable state passed between specialized agents.
"""

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class AgenticDocumentState(TypedDict, total=False):
    # Document Context
    document_id: str
    filename: str
    document_text: str

    # Agent 1: Classification
    category: str
    classification_confidence: float
    classification_reason: str

    # Agent 2: Information Extraction
    summary: str
    extracted_fields: Dict[str, Any]
    keywords: List[str]

    # Agent 3: Priority Assessment
    suggested_priority: str
    priority_explanation: str
    action_items: List[str]

    # Agent 4: Department Routing
    target_department: str
    routing_reason: str
    escalation_required: bool

    # Step 5: Human-in-the-Loop Review
    requires_human_review: bool
    review_status: str  # "auto_approved" | "pending_review" | "approved" | "rejected"
    review_trigger_reasons: List[str]
    reviewer_notes: Optional[str]
    reviewed_at: Optional[str]

    # Audit Trail & Orchestration Metadata (using operator.add reducer for parallel fan-out)
    model_used: str
    workflow_history: Annotated[List[Dict[str, Any]], operator.add]
    errors: Annotated[List[str], operator.add]
