export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed'

export type Department =
  | 'Operations'
  | 'Human Resources'
  | 'Finance'
  | 'Technical'
  | 'Safety'
  | 'Legal'
  | 'Administration'

export interface Document {
  id: string
  filename: string
  stored_filename?: string
  file_extension?: string
  file_path?: string
  content_type?: string
  file_size?: number
  status: DocumentStatus
  department: Department | string | null
  priority?: 'Low' | 'Medium' | 'High' | 'Critical' | string | null
  summary: string | null
  extracted_text?: string | null
  extraction_status?: 'pending' | 'processing' | 'completed' | 'failed'
  extraction_method?: 'pymupdf' | 'tesseract' | string | null
  page_count?: number | null
  extracted_text_path?: string | null
  extracted_at?: string | null
  error_message?: string | null

  // AI Analysis fields
  ai_status?: 'pending' | 'processing' | 'completed' | 'failed'
  ai_category?: string | null
  ai_confidence?: number | null
  ai_classification_reason?: string | null
  ai_summary?: string | null
  ai_extracted_fields?: Record<string, any> | null
  ai_keywords?: string[] | null
  ai_suggested_priority?: 'Low' | 'Medium' | 'High' | 'Critical' | string | null
  ai_priority_explanation?: string | null
  ai_action_items?: string[] | null
  ai_analyzed_at?: string | null
  ai_model?: string | null
  ai_error_message?: string | null

  // Agentic AI & Human Review fields
  ai_review_status?: 'not_required' | 'pending_review' | 'auto_approved' | 'approved' | 'rejected' | string | null
  ai_review_reasons?: string[] | null
  ai_reviewer_notes?: string | null
  ai_reviewed_at?: string | null
  ai_routing?: {
    target_department?: string
    routing_reason?: string
    escalation_required?: boolean
  } | null
  ai_workflow_history?: Array<Record<string, any>> | null

  task_id?: string
  created_at: string | null
  processed_at?: string | null
}

export interface DeleteResponse {
  id: string
  message: string
  deleted: boolean
}

export interface AIAnalysisResult {
  category: string
  confidence: number
  classification_reason: string
  summary: string
  extracted_fields: Record<string, any>
  keywords: string[]
  suggested_priority: 'Low' | 'Medium' | 'High' | 'Critical' | string
  priority_explanation: string
  action_items: string[]
  analyzed_at?: string | null
  model?: string | null
}

export interface DocumentAnalysisResponse {
  id: string
  filename: string
  ai_status: 'pending' | 'processing' | 'completed' | 'failed' | string
  analysis?: AIAnalysisResult | null
  error_message?: string | null

  // Agentic workflow extensions
  review_status?: 'not_required' | 'pending_review' | 'auto_approved' | 'approved' | 'rejected' | string | null
  requires_human_review?: boolean
  review_trigger_reasons?: string[] | null
  routing?: {
    target_department?: string
    routing_reason?: string
    escalation_required?: boolean
  } | null
  workflow_history?: Array<Record<string, any>> | null
}

export interface HumanReviewRequest {
  decision: 'approved' | 'rejected'
  notes?: string
  target_department?: Department | string
  priority?: 'Low' | 'Medium' | 'High' | 'Critical' | string
}

export interface HumanReviewResponse {
  id: string
  filename: string
  review_status: string
  decision: string
  department?: string | null
  priority?: string | null
  reviewer_notes?: string | null
  reviewed_at: string
  message: string
}

export interface AIStatusResponse {
  configured: boolean
  model: string
  provider: string
  message: string
}

export interface TextExtractionResponse {
  id: string
  filename: string
  status: DocumentStatus
  extraction_status: string
  extraction_method?: string | null
  page_count?: number | null
  extracted_text_path?: string | null
  extracted_at?: string | null
  extracted_text?: string | null
  error_message?: string | null
}

export interface DocumentTextResponse {
  id: string
  filename: string
  extraction_status: string
  extraction_method?: string | null
  page_count?: number | null
  extracted_at?: string | null
  text: string
}

export interface DocumentUploadResponse {
  message: string
  id?: string
  filename: string
  content_type: string
  file_size?: number
  status: DocumentStatus
  task_id: string
  created_at?: string
}

export interface DocumentListResponse {
  documents: Document[]
  total: number
}

export interface ChartEntry {
  dept: string
  docs: number
}

export interface CategoryChartEntry {
  category: string
  count: number
}

export interface PriorityChartEntry {
  priority: string
  count: number
}

export interface StatsResponse {
  total_documents: number
  processed_today: number
  pending_review: number
  ocr_completed?: number
  ai_analyzed?: number
  pending_ai?: number
  departments_active: number
  chart_data: ChartEntry[]
  category_chart?: CategoryChartEntry[]
  priority_chart?: PriorityChartEntry[]
}
