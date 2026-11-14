"""
Gemini AI Document Intelligence Service for DocDeclutter.
Uses Google's official google-genai SDK to perform:
1. Document Classification (7 metro categories)
2. Structured Information Extraction (category-specific fields)
3. Document Summarization (concise, factual)
4. Key Info & Action Item Extraction
5. Priority Recommendation (Low, Medium, High, Critical)
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from google import genai
from google.genai import types

from app.core.config import settings
from app.schemas.document import AIAnalysisResult, DocumentCategory, PriorityLevel

logger = logging.getLogger(__name__)

# Allowed standard categories
VALID_CATEGORIES = [c.value for c in DocumentCategory]
VALID_PRIORITIES = [p.value for p in PriorityLevel]


class GeminiServiceError(Exception):
    """Custom exception raised during Gemini AI analysis failure."""
    pass


GEMINI_ANALYSIS_PROMPT = """
You are an expert Document Intelligence AI for a Metro Rail Organization (DocDeclutter).
Analyze the following extracted document text thoroughly and provide structured JSON output.

Categories allowed (choose exactly one):
1. "Employee Application"
2. "Maintenance Report"
3. "Incident Report"
4. "Vendor Invoice"
5. "Passenger Complaint"
6. "Safety Inspection Report"
7. "Other"

Guidance for Information Extraction:
- For "Employee Application": extract employee_name, employee_id, department, application_date, request_type, request_description.
- For "Maintenance Report": extract station, equipment, issue, reported_date, severity, assigned_department, maintenance_details.
- For "Incident Report": extract incident_type, location, incident_date, people_involved, severity, description, action_taken.
- For "Vendor Invoice": extract vendor_name, invoice_number, invoice_date, total_amount, due_date, payment_status.
- For "Passenger Complaint": extract passenger_name, station, complaint_type, complaint_date, description, requested_action.
- For "Safety Inspection Report": extract station, inspection_date, inspector, inspection_findings, safety_issues, recommended_corrective_actions.
- For "Other": extract any key structured fields present.
- IMPORTANT: Use null for any field not present in the document. NEVER invent or hallucinate missing information.

Guidance for Summarization:
- Write a professional, concise summary (approx 75–150 words for complete documents; shorter for brief documents).
- Preserve real names, stations, dates, equipment, and core purpose.
- Do not introduce unsupported facts.

Guidance for Priority Recommendation:
- Choose exactly one: "Low", "Medium", "High", or "Critical".
- "Critical": Life-safety hazard, track blockage, major power failure, derailment, active emergency.
- "High": Station equipment failure (escalator, AFC gate, elevator), severe passenger complaint, overdue safety inspection.
- "Medium": Routine maintenance request, standard vendor invoice, general employee leave request.
- "Low": Informational memo, minor inquiry, routine administrative record.
- Provide a clear, evidence-based priority explanation.

Return ONLY a valid JSON object matching this schema:
{
  "category": "Maintenance Report",
  "confidence": 0.95,
  "classification_reason": "Brief explanation of why this document matches this category",
  "summary": "Concise professional summary preserving key details",
  "extracted_fields": {
    "station": "Station Name or null",
    "equipment": "Equipment Name or null"
  },
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "suggested_priority": "High",
  "priority_explanation": "Explanation based on document evidence",
  "action_items": ["Action item 1", "Action item 2"]
}

