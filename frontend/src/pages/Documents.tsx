import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  FileText, RefreshCw, Upload, AlertCircle, Clock,
  CheckCircle2, XCircle, Download, Trash2, Loader2,
  Eye, Copy, Check, X, Sparkles, FileCode, Info,
  Brain, Tag, AlertTriangle, ShieldAlert
} from 'lucide-react'
import api, { API_BASE_URL } from '../lib/api'
import {
  Document, DocumentListResponse, DocumentTextResponse,
  TextExtractionResponse, DocumentAnalysisResponse,
  AIAnalysisResult, AIStatusResponse, HumanReviewResponse
} from '../types/document'
import { useToastNotification } from '../context/ToastContext'
import HumanReviewModal from '../components/HumanReviewModal'
import AIAnalysisModal from '../components/AIAnalysisModal'

interface OCRStatus {
  available: boolean
  path: string | null
  version: string | null
}

interface AnalysisModalData {
  doc: Document
  analysis: AIAnalysisResult
  reviewStatus?: string
  reviewReasons?: string[]
  reviewerNotes?: string
}

export default function Documents() {
  const { showToast } = useToastNotification()

  const [documents, setDocuments] = useState<Document[]>([])
  const [total, setTotal] = useState<number>(0)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  // OCR state
  const [extractingId, setExtractingId] = useState<string | null>(null)
  const [ocrStatus, setOcrStatus] = useState<OCRStatus | null>(null)

  // AI state
  const [analyzingId, setAnalyzingId] = useState<string | null>(null)
  const [aiStatus, setAiStatus] = useState<AIStatusResponse | null>(null)

  // Modals state
  const [selectedDocText, setSelectedDocText] = useState<DocumentTextResponse | null>(null)
  const [isLoadingText, setIsLoadingText] = useState<boolean>(false)
  const [isCopied, setIsCopied] = useState<boolean>(false)

  const [selectedAnalysis, setSelectedAnalysis] = useState<AnalysisModalData | null>(null)
  const [reviewModalDoc, setReviewModalDoc] = useState<Document | null>(null)

  const fetchOcrStatus = useCallback(async () => {
    try {
      const res = await api.get<OCRStatus>('/documents/ocr-status')
      setOcrStatus(res.data)
    } catch {
      // Non-blocking
    }
  }, [])

  const fetchAiStatus = useCallback(async () => {
    try {
      const res = await api.get<AIStatusResponse>('/documents/ai-status')
      setAiStatus(res.data)
    } catch {
      // Non-blocking
    }
  }, [])

  const fetchDocuments = useCallback(async (isManualRefresh = false) => {
    setIsLoading(true)
    setErrorMessage(null)

    try {
      const response = await api.get<DocumentListResponse>('/documents')
      const data = response.data
      setDocuments(data.documents || [])
      setTotal(data.total ?? (data.documents ? data.documents.length : 0))

      if (isManualRefresh) {
        showToast('Document list updated.', 'info')
      }
    } catch (err: any) {
      const msg = err.message || 'Failed to load documents from backend.'
      setErrorMessage(msg)
      showToast(msg, 'error')
    } finally {
      setIsLoading(false)
    }
  }, [showToast])

  useEffect(() => {
    fetchDocuments()
    fetchOcrStatus()
    fetchAiStatus()
  }, [fetchDocuments, fetchOcrStatus, fetchAiStatus])

  const handleDownload = (doc: Document) => {
    window.open(`${API_BASE_URL}/api/v1/documents/${doc.id}/download`, '_blank')
  }

  const handleDeleteRequest = (id: string) => {
    setConfirmDeleteId(id)
  }

  const handleDeleteCancel = () => {
    setConfirmDeleteId(null)
  }

  const handleDeleteConfirm = async (id: string) => {
    setConfirmDeleteId(null)
    setDeletingId(id)
    try {
      await api.delete(`/documents/${id}`)
      showToast('Document deleted successfully.', 'success')
      await fetchDocuments()
    } catch (err: any) {
      const msg = err.message || 'Failed to delete document.'
      showToast(msg, 'error')
    } finally {
      setDeletingId(null)
    }
  }

  const handleExtractText = async (doc: Document) => {
    setExtractingId(doc.id)
    try {
      const res = await api.post<TextExtractionResponse>(`/documents/${doc.id}/extract`)
      showToast(`Text extracted successfully using ${res.data.extraction_method?.toUpperCase()} (${res.data.page_count} page${(res.data.page_count ?? 1) > 1 ? 's' : ''})!`, 'success')
      await fetchDocuments()
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Text extraction failed.'
      showToast(msg, 'error')
      await fetchDocuments()
    } finally {
      setExtractingId(null)
    }
  }

  const handleAnalyzeWithAI = async (doc: Document, force = false) => {
    setAnalyzingId(doc.id)
    try {
      const res = await api.post<DocumentAnalysisResponse>(`/documents/${doc.id}/analyze?force=${force}`)
      await fetchDocuments()
      if (res.data.analysis) {
        const updatedDoc: Document = {
          ...doc,
          department: res.data.routing?.target_department || doc.department || 'Operations',
          priority: res.data.analysis.suggested_priority || doc.ai_suggested_priority || 'Medium',
          ai_suggested_priority: res.data.analysis.suggested_priority || doc.ai_suggested_priority || 'Medium',
          ai_review_status: res.data.review_status || 'auto_approved',
          ai_review_reasons: res.data.review_trigger_reasons || [],
        }

        if (res.data.requires_human_review || res.data.review_status === 'pending_review') {
          showToast('Document analysis requires mandatory Human Review.', 'info')
          setReviewModalDoc(updatedDoc)
        } else {
          showToast(`AI Analysis completed: ${res.data.analysis.category} (${res.data.analysis.suggested_priority} Priority)`, 'success')
          setSelectedAnalysis({
            doc: updatedDoc,
            analysis: res.data.analysis,
            reviewStatus: res.data.review_status || 'auto_approved',
            reviewReasons: res.data.review_trigger_reasons || [],
          })
        }
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Gemini AI analysis failed.'
      showToast(msg, 'error')
      await fetchDocuments()
    } finally {
      setAnalyzingId(null)
    }
  }

  const handleViewAnalysis = async (doc: Document) => {
    try {
      const res = await api.get<DocumentAnalysisResponse>(`/documents/${doc.id}/analysis`)
      if (res.data.analysis) {
        setSelectedAnalysis({
          doc: {
            ...doc,
            department: res.data.routing?.target_department || doc.department || 'Operations',
            priority: res.data.analysis.suggested_priority || doc.ai_suggested_priority || doc.priority || 'Medium',
            ai_suggested_priority: res.data.analysis.suggested_priority || doc.ai_suggested_priority || 'Medium',
            ai_review_status: res.data.review_status || doc.ai_review_status,
            ai_review_reasons: res.data.review_trigger_reasons || doc.ai_review_reasons,
          },
          analysis: res.data.analysis,
          reviewStatus: res.data.review_status || doc.ai_review_status || 'auto_approved',
          reviewReasons: res.data.review_trigger_reasons || doc.ai_review_reasons || [],
          reviewerNotes: doc.ai_reviewer_notes || undefined,
        })
      } else {
        showToast('No AI analysis results available yet for this document.', 'info')
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to load AI analysis.'
      showToast(msg, 'error')
    }
  }

  const handleReviewDecisionSubmitted = (response: HumanReviewResponse) => {
    setDocuments((prev) =>
      prev.map((d) => {
        if (d.id === response.id) {
          return {
            ...d,
            department: response.department || d.department,
            priority: response.priority || d.priority,
            ai_suggested_priority: response.priority || d.ai_suggested_priority,
            ai_review_status: response.review_status,
            ai_reviewer_notes: response.reviewer_notes,
            ai_reviewed_at: response.reviewed_at,
          }
        }
        return d
      })
    )
    if (selectedAnalysis && selectedAnalysis.doc.id === response.id) {
      setSelectedAnalysis({
        ...selectedAnalysis,
        doc: {
          ...selectedAnalysis.doc,
          department: response.department || selectedAnalysis.doc.department,
          priority: response.priority || selectedAnalysis.doc.priority,
          ai_suggested_priority: response.priority || selectedAnalysis.doc.ai_suggested_priority,
          ai_review_status: response.review_status,
          ai_reviewer_notes: response.reviewer_notes,
        },
        reviewStatus: response.review_status,
        reviewerNotes: response.reviewer_notes || undefined,
      })
    }
    setReviewModalDoc(null)
  }

  const handleViewText = async (doc: Document) => {
    setIsLoadingText(true)
    setIsCopied(false)
    try {
      const res = await api.get<DocumentTextResponse>(`/documents/${doc.id}/text`)
      setSelectedDocText(res.data)
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to load extracted text.'
      showToast(msg, 'error')
    } finally {
      setIsLoadingText(false)
    }
  }

  const handleCopyText = () => {
    if (!selectedDocText?.text) return
    navigator.clipboard.writeText(selectedDocText.text)
    setIsCopied(true)
    setTimeout(() => setIsCopied(false), 2000)
    showToast('Extracted text copied to clipboard.', 'info')
  }

  const handleDownloadTextFile = () => {
    if (!selectedDocText) return
    const blob = new Blob([selectedDocText.text], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${selectedDocText.filename.replace(/\.[^/.]+$/, '')}_extracted.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const formatFileSize = (bytes?: number) => {
    if (!bytes && bytes !== 0) return '—'
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
  }

  const formatDate = (isoString?: string | null) => {
    if (!isoString) return '—'
    try {
      const d = new Date(isoString)
      return d.toLocaleString()
    } catch {
      return isoString
    }
  }

  const renderPriorityBadge = (priority?: string | null) => {
    switch (priority) {
      case 'Critical':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-800 border border-red-300">
            <AlertTriangle className="w-3 h-3 text-red-600" /> Critical
          </span>
        )
      case 'High':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-orange-100 text-orange-800 border border-orange-300">
            High
          </span>
        )
      case 'Medium':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 border border-amber-300">
            Medium
          </span>
        )
      case 'Low':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">
            Low
          </span>
        )
      default:
        return null
    }
  }

  const renderCategoryBadge = (category?: string | null) => {
    if (!category) return null
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 truncate max-w-[150px]">
        <Tag className="w-3 h-3 flex-shrink-0" /> {category}
      </span>
    )
  }

  const renderAIBadge = (doc: Document) => {
    const isAnalyzing = analyzingId === doc.id
    if (isAnalyzing) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800 animate-pulse">
          <Brain className="w-3.5 h-3.5 animate-spin text-purple-600" /> Analyzing...
        </span>
      )
    }

    if (doc.ai_status === 'completed' && doc.ai_category) {
      const effPriority = doc.ai_suggested_priority || doc.priority || 'Medium'
      return (
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 flex-wrap">
            {renderCategoryBadge(doc.ai_category)}
            {renderPriorityBadge(effPriority)}
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            {doc.ai_review_status === 'pending_review' ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300 animate-pulse">
                <ShieldAlert className="w-3 h-3 text-amber-600" />
                Review Pending
              </span>
            ) : doc.ai_review_status === 'approved' ? (
              <span
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800"
                title={doc.ai_reviewer_notes || 'Approved'}
              >
                <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                Approved
              </span>
            ) : doc.ai_review_status === 'rejected' ? (
              <span
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-red-100 text-red-800"
                title={doc.ai_reviewer_notes || 'Rejected'}
              >
                <XCircle className="w-3 h-3 text-red-600" />
                Rejected
              </span>
            ) : null}
            {doc.ai_confidence !== undefined && doc.ai_confidence !== null && (
              <span className="text-[10px] text-gray-500 font-mono">
                {Math.round(doc.ai_confidence * 100)}%
              </span>
            )}
          </div>
        </div>
      )
    }

    if (doc.ai_status === 'failed') {
      return (
        <div className="space-y-0.5" title={doc.ai_error_message || 'AI Analysis failed'}>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
            <XCircle className="w-3 h-3" /> AI Failed
          </span>
          {doc.ai_error_message && (
            <p className="text-[10px] text-red-600 truncate max-w-[140px]" title={doc.ai_error_message}>
              {doc.ai_error_message}
            </p>
          )}
        </div>
      )
    }

    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600 border border-gray-200">
        <Clock className="w-3 h-3" /> Not Analyzed
      </span>
    )
  }

  const renderExtractionBadge = (doc: Document) => {
    const status = doc.extraction_status || (doc.extracted_text ? 'completed' : 'pending')

    if (extractingId === doc.id) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 animate-pulse">
          <Loader2 className="w-3 h-3 animate-spin" /> Extracting OCR...
        </span>
      )
    }

    switch (status) {
      case 'completed':
        return (
          <div className="space-y-0.5">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
              <CheckCircle2 className="w-3 h-3" /> OCR Ready
            </span>
            <div className="text-[11px] text-gray-500 font-mono">
              {doc.extraction_method === 'pymupdf' ? 'PyMuPDF' : doc.extraction_method === 'tesseract' ? 'Tesseract' : doc.extraction_method || 'OCR'}
              {doc.page_count ? ` • ${doc.page_count}p` : ''}
            </div>
          </div>
        )
      case 'processing':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
            <RefreshCw className="w-3 h-3 animate-spin" /> Processing
          </span>
        )
      case 'failed':
        return (
          <div className="space-y-0.5">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800" title={doc.error_message || 'Extraction failed'}>
              <XCircle className="w-3 h-3" /> Failed
            </span>
            {doc.error_message && (
              <p className="text-[10px] text-red-600 truncate max-w-[140px]" title={doc.error_message}>
                {doc.error_message}
              </p>
            )}
          </div>
        )
      case 'pending':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
            <Clock className="w-3 h-3" /> Pending OCR
          </span>
        )
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Metro Documents</h1>
          <p className="text-gray-500 text-sm mt-1">
            Intelligent repository with OCR extraction, classification & LangGraph Agentic AI automation ({total} total).
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { fetchDocuments(true); fetchOcrStatus(); fetchAiStatus() }}
            disabled={isLoading}
            className="flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors shadow-sm"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <Link
            to="/upload"
            className="flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-white bg-metro-blue rounded-lg hover:bg-blue-800 transition-colors shadow-sm"
          >
            <Upload className="w-4 h-4" />
            Upload New
          </Link>
        </div>
      </div>

      {/* Engine & AI Status Bar */}
      <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 px-4 flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex flex-wrap items-center gap-2 text-slate-700">
          <FileCode className="w-4 h-4 text-metro-blue flex-shrink-0" />
          <span className="font-semibold text-slate-900">Services:</span>
          
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-medium">
            <CheckCircle2 className="w-3 h-3" /> PyMuPDF: Ready
          </span>

          {ocrStatus?.available ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-medium">
              <CheckCircle2 className="w-3 h-3" /> Tesseract: v{ocrStatus.version || 'Active'}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-200 text-slate-700 font-medium" title="Install Tesseract-OCR for image text extraction">
              <Info className="w-3 h-3" /> Tesseract: Standby
            </span>
          )}

          {aiStatus?.configured ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-purple-100 text-purple-800 font-semibold border border-purple-200">
              <Brain className="w-3 h-3 text-purple-600" /> LangGraph AI: {aiStatus.model}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-100 text-amber-800 font-medium border border-amber-200" title="Set GEMINI_API_KEY in backend/.env">
              <AlertTriangle className="w-3 h-3 text-amber-600" /> Gemini API Key Missing (Add in backend/.env)
            </span>
          )}
        </div>
        <div className="text-slate-500">
          Automated multi-agent classification, routing & human-in-the-loop review
        </div>
      </div>

      {/* Error alert */}
      {errorMessage && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3 text-red-800">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-sm font-semibold">Error Loading Documents</h4>
            <p className="text-sm mt-0.5">{errorMessage}</p>
          </div>
          <button
            onClick={() => fetchDocuments()}
            className="px-3 py-1 bg-red-100 hover:bg-red-200 text-red-800 rounded text-xs font-medium transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Content */}
      {isLoading && documents.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border p-12 text-center">
          <RefreshCw className="w-8 h-8 text-metro-blue animate-spin mx-auto mb-3" />
          <p className="text-gray-600 font-medium">Fetching documents from backend...</p>
        </div>
      ) : documents.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border p-12 text-center space-y-4">
          <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center mx-auto">
            <FileText className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">No documents found</h3>
            <p className="text-sm text-gray-500 max-w-sm mx-auto mt-1">
              No documents have been uploaded to DocDeclutter yet.
            </p>
          </div>
          <Link
            to="/upload"
            className="inline-flex items-center gap-2 px-4 py-2 bg-metro-blue text-white rounded-lg text-sm font-medium hover:bg-blue-800 transition-colors shadow-sm"
          >
            <Upload className="w-4 h-4" />
            Upload First Document
          </Link>
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-600">
              <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500 border-b">
                <tr>
                  <th scope="col" className="px-6 py-3.5">Document</th>
                  <th scope="col" className="px-6 py-3.5">AI Classification</th>
                  <th scope="col" className="px-6 py-3.5">OCR Status</th>
                  <th scope="col" className="px-6 py-3.5">Department</th>
                  <th scope="col" className="px-6 py-3.5">Size</th>
                  <th scope="col" className="px-6 py-3.5">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {documents.map((doc) => {
                  const isExtracted = doc.extraction_status === 'completed' || !!doc.extracted_text
                  const isExtracting = extractingId === doc.id
                  const isAnalyzed = doc.ai_status === 'completed' && !!doc.ai_category
                  const isAnalyzing = analyzingId === doc.id
                  const isPendingReview = doc.ai_review_status === 'pending_review'

                  return (
                    <tr
                      key={doc.id}
                      className={`hover:bg-gray-50 transition-colors ${deletingId === doc.id ? 'opacity-50' : ''}`}
                    >
                      {/* Document info */}
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-blue-50 text-blue-600 rounded-lg flex-shrink-0">
                            <FileText className="w-4 h-4" />
                          </div>
                          <div className="min-w-0">
                            <p className="font-semibold text-gray-900 truncate max-w-xs sm:max-w-md">
                              {doc.filename}
                            </p>
                            <p className="text-xs text-gray-400 font-mono truncate max-w-xs">
                              {doc.id}
                            </p>
                          </div>
                        </div>
                      </td>

                      {/* AI Classification & Priority */}
                      <td className="px-6 py-4">
                        {renderAIBadge(doc)}
                      </td>

                      {/* OCR Extraction */}
                      <td className="px-6 py-4 whitespace-nowrap">
                        {renderExtractionBadge(doc)}
                      </td>

                      {/* Department */}
                      <td className="px-6 py-4 whitespace-nowrap">
                        {doc.department ? (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                            {doc.department}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-400 italic">Unassigned</span>
                        )}
                      </td>

                      {/* Size */}
                      <td className="px-6 py-4 whitespace-nowrap text-gray-700 text-xs">
                        {formatFileSize(doc.file_size)}
                      </td>

                      {/* Actions */}
                      <td className="px-6 py-4 whitespace-nowrap">
                        {deletingId === doc.id ? (
                          <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                        ) : confirmDeleteId === doc.id ? (
                          /* Inline delete confirmation */
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-red-600 font-medium">Delete?</span>
                            <button
                              onClick={() => handleDeleteConfirm(doc.id)}
                              className="px-2 py-1 bg-red-600 text-white rounded text-xs font-medium hover:bg-red-700 transition-colors"
                            >
                              Yes
                            </button>
                            <button
                              onClick={handleDeleteCancel}
                              className="px-2 py-1 bg-gray-200 text-gray-700 rounded text-xs font-medium hover:bg-gray-300 transition-colors"
                            >
                              No
                            </button>
                          </div>
                        ) : (
                          /* Normal action buttons */
                          <div className="flex items-center gap-1.5 flex-wrap">
                            {/* Human Review Button if Pending Review */}
                            {isPendingReview && (
                              <button
                                onClick={() => setReviewModalDoc(doc)}
                                title="Review and sign-off document"
                                className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-bold text-white bg-amber-600 border border-amber-600 rounded-lg hover:bg-amber-700 transition-colors shadow-sm animate-pulse"
                              >
                                <ShieldAlert className="w-3.5 h-3.5" />
                                <span>Review</span>
                              </button>
                            )}

                            {/* AI Analyze / Re-analyze button */}
                            <button
                              onClick={() => handleAnalyzeWithAI(doc, isAnalyzed)}
                              disabled={isAnalyzing || isExtracting}
                              title={isAnalyzed ? 'Re-analyze with Gemini AI' : 'Analyze with Gemini AI'}
                              className={`inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors border shadow-sm ${
                                isAnalyzed
                                  ? 'text-purple-700 bg-purple-50 border-purple-200 hover:bg-purple-100'
                                  : 'text-white bg-indigo-600 border-indigo-600 hover:bg-indigo-700'
                              } disabled:opacity-50`}
                            >
                              {isAnalyzing ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <Brain className="w-3.5 h-3.5" />
                              )}
                              <span>{isAnalyzing ? 'Analyzing...' : isAnalyzed ? 'Re-analyze' : 'Analyze AI'}</span>
                            </button>

                            {/* View AI Analysis Modal Button */}
                            {isAnalyzed && (
                              <button
                                onClick={() => handleViewAnalysis(doc)}
                                title="View Gemini AI analysis & extracted fields"
                                className="inline-flex items-center gap-1 px-2 py-1.5 text-xs font-medium text-purple-700 bg-purple-50 border border-purple-200 rounded-lg hover:bg-purple-100 transition-colors shadow-sm"
                              >
                                <Sparkles className="w-3.5 h-3.5 text-purple-600" />
                                <span>Analysis</span>
                              </button>
                            )}

                            {/* View Extracted OCR Text */}
                            {isExtracted ? (
                              <button
                                onClick={() => handleViewText(doc)}
                                title="View extracted OCR text"
                                className="inline-flex items-center gap-1 px-2 py-1.5 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg hover:bg-emerald-100 transition-colors shadow-sm"
                              >
                                <Eye className="w-3.5 h-3.5" />
                                <span>Text</span>
                              </button>
                            ) : (
                              <button
                                onClick={() => handleExtractText(doc)}
                                disabled={isExtracting}
                                title="Extract text using OCR"
                                className="inline-flex items-center gap-1 px-2 py-1.5 text-xs font-medium text-gray-700 bg-gray-50 border border-gray-200 rounded-lg hover:bg-gray-100 transition-colors shadow-sm disabled:opacity-50"
                              >
                                {isExtracting ? (
                                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                ) : (
                                  <FileCode className="w-3.5 h-3.5" />
                                )}
                                <span>OCR</span>
                              </button>
                            )}

                            {/* Download Original File */}
                            {doc.file_path && (
                              <button
                                onClick={() => handleDownload(doc)}
                                title="Download original file"
                                className="inline-flex items-center gap-1 px-2 py-1.5 text-xs font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors"
                              >
                                <Download className="w-3.5 h-3.5" />
                              </button>
                            )}

                            {/* Delete */}
                            <button
                              onClick={() => handleDeleteRequest(doc.id)}
                              title="Delete document"
                              className="inline-flex items-center gap-1 px-2 py-1.5 text-xs font-medium text-red-700 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 transition-colors"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Human Review Modal from Documents Table */}
      {reviewModalDoc && (
        <HumanReviewModal
          isOpen={!!reviewModalDoc}
          documentId={reviewModalDoc.id}
          filename={reviewModalDoc.filename}
          category={reviewModalDoc.ai_category || 'Incident Report'}
          confidence={reviewModalDoc.ai_confidence || 0.9}
          suggestedPriority={reviewModalDoc.ai_suggested_priority || reviewModalDoc.priority || 'High'}
          targetDepartment={reviewModalDoc.department || 'Operations'}
          reviewReasons={reviewModalDoc.ai_review_reasons || []}
          summary={reviewModalDoc.ai_summary || reviewModalDoc.summary || ''}
          onClose={() => setReviewModalDoc(null)}
          onDecisionSubmitted={handleReviewDecisionSubmitted}
        />
      )}

      {/* AI Analysis Modal */}
      {selectedAnalysis && (
        <AIAnalysisModal
          isOpen={!!selectedAnalysis}
          doc={selectedAnalysis.doc}
          analysis={selectedAnalysis.analysis}
          reviewStatus={selectedAnalysis.reviewStatus}
          reviewReasons={selectedAnalysis.reviewReasons}
          reviewerNotes={selectedAnalysis.reviewerNotes}
          isReanalyzing={analyzingId === selectedAnalysis.doc.id}
          onClose={() => setSelectedAnalysis(null)}
          onReanalyze={(doc) => handleAnalyzeWithAI(doc, true)}
          onOpenReview={(doc) => {
            setSelectedAnalysis(null)
            setReviewModalDoc(doc)
          }}
        />
      )}

      {/* Extracted Text Modal (Preserved) */}
      {(selectedDocText || isLoadingText) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[85vh] flex flex-col overflow-hidden border border-gray-200">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-slate-50">
              <div className="min-w-0 flex-1 pr-4">
                <div className="flex items-center gap-2">
                  <span className="p-1.5 bg-emerald-100 text-emerald-700 rounded-lg">
                    <FileText className="w-4 h-4" />
                  </span>
                  <h3 className="font-bold text-gray-900 text-base truncate">
                    {selectedDocText?.filename || 'Extracted Document Text'}
                  </h3>
                </div>
                {selectedDocText && (
                  <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                    <span className="inline-flex items-center gap-1 font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                      Method: {selectedDocText.extraction_method?.toUpperCase()}
                    </span>
                    <span>Pages: {selectedDocText.page_count ?? 1}</span>
                    <span>Length: {selectedDocText.text.length} chars</span>
                    <span>Words: {selectedDocText.text.trim().split(/\s+/).filter(Boolean).length}</span>
                  </div>
                )}
              </div>
              <button
                onClick={() => setSelectedDocText(null)}
                className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-200 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto flex-1 bg-gray-50">
              {isLoadingText ? (
                <div className="py-20 text-center">
                  <Loader2 className="w-8 h-8 animate-spin text-metro-blue mx-auto mb-3" />
                  <p className="text-gray-500 text-sm">Loading extracted text...</p>
                </div>
              ) : selectedDocText?.text ? (
                <div className="bg-white rounded-xl p-5 border border-gray-200 shadow-inner font-mono text-xs sm:text-sm text-gray-800 whitespace-pre-wrap leading-relaxed select-text">
                  {selectedDocText.text}
                </div>
              ) : (
                <div className="py-12 text-center text-gray-400 text-sm">
                  No text content was found in this document.
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3.5 bg-white border-t border-gray-100 flex items-center justify-between gap-3">
              <div className="text-xs text-gray-400">
                Extracted: {formatDate(selectedDocText?.extracted_at)}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleCopyText}
                  disabled={!selectedDocText?.text}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors shadow-sm disabled:opacity-50"
                >
                  {isCopied ? <Check className="w-3.5 h-3.5 text-green-600" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{isCopied ? 'Copied!' : 'Copy Text'}</span>
                </button>
                <button
                  onClick={handleDownloadTextFile}
                  disabled={!selectedDocText?.text}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-metro-blue bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors shadow-sm disabled:opacity-50"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download .txt</span>
                </button>
                <button
                  onClick={() => setSelectedDocText(null)}
                  className="px-3.5 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
