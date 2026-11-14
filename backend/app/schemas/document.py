"""
Pydantic schemas for Document API.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class Department(str, Enum):
    OPERATIONS = "Operations"
    HR = "Human Resources"
    FINANCE = "Finance"
    TECHNICAL = "Technical"
    SAFETY = "Safety"
    LEGAL = "Legal"
    ADMINISTRATION = "Administration"


class DocumentCategory(str, Enum):
    EMPLOYEE_APPLICATION = "Employee Application"
    MAINTENANCE_REPORT = "Maintenance Report"
    INCIDENT_REPORT = "Incident Report"
    VENDOR_INVOICE = "Vendor Invoice"
    PASSENGER_COMPLAINT = "Passenger Complaint"
    SAFETY_INSPECTION_REPORT = "Safety Inspection Report"
    OTHER = "Other"


class PriorityLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class AIAnalysisStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentBase(BaseModel):
    filename: str
    content_type: str


class DocumentUploadResponse(BaseModel):
    message: str
    task_id: str
    id: Optional[str] = None
    filename: str
    content_type: str
    file_size: Optional[int] = None
    status: DocumentStatus = DocumentStatus.PENDING
    storage_path: Optional[str] = None
    created_at: Optional[str] = None


class AIAnalysisResult(BaseModel):
    category: str
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    classification_reason: str
    summary: str
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)
    keywords: List[str] = Field(default_factory=list)
    suggested_priority: str
    priority_explanation: str
    action_items: List[str] = Field(default_factory=list)
    analyzed_at: Optional[str] = None
    model: Optional[str] = None


class DocumentResult(BaseModel):
    id: str
    filename: str
    stored_filename: Optional[str] = None
    file_extension: Optional[str] = None
    file_path: Optional[str] = None
    storage_path: Optional[str] = None
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    status: DocumentStatus = DocumentStatus.PENDING
    department: Optional[Department] = None
    priority: Optional[str] = None
    summary: Optional[str] = None
    extracted_text: Optional[str] = None
    extraction_status: Optional[str] = "pending"
    extraction_method: Optional[str] = None
    page_count: Optional[int] = None
    extracted_text_path: Optional[str] = None
    extracted_at: Optional[str] = None
    error_message: Optional[str] = None

    # AI Analysis fields
    ai_status: Optional[str] = "pending"
    ai_category: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_classification_reason: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_extracted_fields: Optional[Dict[str, Any]] = None
    ai_keywords: Optional[List[str]] = None
    ai_suggested_priority: Optional[str] = None
    ai_priority_explanation: Optional[str] = None
    ai_action_items: Optional[List[str]] = None
    ai_analyzed_at: Optional[str] = None
    ai_model: Optional[str] = None
    ai_error_message: Optional[str] = None

    # Agentic AI & Human-in-the-Loop fields
    ai_review_status: Optional[str] = "not_required"
    ai_review_reasons: Optional[List[str]] = None
    ai_reviewer_notes: Optional[str] = None
    ai_reviewed_at: Optional[str] = None
    ai_routing: Optional[Dict[str, Any]] = None
    ai_workflow_history: Optional[List[Dict[str, Any]]] = None

    task_id: Optional[str] = None
    created_at: Optional[str] = None
    processed_at: Optional[str] = None


class DocumentListResponse(BaseModel):
    documents: List[DocumentResult]
    total: int


class DeleteResponse(BaseModel):
    id: str
    message: str
    deleted: bool


class TextExtractionResponse(BaseModel):
    id: str
    filename: str
    status: DocumentStatus
    extraction_status: str
    extraction_method: Optional[str] = None
    page_count: Optional[int] = None
    extracted_text_path: Optional[str] = None
    extracted_at: Optional[str] = None
    extracted_text: Optional[str] = None
    error_message: Optional[str] = None


class DocumentTextResponse(BaseModel):
    id: str
    filename: str
    extraction_status: str
    extraction_method: Optional[str] = None
    page_count: Optional[int] = None
    extracted_at: Optional[str] = None
    text: str


class DocumentAnalysisResponse(BaseModel):
    id: str
    filename: str
    ai_status: str
    analysis: Optional[AIAnalysisResult] = None
    error_message: Optional[str] = None

    # Agentic workflow extensions
    review_status: Optional[str] = None
    requires_human_review: Optional[bool] = False
    review_trigger_reasons: Optional[List[str]] = None
    routing: Optional[Dict[str, Any]] = None
    workflow_history: Optional[List[Dict[str, Any]]] = None


class HumanReviewDecision(str, Enum):
    APPROVE = "approved"
    REJECT = "rejected"


class HumanReviewRequest(BaseModel):
    decision: HumanReviewDecision
    notes: Optional[str] = ""
    target_department: Optional[Department] = None
    priority: Optional[PriorityLevel] = None


class HumanReviewResponse(BaseModel):
    id: str
    filename: str
    review_status: str
    decision: str
    department: Optional[str] = None
    priority: Optional[str] = None
    reviewer_notes: Optional[str] = None
    reviewed_at: str
    message: str
