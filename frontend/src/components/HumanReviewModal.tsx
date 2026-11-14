import { useState, useEffect } from 'react'
import {
  ShieldAlert, CheckCircle2, XCircle, X, AlertTriangle,
  Building2, Tag, Loader2, Sparkles, FileText
} from 'lucide-react'
import api from '../lib/api'
import { Department, HumanReviewResponse } from '../types/document'
import { useToastNotification } from '../context/ToastContext'

const DEPARTMENTS: Department[] = [
  'Operations',
  'Safety',
  'Technical',
  'Finance',
  'Human Resources',
  'Legal',
  'Administration',
]

const PRIORITIES = ['Low', 'Medium', 'High', 'Critical']

interface HumanReviewModalProps {
  isOpen: boolean
  documentId: string
  filename: string
  category: string
  confidence?: number | null
  suggestedPriority?: string | null
  targetDepartment?: string | null
  reviewReasons?: string[] | null
  summary?: string | null
  onClose: () => void
  onDecisionSubmitted: (response: HumanReviewResponse) => void
}

export default function HumanReviewModal({
  isOpen,
  documentId,
  filename,
  category,
  confidence = 0.9,
  suggestedPriority = 'Medium',
  targetDepartment = 'Operations',
  reviewReasons = [],
  summary,
  onClose,
  onDecisionSubmitted,
}: HumanReviewModalProps) {
  const { showToast } = useToastNotification()

  const [selectedDept, setSelectedDept] = useState<string>(targetDepartment || 'Operations')
  const [selectedPriority, setSelectedPriority] = useState<string>(suggestedPriority || 'Medium')
  const [reviewerNotes, setReviewerNotes] = useState<string>('')
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false)
  const [submittingDecision, setSubmittingDecision] = useState<'approved' | 'rejected' | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen) {
      setSelectedDept(targetDepartment || 'Operations')
      setSelectedPriority(suggestedPriority || 'Medium')
      setReviewerNotes('')
      setErrorMessage(null)
      setIsSubmitting(false)
      setSubmittingDecision(null)
    }
  }, [isOpen, targetDepartment, suggestedPriority])

  if (!isOpen) return null

  const handleDecision = async (decision: 'approved' | 'rejected') => {
    setIsSubmitting(true)
    setSubmittingDecision(decision)
    setErrorMessage(null)

    try {
      const payload = {
        decision,
        notes: reviewerNotes.trim(),
        target_department: selectedDept,
        priority: selectedPriority,
      }

      const res = await api.post<HumanReviewResponse>(`/documents/${documentId}/review`, payload)
      showToast(
        decision === 'approved'
          ? `Document approved and routed to ${selectedDept} department.`
          : `Document rejected. Rejection reason logged in audit trail.`,
        decision === 'approved' ? 'success' : 'info'
      )
      onDecisionSubmitted(res.data)
      onClose()
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to submit review decision.'
      setErrorMessage(msg)
      showToast(msg, 'error')
    } finally {
      setIsSubmitting(false)
      setSubmittingDecision(null)
    }
  }

  const renderPriorityBadge = (pri: string) => {
    switch (pri) {
      case 'Critical':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-red-100 text-red-800 border border-red-300">
            <AlertTriangle className="w-3.5 h-3.5 text-red-600" /> Critical
          </span>
        )
      case 'High':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-orange-100 text-orange-800 border border-orange-300">
            High
          </span>
        )
      case 'Medium':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800 border border-amber-300">
            Medium
          </span>
        )
      case 'Low':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">
            Low
          </span>
        )
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[92vh] flex flex-col overflow-hidden border border-amber-200">
        {/* Header */}
        <div className="px-6 py-4 bg-gradient-to-r from-amber-600 via-orange-600 to-amber-700 text-white flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white/20 rounded-xl backdrop-blur-sm">
              <ShieldAlert className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-lg text-white">Human Review Required</h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-amber-900/40 text-amber-100 border border-amber-400/30">
                  LangGraph HITL
                </span>
              </div>
              <p className="text-xs text-amber-100 mt-0.5 truncate max-w-md">
                {filename}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="p-1.5 text-amber-100 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-5 bg-slate-50 text-sm">
          {/* Error Message */}
          {errorMessage && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-red-800 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Trigger Reasons Banner */}
          <div className="bg-amber-50 border border-amber-300 rounded-xl p-4 space-y-2">
            <div className="flex items-center gap-2 text-amber-900 font-semibold text-xs uppercase tracking-wider">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              <span>Review Triggers & Operational Reasons</span>
            </div>
            <ul className="space-y-1.5 text-xs text-amber-950 pl-6 list-disc">
              {reviewReasons && reviewReasons.length > 0 ? (
                reviewReasons.map((reason, idx) => (
                  <li key={idx} className="font-medium">
                    {reason}
                  </li>
                ))
              ) : (
                <li className="font-medium">
                  Document flagged by Agentic Safety Assessment Policy.
                </li>
              )}
            </ul>
          </div>

          {/* AI Metadata Overview */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {/* Classification */}
            <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-sm space-y-1">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                AI Classification
              </span>
              <div className="flex items-center gap-1.5 text-gray-900 font-bold truncate">
                <Tag className="w-3.5 h-3.5 text-indigo-600 flex-shrink-0" />
                <span className="truncate">{category}</span>
              </div>
              <p className="text-[11px] text-gray-500 font-mono">
                Confidence: {Math.round((confidence || 0.9) * 100)}%
              </p>
            </div>

            {/* Recommended Priority */}
            <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-sm space-y-1">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                AI Recommended Priority
              </span>
              <div>{renderPriorityBadge(suggestedPriority || 'Medium')}</div>
            </div>

            {/* Routed Department */}
            <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-sm space-y-1">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                Suggested Department
              </span>
              <div className="flex items-center gap-1.5 text-gray-900 font-semibold text-xs">
                <Building2 className="w-3.5 h-3.5 text-blue-600 flex-shrink-0" />
                <span>{targetDepartment || 'Operations'}</span>
              </div>
            </div>
          </div>

          {/* Executive Summary */}
          {summary && (
            <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm space-y-1.5">
              <div className="flex items-center gap-2 text-xs font-semibold text-gray-600">
                <FileText className="w-3.5 h-3.5 text-metro-blue" />
                <span>Document Summary</span>
              </div>
              <p className="text-xs text-gray-800 leading-relaxed bg-slate-50 p-2.5 rounded-lg border border-slate-100 max-h-28 overflow-y-auto">
                {summary}
              </p>
            </div>
          )}

          {/* Interactive Human Review Decision Controls */}
          <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm space-y-4">
            <h4 className="font-bold text-gray-900 text-xs uppercase tracking-wider flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-purple-600" />
              <span>Reviewer Verification & Adjustments</span>
            </h4>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Department Confirmation/Override */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-700">
                  Target Department:
                </label>
                <select
                  value={selectedDept}
                  onChange={(e) => setSelectedDept(e.target.value)}
                  disabled={isSubmitting}
                  className="w-full text-xs rounded-lg border-gray-300 shadow-sm focus:border-metro-blue focus:ring-metro-blue p-2 border bg-white"
                >
                  {DEPARTMENTS.map((dept) => (
                    <option key={dept} value={dept}>
                      {dept}
                    </option>
                  ))}
                </select>
              </div>

              {/* Priority Confirmation/Override */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-700">
                  Operational Priority:
                </label>
                <select
                  value={selectedPriority}
                  onChange={(e) => setSelectedPriority(e.target.value)}
                  disabled={isSubmitting}
                  className="w-full text-xs rounded-lg border-gray-300 shadow-sm focus:border-metro-blue focus:ring-metro-blue p-2 border bg-white"
                >
                  {PRIORITIES.map((pri) => (
                    <option key={pri} value={pri}>
                      {pri}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Reviewer Notes */}
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700 flex justify-between">
                <span>Reviewer Audit Notes:</span>
                <span className="text-[11px] text-gray-400">Optional</span>
              </label>
              <textarea
                value={reviewerNotes}
                onChange={(e) => setReviewerNotes(e.target.value)}
                placeholder="e.g. Verified emergency brake incident report with safety division. Inspection protocol confirmed."
                disabled={isSubmitting}
                rows={2}
                className="w-full text-xs rounded-lg border-gray-300 shadow-sm focus:border-metro-blue focus:ring-metro-blue p-2.5 border"
              />
            </div>
          </div>
        </div>

        {/* Footer with Approve and Reject Actions */}
        <div className="px-6 py-4 bg-white border-t border-gray-200 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="text-[11px] text-gray-400 font-mono">
            Document ID: {documentId}
          </div>
          <div className="flex items-center gap-2.5 w-full sm:w-auto">
            <button
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-xs font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => handleDecision('rejected')}
              disabled={isSubmitting}
              className="flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 rounded-lg shadow-sm transition-colors"
            >
              {isSubmitting && submittingDecision === 'rejected' ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <XCircle className="w-3.5 h-3.5" />
              )}
              <span>Reject Document</span>
            </button>
            <button
              onClick={() => handleDecision('approved')}
              disabled={isSubmitting}
              className="flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 rounded-lg shadow-sm transition-colors"
            >
              {isSubmitting && submittingDecision === 'approved' ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <CheckCircle2 className="w-3.5 h-3.5" />
              )}
              <span>Approve Document</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
