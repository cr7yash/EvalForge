'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { comparisonsApi } from '@/lib/api'
import { ComparisonDetail } from '@/types/evaluation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { formatCostMetric, cn } from '@/lib/utils'
import { ArrowLeft, Crown } from 'lucide-react'

const POLL_INTERVAL_MS = 1500

const EVALUATOR_TITLES: Record<string, string> = {
  accuracy: 'Accuracy',
  performance: 'Performance',
  cost: 'Cost & Tokens',
}

function statusVariant(status: string): 'default' | 'success' | 'warning' | 'error' {
  switch (status) {
    case 'completed': return 'success'
    case 'running': return 'warning'
    case 'failed': return 'error'
    default: return 'default'
  }
}

function formatMetric(evaluatorName: string, key: string, value: number): string {
  if (evaluatorName === 'accuracy') return `${(value * 100).toFixed(1)}%`
  if (evaluatorName === 'performance') {
    return key.includes('latency') ? `${value.toFixed(0)}ms` : value.toFixed(2)
  }
  if (evaluatorName === 'cost') return formatCostMetric(key, value)
  return String(value)
}

function metricLabel(evaluatorName: string, key: string): string {
  const stripped = evaluatorName === 'cost' ? key.replace(/_usd$/, '') : key
  return stripped.replace(/_/g, ' ')
}

