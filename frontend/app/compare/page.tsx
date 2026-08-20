'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { comparisonsApi, providersApi } from '@/lib/api'
import { Provider, Evaluator } from '@/types/evaluation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Plus, Trash2, ArrowLeft, X } from 'lucide-react'
import Link from 'next/link'

const MIN_MODELS = 2
const MAX_MODELS = 5
const SEP = '::'

/** Encodes {provider, model} as a single <select> value and back. */
const encode = (provider: string, model: string) => `${provider}${SEP}${model}`
const decode = (value: string): [string, string] => {
  const i = value.indexOf(SEP)
  return i === -1 ? ['', ''] : [value.slice(0, i), value.slice(i + SEP.length)]
}

export default function ComparePage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [providers, setProviders] = useState<Provider[]>([])
  const [evaluators, setEvaluators] = useState<Evaluator[]>([])

  const [name, setName] = useState('')
  const [slots, setSlots] = useState<string[]>(['', ''])
  const [selectedEvaluators, setSelectedEvaluators] = useState<string[]>([
    'accuracy', 'performance', 'cost'
  ])
  const [examples, setExamples] = useState([{ prompt: '', expected_output: '' }])

  useEffect(() => {
    Promise.all([providersApi.list(), providersApi.listEvaluators()])
      .then(([providersRes, evaluatorsRes]) => {
        setProviders(providersRes.data)
        setEvaluators(evaluatorsRes.data)
      })
      .catch((error) => console.error('Failed to load data:', error))
  }, [])

  // Every model option, labelled "OpenAI / gpt-5.5", flattened across families.
  const allOptions = providers.flatMap((p) =>
    p.models.map((m) => ({ value: encode(p.id, m), label: `${p.name} / ${m}` }))
  )

  const addSlot = () => {
    if (slots.length < MAX_MODELS) setSlots((prev) => [...prev, ''])
  }

  const removeSlot = (index: number) => {
    if (slots.length > MIN_MODELS) {
      setSlots((prev) => prev.filter((_, i) => i !== index))
    }
  }

  const updateSlot = (index: number, value: string) => {
    setSlots((prev) => prev.map((s, i) => (i === index ? value : s)))
  }

  const toggleEvaluator = (id: string) => {
    setSelectedEvaluators((prev) =>
      prev.includes(id) ? prev.filter((e) => e !== id) : [...prev, id]
    )
  }

  const addExample = () => {
    setExamples((prev) => [...prev, { prompt: '', expected_output: '' }])
  }

  const removeExample = (index: number) => {
    setExamples((prev) => prev.filter((_, i) => i !== index))
  }

  const updateExample = (index: number, field: string, value: string) => {
    setExamples((prev) =>
      prev.map((ex, i) => (i === index ? { ...ex, [field]: value } : ex))
    )
  }

  const chosenValues = new Set(slots.filter(Boolean))
  const filledSlots = slots.filter(Boolean).length
  const canSubmit = name.trim() && filledSlots >= MIN_MODELS && selectedEvaluators.length > 0

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      const models = slots.filter(Boolean).map((slot) => {
        const [provider, model] = decode(slot)
        return { provider, model }
      })

      const response = await comparisonsApi.create({
        name,
        models,
        evaluators: selectedEvaluators,
        examples: examples.map((ex, i) => ({
          id: `example-${i}`,
          prompt: ex.prompt,
          expected_output: ex.expected_output,
        })),
      })

      router.push(`/compare/${response.data.id}`)
    } catch (error: any) {
      console.error('Failed to create comparison:', error)
      alert(`Failed to create comparison: ${error.response?.data?.detail || error.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <Link href="/evaluations" className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-4">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Evaluations
        </Link>
        <h1 className="text-3xl font-bold text-gray-900">Compare Models</h1>
        <p className="text-gray-600 mt-1">
          Run the same prompts against 2-5 models side by side.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Info */}
        <Card>
          <CardHeader>
            <CardTitle>Basic Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Comparison Name</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Reasoning models bakeoff"
                className="mt-1"
                required
              />
            </div>
          </CardContent>
        </Card>

        {/* Model Selection */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Models ({filledSlots}/{MAX_MODELS})</CardTitle>
                <p className="text-sm text-gray-500 mt-1">
                  Pick {MIN_MODELS}-{MAX_MODELS} models to run on the same prompts.
                </p>
              </div>
              {slots.length < MAX_MODELS && (
                <Button type="button" onClick={addSlot} variant="outline" size="sm">
                  <Plus className="h-4 w-4 mr-2" />
                  Add Model
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {slots.map((slot, index) => (
              <div key={index} className="flex items-center gap-3">
                <Select
                  value={slot}
                  onChange={(e) => updateSlot(index, e.target.value)}
                  className="flex-1"
                  required
                >
                  <option value="">Select a model</option>
                  {allOptions.map((opt) => (
                    <option
                      key={opt.value}
                      value={opt.value}
                      disabled={opt.value !== slot && chosenValues.has(opt.value)}
                    >
                      {opt.label}
                    </option>
                  ))}
                </Select>
                {slots.length > MIN_MODELS && (
                  <Button
                    type="button"
                    onClick={() => removeSlot(index)}
                    variant="ghost"
                    size="sm"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
            ))}
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
                  selectedEvaluators.includes(evaluator.id)
                    ? 'border-indigo-500 bg-indigo-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="flex items-start">
                  <input
                    type="checkbox"
                    checked={selectedEvaluators.includes(evaluator.id)}
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

        {/* Shared Prompts */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Shared Prompts</CardTitle>
                <p className="text-sm text-gray-500 mt-1">
                  Every model runs against these same prompts.
                </p>
              </div>
              <Button type="button" onClick={addExample} variant="outline" size="sm">
                <Plus className="h-4 w-4 mr-2" />
                Add Prompt
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {examples.map((example, index) => (
              <div key={index} className="p-4 border-2 border-gray-200 rounded-lg space-y-4">
                <div className="flex items-center justify-between">
                  <p className="font-medium text-gray-900">Prompt {index + 1}</p>
                  {examples.length > 1 && (
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
          <Button type="submit" disabled={loading || !canSubmit}>
            {loading ? 'Starting...' : 'Run Comparison'}
          </Button>
        </div>
      </form>
    </div>
  )
}
