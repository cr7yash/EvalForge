'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { evaluationsApi } from '@/lib/api'
import { EvaluationDetail } from '@/types/evaluation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { ArrowLeft } from 'lucide-react'
import Link from 'next/link'

export default function EvaluationDetailPage() {
  const params = useParams()
  const [evaluation, setEvaluation] = useState<EvaluationDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (params.id) {
      loadEvaluation(params.id as string)
    }
  }, [params.id])

  const loadEvaluation = async (id: string) => {
    try {
      const response = await evaluationsApi.get(id)
      setEvaluation(response.data)
    } catch (error) {
      console.error('Failed to load evaluation:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto">
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading evaluation...</p>
        </div>
      </div>
    )
  }

  if (!evaluation) {
    return (
      <div className="max-w-7xl mx-auto text-center py-12">
        <h2 className="text-2xl font-bold text-gray-900">Evaluation not found</h2>
        <Link href="/evaluations" className="mt-4 inline-block">
          <Button>Back to Evaluations</Button>
        </Link>
      </div>
    )
  }

  const costPerExample = new Map(
    (evaluation.results?.cost?.results ?? []).map((r) => [r.example_id, r.metrics])
  )

  const getStatusVariant = (status: string): "default" | "success" | "warning" | "error" => {
    switch (status) {
      case 'completed': return 'success'
      case 'running': return 'warning'
      case 'failed': return 'error'
      default: return 'default'
    }
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <Link href="/evaluations" className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-4">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Evaluations
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{evaluation.name}</h1>
            <p className="text-gray-600 mt-1">
              {evaluation.provider} / {evaluation.model}
            </p>
          </div>
          <Badge variant={getStatusVariant(evaluation.status)}>
            {evaluation.status}
          </Badge>
        </div>
      </div>

      {/* Error */}
      {evaluation.error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-6">
            <p className="text-red-800 font-medium">Error: {evaluation.error}</p>
          </CardContent>
        </Card>
      )}

      {/* Generation warnings — these explain scores that would otherwise
          look like plain model failures (empty or truncated responses). */}
      {evaluation.warnings && evaluation.warnings.length > 0 && (
        <Alert variant="warning">
          <AlertTitle>
            {evaluation.warnings.length} example
            {evaluation.warnings.length === 1 ? '' : 's'} had generation issues
          </AlertTitle>
          <AlertDescription>
            <p className="mb-2">
              Scores for these examples reflect an incomplete response, not
              necessarily a wrong answer.
            </p>
            <ul className="list-disc list-inside space-y-1">
              {evaluation.warnings.map((warning, i) => (
                <li key={i}>{warning}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {/* Results */}
      {evaluation.results && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Accuracy */}
          {evaluation.results.accuracy && (
            <Card>
              <CardHeader>
                <CardTitle>Accuracy Metrics</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {Object.entries(evaluation.results.accuracy.aggregated_metrics).map(([key, value]) => (
                  <div key={key} className="flex justify-between">
                    <span className="text-sm text-gray-600 capitalize">
                      {key.replace(/_/g, ' ')}
                    </span>
                    <span className="text-sm font-semibold text-gray-900">
                      {(value * 100).toFixed(1)}%
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Performance */}
          {evaluation.results.performance && (
            <Card>
              <CardHeader>
                <CardTitle>Performance Metrics</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {Object.entries(evaluation.results.performance.aggregated_metrics).map(([key, value]) => (
                  <div key={key} className="flex justify-between">
                    <span className="text-sm text-gray-600 capitalize">
                      {key.replace(/_/g, ' ')}
                    </span>
                    <span className="text-sm font-semibold text-gray-900">
                      {key.includes('latency') ? `${value.toFixed(0)}ms` : value.toFixed(2)}
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Cost */}
          {evaluation.results.cost && (
            <Card>
              <CardHeader>
                <CardTitle>Cost &amp; Tokens</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {Object.entries(evaluation.results.cost.aggregated_metrics).map(([key, value]) => (
                  <div key={key} className="flex justify-between">
                    <span className="text-sm text-gray-600 capitalize">
                      {key.replace(/_usd$/, '').replace(/_/g, ' ')}
                    </span>
                    <span className="text-sm font-semibold text-gray-900">
                      {formatCostMetric(key, value)}
                    </span>
                  </div>
                ))}
                {evaluation.results.cost.metadata?.pricing_known === false && (
                  <p className="text-xs text-amber-700 pt-2 border-t">
                    No list price on record for this model — token counts are
                    accurate, dollar figures are not.
                  </p>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Metadata */}
      <Card>
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-600">Created:</span>
              <span className="ml-2 font-medium text-gray-900">
                {new Date(evaluation.created_at).toLocaleString()}
              </span>
            </div>
            {evaluation.completed_at && (
              <div>
                <span className="text-gray-600">Completed:</span>
                <span className="ml-2 font-medium text-gray-900">
                  {new Date(evaluation.completed_at).toLocaleString()}
                </span>
              </div>
            )}
            <div>
              <span className="text-gray-600">Evaluators:</span>
              <span className="ml-2 font-medium text-gray-900">
                {evaluation.evaluators.join(', ')}
              </span>
            </div>
            <div>
              <span className="text-gray-600">Progress:</span>
              <span className="ml-2 font-medium text-gray-900">
                {(evaluation.progress * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Prompts and what the model actually replied */}
      {evaluation.examples?.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Prompts &amp; Responses</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {evaluation.examples.map((example, i) => {
              const response = evaluation.responses?.[i]
              return (
                <div key={example.id ?? i} className="border rounded-lg p-4 space-y-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant="default">#{example.id ?? i + 1}</Badge>
                    {(() => {
                      const m = costPerExample.get(String(example.id ?? i))
                      if (!m) return null
                      return (
                        <span className="text-xs text-gray-500">
                          {m.input_tokens} in · {m.output_tokens} out ·{' '}
                          {m.total_tokens} tokens
                          {m.cost_usd > 0 && ` · $${m.cost_usd.toFixed(6)}`}
                        </span>
                      )
                    })()}
                  </div>

                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">
                      Prompt
                    </p>
                    <p className="text-sm text-gray-900 whitespace-pre-wrap">
                      {example.prompt}
                    </p>
                  </div>

                  {example.expected_output && (
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">
                        Expected
                      </p>
                      <p className="text-sm text-gray-700 whitespace-pre-wrap">
                        {example.expected_output}
                      </p>
                    </div>
                  )}

                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">
                      Response
                    </p>
                    {response ? (
                      <p className="text-sm text-gray-900 whitespace-pre-wrap">
                        {response}
                      </p>
                    ) : (
                      <p className="text-sm italic text-amber-700">
                        No text returned
                      </p>
                    )}
                  </div>
                </div>
              )
            })}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

/**
 * The cost evaluator reports both dollar amounts and raw token counts, so
 * formatting has to follow the metric rather than assume currency.
 */
function formatCostMetric(key: string, value: number): string {
  if (key.endsWith('_tokens')) return value.toLocaleString()
  if (key === 'cost_per_1k_tokens') return `$${value.toFixed(4)}`
  return `$${value.toFixed(6)}`
}