export default function ComparisonDetailPage() {
  const params = useParams()
  const [comparison, setComparison] = useState<ComparisonDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!params.id) return
    const id = params.id as string
    let cancelled = false
    let interval: ReturnType<typeof setInterval> | null = null

    const load = () =>
      comparisonsApi
        .get(id)
        .then((res) => {
          if (cancelled) return
          setComparison(res.data)
          if (['completed', 'failed'].includes(res.data.status) && interval) {
            clearInterval(interval)
            interval = null
          }
        })
        .catch((error) => console.error('Failed to load comparison:', error))
        .finally(() => {
          if (!cancelled) setLoading(false)
        })

    load()
    interval = setInterval(load, POLL_INTERVAL_MS)

    return () => {
      cancelled = true
      if (interval) clearInterval(interval)
    }
  }, [params.id])

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto">
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading comparison...</p>
        </div>
      </div>
    )
  }

  if (!comparison) {
    return (
      <div className="max-w-7xl mx-auto text-center py-12">
        <h2 className="text-2xl font-bold text-gray-900">Comparison not found</h2>
        <Link href="/compare" className="mt-4 inline-block">
          <Button>Back to Compare</Button>
        </Link>
      </div>
    )
  }

  const isRunning = ['pending', 'running'].includes(comparison.status)
  const evaluations = comparison.evaluations

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div>
        <Link href="/compare" className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-4">
          <ArrowLeft className="h-4 w-4 mr-2" />
          New Comparison
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{comparison.name}</h1>
            <p className="text-gray-600 mt-1">{evaluations.length} models</p>
          </div>
          <Badge variant={statusVariant(comparison.status)}>{comparison.status}</Badge>
        </div>
      </div>

      {comparison.error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-6">
            <p className="text-red-800 font-medium">Error: {comparison.error}</p>
          </CardContent>
        </Card>
      )}

      {/* Per-model progress while the comparison is still running */}
      {isRunning && (
        <Card>
          <CardHeader>
            <CardTitle>Running</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {evaluations.map((ev) => (
              <div key={ev.id}>
                <div className="flex items-center justify-between mb-1 text-sm">
                  <span className="font-medium text-gray-900">
                    {ev.provider} / {ev.model}
                  </span>
                  <Badge variant={statusVariant(ev.status)}>{ev.status}</Badge>
                </div>
                <Progress value={ev.progress * 100} />
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Failed models called out explicitly -- their columns go blank below */}
      {evaluations.some((ev) => ev.status === 'failed') && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-6 space-y-2">
            <p className="text-red-800 font-medium">Some models failed to complete:</p>
            {evaluations
              .filter((ev) => ev.status === 'failed')
              .map((ev) => (
                <p key={ev.id} className="text-sm text-red-700">
                  <span className="font-medium">{ev.provider} / {ev.model}</span>: {ev.error}
                </p>
              ))}
          </CardContent>
        </Card>
      )}

      {/* Metrics table -- only meaningful once at least one model has results */}
      {evaluations.some((ev) => ev.results) && (
        <div className="space-y-6">
          {comparison.evaluators.map((evaluatorName) => {
            // Metric key order comes from the first model that has this
            // evaluator's results; every model runs the same evaluators, so
            // this is the same set for all of them.
            const template = evaluations.find((ev) => ev.results?.[evaluatorName])
            const metricKeys = template
              ? Object.keys(template.results![evaluatorName]!.aggregated_metrics)
              : []
            if (metricKeys.length === 0) return null

            return (
              <Card key={evaluatorName}>
                <CardHeader>
                  <CardTitle>{EVALUATOR_TITLES[evaluatorName] ?? evaluatorName}</CardTitle>
                </CardHeader>
                <CardContent className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="text-left font-medium text-gray-500 py-2 pr-4">
                          Metric
                        </th>
                        {evaluations.map((ev) => (
                          <th key={ev.id} className="text-right font-medium text-gray-900 py-2 px-4 min-w-[140px]">
                            <Link
                              href={`/evaluations/${ev.id}`}
                              className="hover:text-indigo-600 hover:underline"
                            >
                              {ev.provider} / {ev.model}
                            </Link>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {metricKeys.map((metric) => (
                        <tr key={metric} className="border-b border-gray-100 last:border-0">
                          <td className="py-2 pr-4 text-gray-600 capitalize">
                            {metricLabel(evaluatorName, metric)}
                          </td>
                          {evaluations.map((ev) => {
                            const evaluatorResult = ev.results?.[evaluatorName]
                            const isWinner = comparison.winners[metric] === ev.id
                            const pricingKnown = evaluatorResult?.metadata?.pricing_known

                            let cell: React.ReactNode = <span className="text-gray-400">—</span>
                            if (ev.status === 'failed') {
                              cell = <span className="text-red-400">failed</span>
                            } else if (evaluatorResult) {
                              const value = evaluatorResult.aggregated_metrics[metric]
                              const isCostMetric = evaluatorName === 'cost' && metric !== 'input_tokens'
                                && metric !== 'output_tokens' && metric !== 'total_tokens'
                              if (isCostMetric && pricingKnown === false) {
                                cell = <span className="text-gray-400" title="No list price on record">—</span>
                              } else if (typeof value === 'number') {
                                cell = formatMetric(evaluatorName, metric, value)
                              }
                            } else if (ev.status !== 'completed') {
                              cell = <span className="text-gray-400">…</span>
                            }

                            return (
                              <td
                                key={ev.id}
                                className={cn(
                                  'py-2 px-4 text-right',
                                  isWinner && 'bg-green-50 font-semibold text-green-800 rounded'
                                )}
                              >
                                <span className="inline-flex items-center gap-1 justify-end">
                                  {isWinner && <Crown className="h-3.5 w-3.5 text-green-600" />}
                                  {cell}
                                </span>
                              </td>
                            )
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {/* Without this, an all-unpriced comparison is just a wall
                      of dashes with no indication of why. */}
                  {evaluatorName === 'cost' && (() => {
                    const unpriced = evaluations.filter(
                      (ev) => ev.results?.cost?.metadata?.pricing_known === false
                    )
                    if (unpriced.length === 0) return null
                    const allUnpriced = unpriced.length === evaluations.length
                    return (
                      <p className="text-xs text-amber-700 mt-3 pt-3 border-t">
                        {allUnpriced
                          ? 'No list price is on record for any of these models, so every cost figure shows as “—”. Token counts above are still accurate.'
                          : `No list price on record for ${unpriced
                              .map((ev) => ev.model)
                              .join(', ')} — their cost cells show “—” and they are excluded from cost winners.`}
                      </p>
                    )
                  })()}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {/* Each prompt with every model's reply, so scores can be checked
          against what the models actually said. */}
      <Card>
        <CardHeader>
          <CardTitle>Prompts &amp; Responses</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {comparison.examples.map((example, i) => (
            <div key={example.id ?? i} className="space-y-3">
              <div className="border rounded-lg p-3 bg-gray-50">
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">
                  Prompt {i + 1}
                </p>
                <p className="text-sm text-gray-900 whitespace-pre-wrap">
                  {example.prompt}
                </p>
                {example.expected_output && (
                  <>
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mt-3 mb-1">
                      Expected
                    </p>
                    <p className="text-sm text-gray-700 whitespace-pre-wrap">
                      {example.expected_output}
                    </p>
                  </>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {evaluations.map((ev) => {
                  const response = ev.responses?.[i]
                  return (
                    <div key={ev.id} className="border rounded-lg p-3">
                      <div className="flex items-center justify-between mb-2 gap-2">
                        <Link
                          href={`/evaluations/${ev.id}`}
                          className="text-xs font-semibold text-gray-900 hover:text-indigo-600 hover:underline truncate"
                        >
                          {ev.provider} / {ev.model}
                        </Link>
                        {ev.status !== 'completed' && (
                          <Badge variant={statusVariant(ev.status)}>{ev.status}</Badge>
                        )}
                      </div>
                      {ev.status === 'failed' ? (
                        <p className="text-sm italic text-red-600">
                          Model failed — no response
                        </p>
                      ) : response ? (
                        <p className="text-sm text-gray-900 whitespace-pre-wrap">
                          {response}
                        </p>
                      ) : ev.status === 'completed' ? (
                        <p className="text-sm italic text-amber-700">
                          No text returned
                        </p>
                      ) : (
                        <p className="text-sm italic text-gray-400">Waiting…</p>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
