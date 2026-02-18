'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { evaluationsApi } from '@/lib/api'
import { Evaluation } from '@/types/evaluation'
import { Plus, FlaskConical, Clock, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'

export default function EvaluationsPage() {
  const [evaluations, setEvaluations] = useState<Evaluation[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadEvaluations()
  }, [])

  const loadEvaluations = async () => {
    try {
      const response = await evaluationsApi.list()
      setEvaluations(response.data.evaluations)
    } catch (error) {
      console.error('Failed to load evaluations:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-indigo-600 animate-spin mx-auto mb-4" />
          <p className="text-slate-600">Loading evaluations...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen">
      <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold text-slate-900">Evaluations</h1>
            <p className="text-slate-600 mt-2 text-lg">Manage your LLM evaluation runs</p>
          </div>
          <Link href="/evaluations/new">
            <button className="btn-primary h-12 px-6 flex items-center gap-2 text-base">
              <Plus className="w-5 h-5" />
              New Evaluation
            </button>
          </Link>
        </div>

        {/* Empty State */}
        {evaluations.length === 0 ? (
          <div className="card p-16 text-center bg-gradient-to-br from-slate-50 to-white">
            <div className="max-w-md mx-auto space-y-6">
              <div className="inline-flex p-5 bg-slate-100 rounded-2xl">
                <FlaskConical className="w-16 h-16 text-slate-400" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-slate-900 mb-3">No evaluations yet</h2>
                <p className="text-slate-600 text-lg">
                  Create your first evaluation to start benchmarking LLMs
                </p>
              </div>
              <Link href="/evaluations/new">
                <button className="btn-primary h-12 px-8 text-base">
                  Create Evaluation
                </button>
              </Link>
            </div>
          </div>
        ) : (
          /* Evaluations List */
          <div className="grid gap-4">
            {evaluations.map((evaluation) => (
              <Link key={evaluation.id} href={`/evaluations/${evaluation.id}`}>
                <div className="card card-hover p-6">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-4 flex-1">
                      <div className="p-3 bg-indigo-100 rounded-xl flex-shrink-0">
                        <FlaskConical className="w-6 h-6 text-indigo-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="text-lg font-semibold text-slate-900 mb-1">
                          {evaluation.name}
                        </h3>
                        <div className="flex items-center gap-4 text-sm text-slate-600">
                          <span className="font-medium">{evaluation.provider}</span>
                          <span>•</span>
                          <span className="font-mono text-xs">{evaluation.model}</span>
                          <span>•</span>
                          <span className="flex items-center gap-1.5">
                            <Clock className="w-4 h-4" />
                            {new Date(evaluation.created_at).toLocaleString()}
                          </span>
                        </div>
                        <div className="mt-2 flex items-center gap-2">
                          {evaluation.evaluators.map((evaluator) => (
                            <span
                              key={evaluator}
                              className="px-2 py-1 bg-slate-100 text-slate-700 rounded-md text-xs font-medium"
                            >
                              {evaluator}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                    <StatusBadge status={evaluation.status} />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const config = {
    completed: { icon: CheckCircle2, class: 'badge-success', text: 'Completed' },
    running: { icon: Loader2, class: 'badge-warning', text: 'Running' },
    failed: { icon: AlertCircle, class: 'badge-error', text: 'Failed' },
    pending: { icon: Clock, class: 'badge-default', text: 'Pending' },
  }[status] || { icon: Clock, class: 'badge-default', text: status }

  const Icon = config.icon

  return (
    <span className={`badge ${config.class} flex items-center gap-1.5 px-3 py-1.5`}>
      <Icon className={`w-4 h-4 ${status === 'running' ? 'animate-spin' : ''}`} />
      {config.text}
    </span>
  )
}
