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
  warnings?: string[]
  created_at: string
  completed_at?: string
}

/** GET /evaluations/:id — includes the prompts and the model's replies. */
export interface EvaluationDetail extends Evaluation {
  examples: Array<{
    id?: string
    prompt: string
    expected_output?: string
    context?: string
  }>
  responses: string[]
  config?: Record<string, unknown>
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
    details?: Record<string, number>
  }>
  metadata?: Record<string, unknown> & { pricing_known?: boolean }
}

export interface Provider {
  id: string
  name: string
  models: string[]
}

export interface ComparisonModelSpec {
  provider: string
  model: string
}

/** One model's run inside a comparison, including what it replied. */
export interface ComparisonEvaluation extends Evaluation {
  responses: string[]
}

/** GET /comparisons/:id — polled while status is pending/running. */
export interface ComparisonDetail {
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  evaluators: string[]
  error?: string
  created_at: string
  completed_at?: string
  examples: Array<{
    id?: string
    prompt: string
    expected_output?: string
    context?: string
  }>
  evaluations: ComparisonEvaluation[]
  /** metric name -> id of the winning evaluation, or null if no winner */
  winners: Record<string, string | null>
}

export interface Evaluator {
  id: string
  name: string
  description: string
  metrics: string[]
}
