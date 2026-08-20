import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * The cost evaluator reports both dollar amounts and raw token counts, so
 * formatting has to follow the metric rather than assume currency.
 */
export function formatCostMetric(key: string, value: number): string {
  if (key.endsWith('_tokens')) return value.toLocaleString()
  if (key === 'cost_per_1k_tokens') return `$${value.toFixed(4)}`
  return `$${value.toFixed(6)}`
}
