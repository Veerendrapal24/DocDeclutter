import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  UploadCloud, FileText, CheckCircle2, AlertCircle, Loader2, ArrowRight,
  Brain, ShieldAlert, Sparkles
} from 'lucide-react'
import api from '../lib/api'
import {
  Document, DocumentUploadResponse, DocumentAnalysisResponse,
  HumanReviewResponse
} from '../types/document'
import { useToastNotification } from '../context/ToastContext'
import HumanReviewModal from '../components/HumanReviewModal'
import AIAnalysisModal from '../components/AIAnalysisModal'

export default function Upload() {
  const navigate = useNavigate()
  const { showToast } = useToastNotification()

  const [file, setFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadResult, setUploadResult] = useState<DocumentUploadResponse | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // AI Analysis state on upload
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false)
  const [analysisResponse, setAnalysisResponse] = useState<DocumentAnalysisResponse | null>(null)
  const [analysisDoc, setAnalysisDoc] = useState<Document | null>(null)
  const [analysisError, setAnalysisError] = useState<string | null>(null)

  // Modals state
  const [isAnalysisModalOpen, setIsAnalysisModalOpen] = useState<boolean>(false)
  const [isReviewModalOpen, setIsReviewModalOpen] = useState<boolean>(false)

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const selected = e.dataTransfer.files[0]
      validateAndSetFile(selected)
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSetFile(e.target.files[0])
    }
  }

  const validateAndSetFile = (selectedFile: File) => {
    setErrorMessage(null)
    setAnalysisError(null)
    setUploadResult(null)
    setAnalysisResponse(null)
    setAnalysisDoc(null)

    const allowedTypes = [
      'application/pdf',
      'image/png',
      'image/jpeg',
    ]

    if (!allowedTypes.includes(selectedFile.type) && !selectedFile.name.endsWith('.pdf')) {
      const msg = `Unsupported file type. Please upload a PDF, PNG, or JPG/JPEG file.`
      setErrorMessage(msg)
      showToast(msg, 'error')
      return
    }

    setFile(selectedFile)
  }

  const handleSubmit = async () => {
    if (!file) {
      showToast('Please select a document to upload.', 'error')
      return
    }

    setIsUploading(true)
    setErrorMessage(null)
    setAnalysisError(null)
    setUploadProgress(0)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await api.post<DocumentUploadResponse>('/documents/upload', formData, {
        onUploadProgress: (e) => {
          if (e.total) setUploadProgress(Math.round((e.loaded * 100) / e.total))
        },
      })
      const data = response.data

      setUploadProgress(100)
      setUploadResult(data)
      showToast(`Document "${data.filename}" uploaded successfully!`, 'success')
    } catch (err: any) {
      const msg = err.message || 'Failed to upload document. Please try again.'
      setErrorMessage(msg)
      showToast(msg, 'error')
    } finally {
      setIsUploading(false)
    }
  }

  const handleAnalyzeWithAI = async () => {
    if (!uploadResult?.id || isAnalyzing) return

    setIsAnalyzing(true)
    setAnalysisError(null)

    try {
      const res = await api.post<DocumentAnalysisResponse>(`/documents/${uploadResult.id}/analyze`)
      const data = res.data
      setAnalysisResponse(data)

      const docObj: Document = {
        id: data.id,
        filename: data.filename,
        content_type: uploadResult.content_type,
        file_size: uploadResult.file_size,
        status: 'completed',
        department: data.routing?.target_department || 'Operations',
        summary: data.analysis?.summary || null,
        created_at: uploadResult.created_at || new Date().toISOString(),
        ai_status: 'completed',
        ai_category: data.analysis?.category || null,
        ai_confidence: data.analysis?.confidence || 0.9,
        ai_suggested_priority: data.analysis?.suggested_priority || 'Medium',
        priority: data.analysis?.suggested_priority || 'Medium',
        ai_review_status: data.review_status || 'auto_approved',
        ai_review_reasons: data.review_trigger_reasons || [],
        ai_routing: data.routing,
        ai_workflow_history: data.workflow_history,
      }
      setAnalysisDoc(docObj)

      if (data.requires_human_review || data.review_status === 'pending_review') {
        showToast('Analysis completed: Document requires mandatory Human Review.', 'info')
        setIsReviewModalOpen(true)
      } else {
        showToast(`AI Analysis complete: ${data.analysis?.category} (${data.analysis?.suggested_priority} Priority)`, 'success')
        setIsAnalysisModalOpen(true)
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'AI analysis failed. Please try again.'
      setAnalysisError(msg)
      showToast(msg, 'error')
    } finally {
      setIsAnalyzing(false)
    }
  }

  const handleReviewDecisionSubmitted = (decisionRes: HumanReviewResponse) => {
    if (analysisResponse) {
      setAnalysisResponse({
        ...analysisResponse,
        review_status: decisionRes.review_status,
        requires_human_review: false,
      })
    }
    if (analysisDoc) {
      setAnalysisDoc({
        ...analysisDoc,
        department: decisionRes.department || analysisDoc.department,
        priority: decisionRes.priority || analysisDoc.priority,
        ai_suggested_priority: decisionRes.priority || analysisDoc.ai_suggested_priority,
        ai_review_status: decisionRes.review_status,
        ai_reviewer_notes: decisionRes.reviewer_notes,
      })
    }
  }

  const handleReset = () => {
    setFile(null)
    setUploadResult(null)
    setErrorMessage(null)
    setAnalysisError(null)
    setUploadProgress(0)
    setAnalysisResponse(null)
    setAnalysisDoc(null)
    setIsAnalysisModalOpen(false)
    setIsReviewModalOpen(false)
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Upload Metro Document</h1>
        <p className="text-gray-500 text-sm mt-1">
          Upload PDF reports, maintenance logs, inspection sheets, or emergency memos for LangGraph AI processing.
        </p>
      </div>

      {/* Error alert banner */}
      {errorMessage && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3 text-red-800">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-sm font-semibold">Upload Failed</h4>
            <p className="text-sm mt-0.5">{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Success banner with metadata & navigation */}
      {uploadResult ? (
        <div className="bg-white border border-green-200 rounded-xl p-6 shadow-sm space-y-4">
          <div className="flex items-center gap-3 text-green-700">
            <CheckCircle2 className="w-6 h-6 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-lg text-gray-900">Upload Successful</h3>
              <p className="text-sm text-gray-500">{uploadResult.message}</p>
            </div>
          </div>

          <div className="bg-gray-50 rounded-lg p-4 text-xs font-mono space-y-1.5 border">
            <div className="flex justify-between">
              <span className="text-gray-500">Document ID:</span>
              <span className="text-gray-900 font-semibold">{uploadResult.id || 'N/A'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Filename:</span>
              <span className="text-gray-900 font-semibold">{uploadResult.filename}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Content Type:</span>
              <span className="text-gray-900">{uploadResult.content_type}</span>
            </div>
            {uploadResult.file_size !== undefined && (
              <div className="flex justify-between">
                <span className="text-gray-500">File Size:</span>
                <span className="text-gray-900">{(uploadResult.file_size / 1024).toFixed(1)} KB</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-gray-500">Storage Status:</span>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-100 text-emerald-800">
                Ready for Analysis
              </span>
            </div>
          </div>

          {/* Analysis Error Alert */}
          {analysisError && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-3.5 flex items-start gap-2.5 text-red-800 text-xs">
              <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold block">AI Analysis Failed</span>
                <span>{analysisError}</span>
              </div>
            </div>
          )}

          {/* AI Analysis Outcome Card if already analyzed */}
          {analysisResponse && analysisResponse.analysis && (
            <div className="bg-purple-50/60 border border-purple-200 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-purple-600" />
                  <span className="font-bold text-xs uppercase tracking-wider text-purple-900">
                    AI Analysis Result
                  </span>
                </div>
                {analysisResponse.review_status === 'pending_review' ? (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300">
                    <ShieldAlert className="w-3.5 h-3.5 text-amber-600" />
                    Review Pending
                  </span>
                ) : analysisResponse.review_status === 'approved' ? (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    Approved
                  </span>
                ) : analysisResponse.review_status === 'rejected' ? (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800">
                    Rejected
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                    Auto-approved
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                <div className="bg-white p-2 rounded-lg border border-purple-100">
                  <span className="text-[10px] text-gray-500 uppercase block">Category</span>
                  <span className="font-bold text-gray-900 truncate block">
                    {analysisResponse.analysis.category}
                  </span>
                </div>
                <div className="bg-white p-2 rounded-lg border border-purple-100">
                  <span className="text-[10px] text-gray-500 uppercase block">Priority</span>
                  <span className="font-bold text-gray-900">
                    {analysisResponse.analysis.suggested_priority}
                  </span>
                </div>
                <div className="bg-white p-2 rounded-lg border border-purple-100 col-span-2 sm:col-span-1">
                  <span className="text-[10px] text-gray-500 uppercase block">Department</span>
                  <span className="font-bold text-blue-700 truncate block">
                    {analysisResponse.routing?.target_department || 'Operations'}
                  </span>
                </div>
              </div>

              {/* Review button if pending review */}
              {analysisResponse.review_status === 'pending_review' && (
                <div className="pt-1">
                  <button
                    onClick={() => setIsReviewModalOpen(true)}
                    className="w-full inline-flex items-center justify-center gap-2 py-2 px-3 text-xs font-bold text-white bg-amber-600 hover:bg-amber-700 rounded-lg shadow-sm transition-colors"
                  >
                    <ShieldAlert className="w-4 h-4" />
                    <span>Complete Required Human Review</span>
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row gap-3 pt-2">
            {uploadResult.id && (
              <button
                onClick={analysisResponse ? () => setIsAnalysisModalOpen(true) : handleAnalyzeWithAI}
                disabled={isAnalyzing}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 px-4 bg-purple-600 text-white rounded-lg font-medium hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
              >
                {isAnalyzing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Analyzing with LangGraph...</span>
                  </>
                ) : analysisResponse ? (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>View AI Analysis</span>
                  </>
                ) : (
                  <>
                    <Brain className="w-4 h-4" />
                    <span>Analyze with AI</span>
                  </>
                )}
              </button>
            )}

            <button
              onClick={() => navigate('/documents')}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 px-4 bg-metro-blue text-white rounded-lg font-medium hover:bg-blue-800 transition-colors shadow-sm"
            >
              View in Documents
              <ArrowRight className="w-4 h-4" />
            </button>

            <button
              onClick={handleReset}
              className="py-2.5 px-4 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
            >
              Upload Another
            </button>
          </div>
        </div>
      ) : (
        /* Upload Drag-and-Drop Area */
        <div className="space-y-4">
          <div
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            className="border-2 border-dashed border-blue-300 rounded-xl p-10 text-center hover:border-blue-500 hover:bg-blue-50/30 transition-colors cursor-pointer bg-white"
            onClick={() => document.getElementById('file-input')?.click()}
          >
            <UploadCloud className="w-12 h-12 mx-auto text-blue-500 mb-3" />
            <p className="text-gray-700 font-medium">
              Drag & drop your PDF file here, or{' '}
              <span className="text-blue-600 underline font-semibold">browse files</span>
            </p>
            <p className="text-xs text-gray-400 mt-2">
              Supports PDF, PNG, JPG/JPEG up to 10 MB
            </p>
            <input
              id="file-input"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,application/pdf"
              className="hidden"
              onChange={handleFileChange}
            />
          </div>

          {/* Selected file preview */}
          {file && (
            <div className="bg-white border rounded-xl p-4 flex items-center gap-3 shadow-sm">
              <div className="p-2.5 bg-blue-50 text-blue-600 rounded-lg">
                <FileText className="w-6 h-6" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-900 truncate">{file.name}</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {(file.size / 1024).toFixed(1)} KB • {file.type || 'application/pdf'}
                </p>
              </div>
              <button
                type="button"
                onClick={handleReset}
                disabled={isUploading}
                className="text-xs text-gray-500 hover:text-red-600 px-2 py-1 rounded hover:bg-gray-100"
              >
                Change
              </button>
            </div>
          )}

          {/* Upload progress bar */}
          {isUploading && uploadProgress > 0 && (
            <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
              <div
                className="bg-metro-blue h-2 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          )}

          {/* Upload Button */}
          <button
            onClick={handleSubmit}
            disabled={!file || isUploading}
            className="w-full py-3 bg-metro-blue text-white rounded-xl font-semibold hover:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm flex items-center justify-center gap-2"
          >
            {isUploading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Uploading Document to FastAPI...</span>
              </>
            ) : (
              <span>Upload & Process Document</span>
            )}
          </button>
        </div>
      )}

      {/* Human Review Modal on Upload Screen */}
      {uploadResult && (
        <HumanReviewModal
          isOpen={isReviewModalOpen}
          documentId={uploadResult.id || ''}
          filename={uploadResult.filename}
          category={analysisResponse?.analysis?.category || 'Incident Report'}
          confidence={analysisResponse?.analysis?.confidence || 0.9}
          suggestedPriority={analysisResponse?.analysis?.suggested_priority || 'High'}
          targetDepartment={analysisResponse?.routing?.target_department || 'Operations'}
          reviewReasons={analysisResponse?.review_trigger_reasons || []}
          summary={analysisResponse?.analysis?.summary || ''}
          onClose={() => setIsReviewModalOpen(false)}
          onDecisionSubmitted={handleReviewDecisionSubmitted}
        />
      )}

      {/* AI Analysis Modal on Upload Screen */}
      {analysisDoc && analysisResponse?.analysis && (
        <AIAnalysisModal
          isOpen={isAnalysisModalOpen}
          doc={analysisDoc}
          analysis={analysisResponse.analysis}
          reviewStatus={analysisResponse.review_status}
          reviewReasons={analysisResponse.review_trigger_reasons}
          onClose={() => setIsAnalysisModalOpen(false)}
          onOpenReview={() => {
            setIsAnalysisModalOpen(false)
            setIsReviewModalOpen(true)
          }}
        />
      )}
    </div>
  )
}
