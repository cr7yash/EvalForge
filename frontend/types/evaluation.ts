export interface Evaluation {
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  provider: string
  model: string
  progress: number
  results?: EvaluationResults
  evaluators: string[]
  error?: string
  created_at: string
  completed_at?: string
}

export interface EvaluationResults {
  accuracy?: EvaluatorResult
  performance?: EvaluatorResult
  cost?: EvaluatorResult
  [key: string]: EvaluatorResult | undefined
}

export interface EvaluatorResult {
  evaluator_name: string
  aggregated_metrics: Record<string, number>
  results: Array<{
    example_id: string
    metrics: Record<string, number>
  }>
}

export interface Provider {
  id: string
  name: string
  models: string[]
}

export interface Evaluator {
  id: string
  name: string
  description: string
  metrics: string[]
}