Document Text to Analyze:
\"\"\"
__DOCUMENT_TEXT__
\"\"\"
"""


class GeminiService:
    def __init__(self):
        self._client: Optional[genai.Client] = None
        self._api_key: Optional[str] = None
        self._model: str = getattr(settings, "gemini_model", "gemini-3.5-flash-lite") or "gemini-3.5-flash-lite"
        self._refresh_client()

    def _get_configured_api_key(self) -> Optional[str]:
        """Retrieve API key from settings or environment without logging secrets."""
        key = getattr(settings, "gemini_api_key", None)
        if not key or key == "your_gemini_api_key_here":
            key = os.environ.get("GEMINI_API_KEY")
        if not key or key == "your_gemini_api_key_here":
            key = os.environ.get("GOOGLE_API_KEY")
        if key and key.strip() and key != "your_gemini_api_key_here":
            return key.strip()
        return None

    def _refresh_client(self):
        """Initialize or refresh the google-genai Client if an API key is available."""
        key = self._get_configured_api_key()
        self._api_key = key
        self._model = getattr(settings, "gemini_model", "gemini-3.5-flash-lite") or "gemini-3.5-flash-lite"
        if key:
            try:
                self._client = genai.Client(api_key=key)
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Client: {e}")
                self._client = None
        else:
            self._client = None

    def is_api_key_configured(self) -> bool:
        """Check if a valid Gemini API key is configured."""
        self._refresh_client()
        return self._client is not None

    def get_service_status(self) -> Dict[str, Any]:
        """Return diagnostic status of the Gemini service."""
        configured = self.is_api_key_configured()
        return {
            "configured": configured,
            "model": self._model,
            "provider": "google-genai",
            "message": "Gemini API key is configured and ready." if configured else "Gemini API key is missing. Set GEMINI_API_KEY in backend/.env"
        }

    def analyze_document_text(self, document_text: str, doc_filename: str = "") -> AIAnalysisResult:
        """
        Analyze extracted document text using Gemini.
        Returns a validated AIAnalysisResult object.
        """
        if not document_text or not document_text.strip():
            raise GeminiServiceError("Cannot analyze document: extracted text is empty.")

        # Ensure API key is configured
        self._refresh_client()
        if not self._client:
            raise GeminiServiceError(
                "Gemini API key is not configured. Please set GEMINI_API_KEY in backend/.env "
                "(obtain a free key from https://aistudio.google.com/app/apikey)."
            )

        # Truncate overly long text safely (Gemini handles 1M+ tokens, but keep student project requests fast & focused)
        max_chars = 30000
        truncated_text = document_text[:max_chars]
        if len(document_text) > max_chars:
            truncated_text += "\n\n[... Text truncated for optimal processing ...]"

        # Build prompt using literal substitution to prevent KeyError with JSON braces
        prompt = GEMINI_ANALYSIS_PROMPT.replace("__DOCUMENT_TEXT__", truncated_text)

        parsed_data, used_model = self.generate_json(prompt)

        try:
            return self._normalize_and_validate(parsed_data, model_name=used_model)
        except Exception as e:
            logger.error("Failed to normalize Gemini response data: %s", e)
            raise GeminiServiceError(f"Failed to process structured AI analysis: {e}")

    def generate_json(self, prompt: str, system_instruction: Optional[str] = None) -> Tuple[Dict[str, Any], str]:
        """
        Execute a Gemini generation request that requires JSON output.
        Reuses the existing authenticated client, model selection, retry, and fallback logic.
        Returns a tuple of (parsed_json_dict, model_name_used).
        """
        self._refresh_client()
        if not self._client:
            raise GeminiServiceError(
                "Gemini API key is not configured. Please set GEMINI_API_KEY in backend/.env "
                "(obtain a free key from https://aistudio.google.com/app/apikey)."
            )

        models_to_try = [self._model]
        for fallback in [
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3.8-flash",
        ]:
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        response = None
        last_error = None
        used_model = self._model

        import time

        for candidate in models_to_try:
            for attempt in range(3):
                try:
                    config_kwargs: Dict[str, Any] = {
                        "response_mime_type": "application/json",
                        "temperature": 0.1,
                    }
                    if system_instruction:
                        config_kwargs["system_instruction"] = system_instruction
                    config = types.GenerateContentConfig(**config_kwargs)

                    response = self._client.models.generate_content(
                        model=candidate,
                        contents=prompt,
                        config=config,
                    )
                    used_model = candidate
                    break
                except Exception as e:
                    error_str = str(e)
                    last_error = error_str
                    logger.warning("Gemini model %s attempt %s failed: %s", candidate, attempt + 1, error_str)
                    if "API_KEY_INVALID" in error_str or "API key not valid" in error_str:
                        raise GeminiServiceError("The provided GEMINI_API_KEY is invalid. Please check your key at https://aistudio.google.com/app/apikey")
                    if "503" in error_str or "high demand" in error_str or "UNAVAILABLE" in error_str or "Server disconnected" in error_str or "RemoteProtocolError" in error_str:
                        time.sleep(1.5)
                        continue
                    break  # Try next candidate on 404 or other errors
            if response is not None:
                break

        if response is None:
            error_msg = last_error or "All candidate models failed."
            if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
                raise GeminiServiceError("Gemini API rate limit reached. Please wait a moment before retrying.")
            raise GeminiServiceError(f"Gemini API call failed: {error_msg}")

        raw_text = response.text or ""
        parsed_data = self._clean_and_parse_json(raw_text)
        return parsed_data, used_model

    def _clean_and_parse_json(self, raw_text: str) -> Dict[str, Any]:
        """Strip markdown fences if present and parse JSON safely."""
        cleaned = raw_text.strip()
        # Remove ```json and ``` if returned
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Fallback regex extraction if model prepended commentary
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            raise GeminiServiceError(f"Failed to parse Gemini response as JSON: {e}. Raw response: {raw_text[:200]}")

    def _normalize_and_validate(self, data: Dict[str, Any], model_name: Optional[str] = None) -> AIAnalysisResult:
        """Validate and normalize parsed data into an AIAnalysisResult."""
        # 1. Normalize Category
        category = str(data.get("category", "Other")).strip()
        if category not in VALID_CATEGORIES:
            # Attempt fuzzy match
            matched = False
            for valid_cat in VALID_CATEGORIES:
                if valid_cat.lower() in category.lower() or category.lower() in valid_cat.lower():
                    category = valid_cat
                    matched = True
                    break
            if not matched:
                category = "Other"

        # 2. Normalize Confidence
        try:
            confidence = float(data.get("confidence", 0.85))
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.85

        # 3. Normalize Priority
        priority = str(data.get("suggested_priority", "Medium")).strip().capitalize()
        if priority not in VALID_PRIORITIES:
            matched_pri = False
            for valid_pri in VALID_PRIORITIES:
                if valid_pri.lower() == priority.lower():
                    priority = valid_pri
                    matched_pri = True
                    break
            if not matched_pri:
                priority = "Medium"

        # 4. Normalize Keywords
        raw_keywords = data.get("keywords") or []
        if isinstance(raw_keywords, list):
            keywords = [str(k).strip() for k in raw_keywords if str(k).strip()]
        else:
            keywords = []

        # 5. Normalize Action Items
        raw_actions = data.get("action_items") or []
        if isinstance(raw_actions, list):
            action_items = [str(a).strip() for a in raw_actions if str(a).strip()]
        else:
            action_items = []

        # 6. Normalize Extracted Fields
        extracted_fields = data.get("extracted_fields")
        if not isinstance(extracted_fields, dict):
            extracted_fields = {}

        now = datetime.now(timezone.utc).isoformat()

        return AIAnalysisResult(
            category=category,
            confidence=confidence,
            classification_reason=str(data.get("classification_reason") or "Classified based on document content."),
            summary=str(data.get("summary") or "Summary unavailable."),
            extracted_fields=extracted_fields,
            keywords=keywords,
            suggested_priority=priority,
            priority_explanation=str(data.get("priority_explanation") or "Standard operational assessment."),
            action_items=action_items,
            analyzed_at=now,
            model=model_name or self._model,
        )


# Singleton instance
gemini_service = GeminiService()
