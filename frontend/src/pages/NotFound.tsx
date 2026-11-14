import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="text-center py-24">
      <h1 className="text-5xl font-bold text-metro-blue mb-4">404</h1>
      <p className="text-gray-500 mb-8">Page not found.</p>
      <Link to="/" className="px-6 py-3 bg-metro-blue text-white rounded-xl hover:bg-blue-800 transition-colors">
        Back to Dashboard
      </Link>
    </div>
  )
}
