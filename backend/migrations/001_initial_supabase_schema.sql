-- =================================================================
-- DocDeclutter – Supabase Database Schema & Storage Setup
-- Version: 001_initial_supabase_schema.sql
-- =================================================================

-- 1. Create Private Storage Bucket 'metro-documents'
-- Allows PDF, PNG, JPG, JPEG, and text files up to 10 MB.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'metro-documents',
    'metro-documents',
    false, -- STRICTLY PRIVATE: Access via authenticated backend signed URLs
    10485760, -- 10 MB maximum file size limit
    ARRAY[
        'application/pdf',
        'image/png',
        'image/jpeg',
        'image/jpg',
        'text/plain'
    ]::text[]
)
ON CONFLICT (id) DO UPDATE SET
    public = false,
    file_size_limit = 10485760,
    allowed_mime_types = ARRAY[
        'application/pdf',
        'image/png',
        'image/jpeg',
        'image/jpg',
        'text/plain'
    ]::text[];

-- 2. Create Documents Table
CREATE TABLE IF NOT EXISTS public.documents (
    -- Identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_size BIGINT NOT NULL,

    -- Core Metro Attributes
    department TEXT,
    priority TEXT,
    summary TEXT,
    document_status TEXT NOT NULL DEFAULT 'pending',

    -- Text Extraction / OCR
    extraction_status TEXT NOT NULL DEFAULT 'pending',
    extraction_method TEXT,
    page_count INT,
    extracted_text_path TEXT,
    extracted_text TEXT,
    extracted_at TIMESTAMPTZ,
    error_message TEXT,

    -- Gemini AI Analysis
    ai_status TEXT DEFAULT 'pending',
    ai_category TEXT,
    ai_confidence NUMERIC(4, 3),
    ai_classification_reason TEXT,
    ai_summary TEXT,
    ai_extracted_fields JSONB DEFAULT '{}'::jsonb,
    ai_keywords JSONB DEFAULT '[]'::jsonb,
    ai_suggested_priority TEXT,
    ai_priority_explanation TEXT,
    ai_action_items JSONB DEFAULT '[]'::jsonb,
    ai_model TEXT,
    ai_analyzed_at TIMESTAMPTZ,
    ai_error_message TEXT,

    -- LangGraph Agentic AI & Human-in-the-Loop Review
    ai_review_status TEXT DEFAULT 'not_required',
    ai_review_reasons JSONB DEFAULT '[]'::jsonb,
    ai_reviewer_notes TEXT,
    ai_reviewed_at TIMESTAMPTZ,
    ai_routing JSONB DEFAULT '{}'::jsonb,
    ai_workflow_history JSONB DEFAULT '[]'::jsonb,

    -- Operational Tracking
    task_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    processed_at TIMESTAMPTZ
);

-- 3. Indexes for High-Performance Querying & Dashboard Metrics
CREATE INDEX IF NOT EXISTS idx_documents_status ON public.documents (document_status);
CREATE INDEX IF NOT EXISTS idx_documents_ai_status ON public.documents (ai_status);
CREATE INDEX IF NOT EXISTS idx_documents_ai_category ON public.documents (ai_category);
CREATE INDEX IF NOT EXISTS idx_documents_ai_priority ON public.documents (ai_suggested_priority);
CREATE INDEX IF NOT EXISTS idx_documents_department ON public.documents (department);
CREATE INDEX IF NOT EXISTS idx_documents_review_status ON public.documents (ai_review_status);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON public.documents (created_at DESC);

-- 4. Automatically Update 'updated_at' on Row Modification
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_documents_updated_at ON public.documents;
CREATE TRIGGER trigger_documents_updated_at
    BEFORE UPDATE ON public.documents
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

-- 5. Row Level Security (RLS)
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

-- Service Role Key (Backend Server): Full administrative control
CREATE POLICY "Service Role Full Access" ON public.documents
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Authenticated Users: Read-only access policy (ready for Phase with User Auth)
CREATE POLICY "Authenticated Read Access" ON public.documents
    FOR SELECT
    TO authenticated
    USING (true);
