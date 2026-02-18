'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard, FlaskConical, Database, Gauge, GitCompare, FileText, Settings
} from 'lucide-react'

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Evaluations', href: '/evaluations', icon: FlaskConical },
  { name: 'Datasets', href: '/datasets', icon: Database },
  { name: 'Stress Test', href: '/stress-test', icon: Gauge },
  { name: 'Compare', href: '/compare', icon: GitCompare },
  { name: 'Reports', href: '/reports', icon: FileText },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="w-72 bg-white border-r border-gray-200 flex flex-col flex-shrink-0">
      {/* Logo */}
      <div className="h-20 flex items-center px-6 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl">
            <FlaskConical className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">EvalForge</h1>
            <p className="text-xs text-slate-500">v1.0.0</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-6 space-y-1">
        {navigation.map((item) => {
          const isActive = pathname === item.href || (item.href !== '/' && pathname?.startsWith(item.href))
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-4 py-3 text-sm font-medium rounded-xl transition-all',
                isActive
                  ? 'bg-indigo-50 text-indigo-700'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              )}
            >
              <item.icon className="w-5 h-5" />
              {item.name}
              {isActive && (
                <div className="ml-auto w-1.5 h-1.5 bg-indigo-600 rounded-full" />
              )}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-6 border-t border-gray-200 space-y-3">
        <div className="card p-4 bg-gradient-to-br from-slate-50 to-slate-100">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-slate-600">API Status</span>
            <span className="flex items-center gap-1.5 text-xs text-emerald-600">
              <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
              Online
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-600">Evaluations</span>
            <span className="text-sm font-bold text-slate-900">0</span>
          </div>
        </div>
        <Link
          href="/settings"
          className="flex items-center gap-3 px-4 py-2.5 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-xl transition-colors"
        >
          <Settings className="w-5 h-5" />
          Settings
        </Link>
      </div>
    </aside>
  )
}
