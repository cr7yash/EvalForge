'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { evaluationsApi, providersApi } from '@/lib/api'
import { Provider, Evaluator } from '@/types/evaluation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Plus, Trash2, ArrowLeft } from 'lucide-react'
import Link from 'next/link'

export default function NewEvaluationPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [providers, setProviders] = useState<Provider[]>([])
  const [evaluators, setEvaluators] = useState<Evaluator[]>([])

  const [form, setForm] = useState({
    name: '',
    provider: '',
    model: '',
    evaluators: ['accuracy', 'performance', 'cost'],
    examples: [{
      prompt: '',
      expected_output: ''
    }]
  })

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [providersRes, evaluatorsRes] = await Promise.all([
        providersApi.list(),
        providersApi.listEvaluators()
      ])
      setProviders(providersRes.data)
      setEvaluators(evaluatorsRes.data)
    } catch (error) {
      console.error('Failed to load data:', error)
    }
  }

  const selectedProvider = providers.find(p => p.id === form.provider)

  const addExample = () => {
    setForm(prev => ({
      ...prev,
      examples: [...prev.examples, { prompt: '', expected_output: '' }]
    }))
  }

  const removeExample = (index: number) => {
    setForm(prev => ({
      ...prev,
      examples: prev.examples.filter((_, i) => i !== index)
    }))
  }

  const updateExample = (index: number, field: string, value: string) => {
    setForm(prev => ({
      ...prev,
      examples: prev.examples.map((ex, i) =>
        i === index ? { ...ex, [field]: value } : ex
      )
    }))
  }

  const toggleEvaluator = (id: string) => {
    setForm(prev => ({
      ...prev,
      evaluators: prev.evaluators.includes(id)
        ? prev.evaluators.filter(e => e !== id)
        : [...prev.evaluators, id]
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      const response = await evaluationsApi.create({
        name: form.name,
        provider: form.provider,
        model: form.model,
        evaluators: form.evaluators,
        examples: form.examples.map((ex, i) => ({
          id: `example-${i}`,
          prompt: ex.prompt,
          expected_output: ex.expected_output
        }))
      })

      router.push(`/evaluations/${response.data.id}`)
    } catch (error: any) {
      console.error('Failed to create evaluation:', error)
      alert(`Failed to create evaluation: ${error.response?.data?.detail || error.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <Link href="/evaluations" className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-4">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Evaluations
        </Link>
        <h1 className="text-3xl font-bold text-gray-900">New Evaluation</h1>
        <p className="text-gray-600 mt-1">Configure your LLM evaluation</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Info */}
        <Card>
          <CardHeader>
            <CardTitle>Basic Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Evaluation Name</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm(prev => ({ ...prev, name: e.target.value }))}
                placeholder="e.g., GPT-4 vs Claude Comparison"
                className="mt-1"
                required
              />
            </div>
          </CardContent>
        </Card>

        {/* Model Selection */}
        <Card>
          <CardHeader>
            <CardTitle>Model Selection</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Provider</Label>
                <Select
                  value={form.provider}
                  onChange={(e) => setForm(prev => ({ ...prev, provider: e.target.value, model: '' }))}
                  className="mt-1"
                  required
                >
                  <option value="">Select provider</option>
                  {providers.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </Select>
              </div>
              <div>
                <Label>Model</Label>
                <Select
                  value={form.model}
                  onChange={(e) => setForm(prev => ({ ...prev, model: e.target.value }))}
                  disabled={!form.provider}
                  className="mt-1"
                  required
                >
                  <option value="">Select model</option>
                  {selectedProvider?.models.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Evaluators */}
        <Card>
          <CardHeader>
            <CardTitle>Evaluators</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {evaluators.map((evaluator) => (
              <div
                key={evaluator.id}
                onClick={() => toggleEvaluator(evaluator.id)}
                className={`p-4 rounded-lg border-2 cursor-pointer transition-colors ${
                  form.evaluators.includes(evaluator.id)
                    ? 'border-indigo-500 bg-indigo-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="flex items-start">
                  <input
                    type="checkbox"
                    checked={form.evaluators.includes(evaluator.id)}
                    onChange={() => {}}
                    className="mt-1 mr-3"
                  />
                  <div>
                    <p className="font-medium text-gray-900">{evaluator.name}</p>
                    <p className="text-sm text-gray-600 mt-1">{evaluator.description}</p>
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Examples */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Test Examples</CardTitle>
              <Button type="button" onClick={addExample} variant="outline" size="sm">
                <Plus className="h-4 w-4 mr-2" />
                Add Example
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {form.examples.map((example, index) => (
              <div key={index} className="p-4 border-2 border-gray-200 rounded-lg space-y-4">
                <div className="flex items-center justify-between">
                  <p className="font-medium text-gray-900">Example {index + 1}</p>
                  {form.examples.length > 1 && (
                    <Button
                      type="button"
                      onClick={() => removeExample(index)}
                      variant="ghost"
                      size="sm"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
                <div>
                  <Label>Prompt</Label>
                  <Textarea
                    value={example.prompt}
                    onChange={(e) => updateExample(index, 'prompt', e.target.value)}
                    placeholder="Enter the prompt..."
                    className="mt-1"
                    required
                  />
                </div>
                <div>
                  <Label>Expected Output</Label>
                  <Textarea
                    value={example.expected_output}
                    onChange={(e) => updateExample(index, 'expected_output', e.target.value)}
                    placeholder="Enter expected response..."
                    className="mt-1"
                    required
                  />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Actions */}
        <div className="flex justify-end gap-4">
          <Link href="/evaluations">
            <Button type="button" variant="outline">Cancel</Button>
          </Link>
          <Button type="submit" disabled={loading}>
            {loading ? 'Creating...' : 'Start Evaluation'}
          </Button>
        </div>
      </form>
    </div>
  )
}
