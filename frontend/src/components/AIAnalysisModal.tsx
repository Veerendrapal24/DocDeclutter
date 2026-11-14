import {
  Brain, X, Sparkles, FileText, Layers, ShieldCheck, ListChecks,
  Tag, AlertTriangle, RefreshCw, CheckCircle2, XCircle
} from 'lucide-react'
import { AIAnalysisResult, Document } from '../types/document'

interface AIAnalysisModalProps {
  isOpen: boolean
  doc: Document | null
  analysis: AIAnalysisResult | null
  reviewStatus?: string | null
  reviewReasons?: string[] | null
  reviewerNotes?: string | null
  isReanalyzing?: boolean
  onClose: () => void
  onReanalyze?: (doc: Document) => void
  onOpenReview?: (doc: Document, analysis: AIAnalysisResult) => void
}

export default function AIAnalysisModal({
  isOpen,
  doc,
  analysis,
  reviewStatus,
  reviewReasons = [],
  reviewerNotes,
  isReanalyzing = false,
  onClose,
  onReanalyze,
  onOpenReview,
}: AIAnalysisModalProps) {
  if (!isOpen || !doc || !analysis) return null

  const effectiveReviewStatus = reviewStatus || doc.ai_review_status || 'auto_approved'
  const effectiveReviewReasons = (reviewReasons && reviewReasons.length > 0)
    ? reviewReasons
    : (doc.ai_review_reasons || [])

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
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">
            Low
          </span>
        )
    }
  }

  const renderReviewStatusBanner = () => {
    if (effectiveReviewStatus === 'pending_review') {
      return (
        <div className="bg-amber-50 border border-amber-300 rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-sm">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-bold text-amber-900">
                Action Required: Human-in-the-Loop Review Pending
              </h4>
              <p className="text-xs text-amber-800 mt-0.5">
                {effectiveReviewReasons.length > 0
                  ? effectiveReviewReasons.join(' • ')
                  : 'Document requires human verification under safety/critical criteria.'}
              </p>
            </div>
          </div>
          {onOpenReview && (
            <button
              onClick={() => onOpenReview(doc, analysis)}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white font-semibold text-xs rounded-lg shadow-sm transition-colors whitespace-nowrap"
            >
              <ShieldCheck className="w-4 h-4" />
              <span>Review & Approve</span>
            </button>
          )}
        </div>
      )
    }

    if (effectiveReviewStatus === 'approved') {
      return (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 px-4 flex items-center justify-between text-xs text-emerald-800">
          <div className="flex items-center gap-2 font-semibold">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>Human Review Decision: APPROVED</span>
          </div>
          {reviewerNotes && (
            <span className="text-emerald-700 italic truncate max-w-sm">
              "{reviewerNotes}"
            </span>
          )}
        </div>
      )
    }

    if (effectiveReviewStatus === 'rejected') {
      return (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 px-4 flex items-center justify-between text-xs text-red-800">
          <div className="flex items-center gap-2 font-semibold">
            <XCircle className="w-4 h-4 text-red-600" />
            <span>Human Review Decision: REJECTED</span>
          </div>
          {reviewerNotes && (
            <span className="text-red-700 italic truncate max-w-sm">
              "{reviewerNotes}"
            </span>
          )}
        </div>
      )
    }

    return null
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden border border-gray-200">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-slate-900 text-white">
          <div className="min-w-0 flex-1 pr-4">
            <div className="flex items-center gap-2.5">
              <span className="p-1.5 bg-purple-500/20 text-purple-300 rounded-lg border border-purple-400/30">
                <Brain className="w-5 h-5 text-purple-400" />
              </span>
              <div>
                <h3 className="font-bold text-white text-base truncate">
                  {doc.filename}
                </h3>
                <p className="text-xs text-gray-400 font-mono">
                  ID: {doc.id}
                </p>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto flex-1 bg-slate-50 space-y-5">
          {/* Review Status Banner */}
          {renderReviewStatusBanner()}

          {/* Top Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
            {/* Category */}
            <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-sm">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block">Category</span>
              <span className="text-sm font-bold text-gray-900 mt-1 block truncate">{analysis.category}</span>
              <p className="text-[10px] text-gray-500 mt-0.5 font-mono">
                Confidence: {Math.round((analysis.confidence || 0) * 100)}%
              </p>
            </div>

            {/* Suggested Priority */}
            <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-sm">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block">Recommended Priority</span>
              <div className="mt-1">{renderPriorityBadge(analysis.suggested_priority)}</div>
              <p className="text-[10px] text-gray-500 mt-0.5 line-clamp-1" title={analysis.priority_explanation}>
                {analysis.priority_explanation}
              </p>
            </div>

            {/* Department */}
            <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-sm">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block">Assigned Department</span>
              <span className="text-sm font-bold text-blue-800 mt-1 block truncate">
                {doc.department || 'Operations'}
              </span>
              <p className="text-[10px] text-gray-500 mt-0.5">
                Routed by LangGraph
              </p>
            </div>

            {/* Model Info */}
            <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-sm">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block">AI Model</span>
              <div className="mt-1 flex items-center gap-1 text-xs font-semibold text-purple-700 truncate">
                <Sparkles className="w-3.5 h-3.5 text-purple-600 flex-shrink-0" />
                <span className="truncate">{analysis.model || 'gemini-3.5-flash-lite'}</span>
              </div>
              <p className="text-[10px] text-gray-500 mt-0.5">
                {analysis.analyzed_at ? new Date(analysis.analyzed_at).toLocaleTimeString() : 'Recent'}
              </p>
            </div>
          </div>

          {/* Executive Summary */}
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm space-y-2">
            <div className="flex items-center gap-2 text-gray-900 font-bold text-xs uppercase tracking-wider">
              <FileText className="w-4 h-4 text-metro-blue" />
              <span>Executive Document Summary</span>
            </div>
            <p className="text-xs sm:text-sm text-gray-700 leading-relaxed bg-slate-50 p-3.5 rounded-lg border border-slate-100">
              {analysis.summary}
            </p>
            {analysis.classification_reason && (
              <p className="text-xs text-gray-500 italic pt-1">
                Classification rationale: {analysis.classification_reason}
              </p>
            )}
          </div>

          {/* Extracted Entities */}
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm space-y-3">
            <div className="flex items-center gap-2 text-gray-900 font-bold text-xs uppercase tracking-wider">
              <Layers className="w-4 h-4 text-indigo-600" />
              <span>Extracted Structured Information</span>
            </div>
            {analysis.extracted_fields && Object.keys(analysis.extracted_fields).length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {Object.entries(analysis.extracted_fields).map(([key, val]) => (
                  <div key={key} className="bg-gray-50 p-3 rounded-lg border border-gray-200">
                    <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider block">
                      {key.replace(/_/g, ' ')}
                    </span>
                    <span className="text-xs font-semibold text-gray-900 mt-0.5 block break-words">
                      {val !== null && val !== undefined && val !== '' ? String(val) : <span className="text-gray-400 italic">N/A</span>}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400 italic">No specific structured fields extracted.</p>
            )}
          </div>

          {/* Priority Explanation */}
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm space-y-2">
            <div className="flex items-center gap-2 text-gray-900 font-bold text-xs uppercase tracking-wider">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>Priority Recommendation & Evidence</span>
            </div>
            <div className="bg-slate-50 p-3.5 rounded-lg border border-slate-100 text-xs text-gray-700 leading-relaxed">
              {analysis.priority_explanation}
            </div>
          </div>

          {/* Action Items & Keywords Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Action Items */}
            <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm space-y-2">
              <div className="flex items-center gap-2 text-gray-900 font-bold text-xs uppercase tracking-wider">
                <ListChecks className="w-4 h-4 text-indigo-600" />
                <span>Action Items</span>
              </div>
              {analysis.action_items && analysis.action_items.length > 0 ? (
                <ul className="space-y-1.5 text-xs text-gray-700">
                  {analysis.action_items.map((action, idx) => (
                    <li key={idx} className="flex items-start gap-2 bg-slate-50 p-2 rounded border border-slate-100">
                      <span className="w-4 h-4 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold text-[10px] flex-shrink-0 mt-0.5">
                        {idx + 1}
                      </span>
                      <span>{action}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-gray-400 italic">No action items detected.</p>
              )}
            </div>

            {/* Keywords */}
            <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm space-y-2">
              <div className="flex items-center gap-2 text-gray-900 font-bold text-xs uppercase tracking-wider">
                <Tag className="w-4 h-4 text-purple-600" />
                <span>Keywords</span>
              </div>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {analysis.keywords && analysis.keywords.length > 0 ? (
                  analysis.keywords.map((kw, idx) => (
                    <span key={idx} className="px-2.5 py-1 rounded-md text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200">
                      {kw}
                    </span>
                  ))
                ) : (
                  <p className="text-xs text-gray-400 italic">No keywords extracted.</p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3.5 bg-white border-t border-gray-200 flex items-center justify-between gap-3">
          <div className="text-xs text-gray-400">
            DocDeclutter Intelligence Engine • LangGraph Multi-Agent Workflow
          </div>
          <div className="flex items-center gap-2">
            {onReanalyze && (
              <button
                onClick={() => onReanalyze(doc)}
                disabled={isReanalyzing}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-purple-700 bg-purple-50 border border-purple-200 rounded-lg hover:bg-purple-100 transition-colors shadow-sm disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isReanalyzing ? 'animate-spin' : ''}`} />
                <span>{isReanalyzing ? 'Analyzing...' : 'Re-analyze'}</span>
              </button>
            )}
            <button
              onClick={onClose}
              className="px-4 py-1.5 text-xs font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
