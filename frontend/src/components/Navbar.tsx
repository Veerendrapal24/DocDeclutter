import { Link, NavLink } from 'react-router-dom'
import { FileText, Upload, LayoutDashboard } from 'lucide-react'

export default function Navbar() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
      isActive
        ? 'bg-blue-700 text-white'
        : 'text-blue-100 hover:bg-blue-700 hover:text-white'
    }`

  return (
    <nav className="bg-metro-blue shadow-lg">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 text-white font-bold text-lg">
          <FileText className="w-6 h-6 text-metro-gold" />
          DocDeclutter
        </Link>
        <div className="flex gap-2">
          <NavLink to="/" end className={linkClass}>
            <LayoutDashboard className="w-4 h-4" /> Dashboard
          </NavLink>
          <NavLink to="/upload" className={linkClass}>
            <Upload className="w-4 h-4" /> Upload
          </NavLink>
          <NavLink to="/documents" className={linkClass}>
            <FileText className="w-4 h-4" /> Documents
          </NavLink>
        </div>
      </div>
    </nav>
  )
}
