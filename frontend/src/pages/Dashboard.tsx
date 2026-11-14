import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  FileCheck, Clock, AlertCircle, RefreshCw, Upload,
  FileText, ArrowRight, Brain, Sparkles, ShieldCheck, AlertTriangle,
  Tag, CheckCircle2
} from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import api from '../lib/api'
import { Document, DocumentListResponse, StatsResponse } from '../types/document'
import { useToastNotification } from '../context/ToastContext'

interface CategoryChartItem {
  category: string
  docs: number
}

interface PriorityCountItem {
  priority: string
  count: number
  color: string
  bg: string
  border: string
}

export default function Dashboard() {
  const { showToast } = useToastNotification()

  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Core metrics
  const [totalDocs, setTotalDocs] = useState<number>(0)
  const [ocrCompleted, setOcrCompleted] = useState<number>(0)
  const [aiAnalyzed, setAiAnalyzed] = useState<number>(0)
  const [pendingAi, setPendingAi] = useState<number>(0)

  // Chart data
  const [categoryChart, setCategoryChart] = useState<CategoryChartItem[]>([])
  const [priorityDistribution, setPriorityDistribution] = useState<PriorityCountItem[]>([])
  const [recentDocs, setRecentDocs] = useState<Document[]>([])

  const fetchDashboardData = useCallback(async (isManual = false) => {
    setIsLoading(true)
    setErrorMessage(null)

    try {
      // 1. Fetch document list
      const docResponse = await api.get<DocumentListResponse>('/documents')
      const docs: Document[] = docResponse.data.documents || []
      const total = docResponse.data.total ?? docs.length
      setTotalDocs(total)

      // 2. Fetch stats endpoint
      let statsData: StatsResponse | null = null
      try {
        const statsRes = await api.get<StatsResponse>('/documents/stats')
        statsData = statsRes.data
      } catch {
        // Fallback calculation from docs
      }

      // Calculate OCR completed
      const ocrCount = statsData?.ocr_completed ?? docs.filter(
        (d) => d.extraction_status === 'completed' || !!d.extracted_text
      ).length
      setOcrCompleted(ocrCount)

      // Calculate AI Analyzed
      const aiCount = statsData?.ai_analyzed ?? docs.filter(
        (d) => d.ai_status === 'completed' && !!d.ai_category
      ).length
      setAiAnalyzed(aiCount)

      // Calculate Pending AI
      const pendingCount = statsData?.pending_ai ?? docs.filter(
        (d) => d.ai_status !== 'completed' || !d.ai_category
      ).length
      setPendingAi(pendingCount)

      // 3. Category distribution
      const catCounts: Record<string, number> = {
        'Maintenance': 0,
        'Safety': 0,
        'Incident': 0,
        'Invoice': 0,
        'Complaint': 0,
        'Employee': 0,
        'Other': 0,
      }

      docs.forEach((d) => {
        const cat = d.ai_category
        if (cat === 'Maintenance Report') catCounts['Maintenance']++
        else if (cat === 'Safety Inspection Report') catCounts['Safety']++
        else if (cat === 'Incident Report') catCounts['Incident']++
        else if (cat === 'Vendor Invoice') catCounts['Invoice']++
        else if (cat === 'Passenger Complaint') catCounts['Complaint']++
        else if (cat === 'Employee Application') catCounts['Employee']++
        else if (cat) catCounts['Other']++
      })

      const computedCatChart: CategoryChartItem[] = Object.keys(catCounts).map((key) => ({
        category: key,
        docs: catCounts[key],
      }))
      setCategoryChart(computedCatChart)

      // 4. Priority distribution
      const priCounts: Record<string, number> = {
        Critical: 0,
        High: 0,
        Medium: 0,
        Low: 0,
      }
      docs.forEach((d) => {
        const p = d.ai_suggested_priority
        if (p && priCounts[p] !== undefined) {
          priCounts[p]++
        }
      })

      setPriorityDistribution([
        { priority: 'Critical', count: priCounts.Critical, color: 'text-red-700', bg: 'bg-red-50', border: 'border-red-200' },
        { priority: 'High', count: priCounts.High, color: 'text-orange-700', bg: 'bg-orange-50', border: 'border-orange-200' },
        { priority: 'Medium', count: priCounts.Medium, color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200' },
        { priority: 'Low', count: priCounts.Low, color: 'text-blue-700', bg: 'bg-blue-50', border: 'border-blue-200' },
      ])

      // 5. Recent documents
      setRecentDocs(docs.slice(0, 5))

      if (isManual) {
        showToast('Dashboard data refreshed.', 'info')
      }
    } catch (err: any) {
      const msg = err.message || 'Failed to fetch dashboard statistics from backend.'
      setErrorMessage(msg)
      showToast(msg, 'error')
    } finally {
      setIsLoading(false)
    }
  }, [showToast])

  useEffect(() => {
    fetchDashboardData()
  }, [fetchDashboardData])

  const statsCards = [
    {
      label: 'Total Documents',
      value: totalDocs,
      icon: FileCheck,
      color: 'bg-blue-100 text-blue-700',
      subtitle: 'Stored in local repository',
    },
    {
      label: 'OCR Text Extracted',
      value: ocrCompleted,
      icon: CheckCircle2,
      color: 'bg-emerald-100 text-emerald-700',
      subtitle: 'Processed via PyMuPDF / OCR',
    },
    {
      label: 'Gemini AI Analyzed',
      value: aiAnalyzed,
      icon: Brain,
      color: 'bg-purple-100 text-purple-700',
      subtitle: 'Classified & structured',
    },
    {
      label: 'Pending AI Analysis',
      value: pendingAi,
      icon: Clock,
      color: 'bg-amber-100 text-amber-700',
      subtitle: 'Ready for intelligence scan',
    },
  ]

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Metro Operations Intelligence</h1>
          <p className="text-gray-500 text-sm mt-1">
            Real-time document automation, Gemini AI classification & operational priority routing.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchDashboardData(true)}
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
            Upload Document
          </Link>
        </div>
      </div>

      {/* Error alert */}
      {errorMessage && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3 text-red-800">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-sm font-semibold">Could not load live metrics</h4>
            <p className="text-sm mt-0.5">{errorMessage}</p>
          </div>
          <button
            onClick={() => fetchDashboardData()}
            className="px-3 py-1 bg-red-100 hover:bg-red-200 text-red-800 rounded text-xs font-medium transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Primary KPI Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statsCards.map((s) => (
          <div
            key={s.label}
            className="bg-white rounded-xl shadow-sm border p-5 flex items-center gap-4 transition-transform hover:-translate-y-0.5"
          >
            <div className={`p-3 rounded-xl ${s.color} flex-shrink-0`}>
              <s.icon className="w-6 h-6" />
            </div>
            <div className="min-w-0">
              <p className="text-2xl font-bold text-gray-900">
                {isLoading ? '...' : s.value}
              </p>
              <p className="text-xs text-gray-600 font-semibold">{s.label}</p>
              <p className="text-[11px] text-gray-400 truncate">{s.subtitle}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Priority Distribution Cards */}
      <div className="bg-white rounded-xl shadow-sm border p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-indigo-600" />
            <h2 className="font-semibold text-gray-800 text-sm">Operational Priority Distribution</h2>
          </div>
          <span className="text-xs text-gray-400">Gemini Recommended</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {priorityDistribution.map((item) => (
            <div
              key={item.priority}
              className={`p-3.5 rounded-xl border ${item.border} ${item.bg} flex items-center justify-between`}
            >
              <div>
                <span className="text-xs font-medium text-gray-500 uppercase tracking-wider block">
                  {item.priority}
                </span>
                <span className={`text-2xl font-extrabold ${item.color} mt-0.5 block`}>
                  {item.count}
                </span>
              </div>
              {item.priority === 'Critical' ? (
                <AlertTriangle className="w-5 h-5 text-red-500" />
              ) : (
                <Tag className="w-5 h-5 text-gray-400" />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Category Chart & Recent Uploads Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Category distribution chart */}
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="font-semibold text-gray-800">Documents by Category</h2>
              <p className="text-xs text-gray-400">Classified using Google Gemini AI</p>
            </div>
            <span className="text-xs font-medium text-purple-700 bg-purple-50 px-2.5 py-1 rounded-md border border-purple-200 flex items-center gap-1">
              <Sparkles className="w-3 h-3" /> Live AI Data
            </span>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categoryChart} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <XAxis dataKey="category" tick={{ fontSize: 11, fill: '#6B7280' }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#6B7280' }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#ffffff',
                    borderRadius: '8px',
                    borderColor: '#E5E7EB',
                    fontSize: '12px',
                  }}
                />
                <Bar dataKey="docs" radius={[4, 4, 0, 0]}>
                  {categoryChart.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={
                        entry.category === 'Maintenance' ? '#003580' :
                        entry.category === 'Safety' ? '#059669' :
                        entry.category === 'Incident' ? '#DC2626' :
                        entry.category === 'Invoice' ? '#D97706' :
                        entry.category === 'Complaint' ? '#7C3AED' :
                        entry.category === 'Employee' ? '#2563EB' : '#6B7280'
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recent uploads sidebar */}
        <div className="bg-white rounded-xl shadow-sm border p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-800">Recent Documents</h2>
              <Link to="/documents" className="text-xs text-blue-600 hover:underline flex items-center gap-1 font-medium">
                View all <ArrowRight className="w-3 h-3" />
              </Link>
            </div>

            {isLoading && recentDocs.length === 0 ? (
              <div className="py-8 text-center text-sm text-gray-400">Loading...</div>
            ) : recentDocs.length === 0 ? (
              <div className="py-8 text-center text-gray-400 text-sm">
                No documents uploaded yet.
              </div>
            ) : (
              <div className="space-y-3">
                {recentDocs.map((doc) => (
                  <div
                    key={doc.id}
                    className="p-3 bg-gray-50 rounded-lg border border-gray-100 flex items-center justify-between gap-2"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <FileText className="w-4 h-4 text-metro-blue flex-shrink-0" />
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-gray-900 truncate">{doc.filename}</p>
                        <p className="text-[10px] text-gray-500">
                          {doc.ai_category || (doc.extraction_status === 'completed' ? 'OCR Ready' : 'Pending')}
                        </p>
                      </div>
                    </div>
                    {doc.ai_suggested_priority ? (
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full flex-shrink-0 ${
                        doc.ai_suggested_priority === 'Critical' ? 'bg-red-100 text-red-800' :
                        doc.ai_suggested_priority === 'High' ? 'bg-orange-100 text-orange-800' :
                        doc.ai_suggested_priority === 'Medium' ? 'bg-amber-100 text-amber-800' :
                        'bg-blue-100 text-blue-800'
                      }`}>
                        {doc.ai_suggested_priority}
                      </span>
                    ) : (
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-800 flex-shrink-0">
                        {doc.status}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="pt-4 border-t mt-4">
            <Link
              to="/upload"
              className="w-full py-2.5 px-3 bg-blue-50 text-metro-blue hover:bg-blue-100 rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-2"
            >
              <Upload className="w-3.5 h-3.5" />
              Upload New Document
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
