import Link from 'next/link'
import { FlaskConical, Activity, TrendingUp, DollarSign, Plus, ArrowRight } from 'lucide-react'

export default function DashboardPage() {
  return (
    <div className="min-h-screen">
      <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold text-slate-900">Dashboard</h1>
            <p className="text-slate-600 mt-2 text-lg">Monitor your LLM evaluation metrics</p>
          </div>
          <Link href="/evaluations/new">
            <button className="btn-primary h-12 px-6 flex items-center gap-2 text-base">
              <Plus className="w-5 h-5" />
              New Evaluation
            </button>
          </Link>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard
            title="Total Evaluations"
            value="0"
            icon={FlaskConical}
            gradient="from-blue-500 to-cyan-500"
          />
          <StatCard
            title="Success Rate"
            value="0%"
            icon={TrendingUp}
            gradient="from-green-500 to-emerald-500"
          />
          <StatCard
            title="Avg Response Time"
            value="0ms"
            icon={Activity}
            gradient="from-purple-500 to-pink-500"
          />
          <StatCard
            title="Total Cost"
            value="$0.00"
            icon={DollarSign}
            gradient="from-orange-500 to-red-500"
          />
        </div>

        {/* Hero Card */}
        <div className="card card-hover p-12 text-center bg-gradient-to-br from-indigo-50 via-white to-purple-50">
          <div className="max-w-2xl mx-auto space-y-6">
            <div className="inline-flex p-4 bg-indigo-100 rounded-2xl">
              <FlaskConical className="w-12 h-12 text-indigo-600" />
            </div>
            <div>
              <h2 className="text-3xl font-bold text-slate-900 mb-3">
                Start Evaluating LLMs
              </h2>
              <p className="text-slate-600 text-lg leading-relaxed">
                Create comprehensive evaluations to measure accuracy, performance, and cost across multiple language models.
              </p>
            </div>
            <div className="flex items-center justify-center gap-4">
              <Link href="/evaluations/new">
                <button className="btn-primary h-12 px-8 text-base flex items-center gap-2">
                  Create Evaluation
                  <ArrowRight className="w-5 h-5" />
                </button>
              </Link>
              <Link href="/evaluations">
                <button className="btn-secondary h-12 px-8 text-base">
                  View All
                </button>
              </Link>
            </div>
          </div>
        </div>

        {/* Features */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <FeatureCard
            title="Accuracy Analysis"
            description="Measure semantic similarity, BLEU scores, ROUGE metrics, and exact match accuracy."
            icon="🎯"
          />
          <FeatureCard
            title="Performance Testing"
            description="Track latency, throughput, and token generation speed across different models."
            icon="⚡"
          />
          <FeatureCard
            title="Cost Optimization"
            description="Monitor token usage and API costs to optimize your LLM infrastructure spending."
            icon="💰"
          />
        </div>
      </div>
    </div>
  )
}

interface StatCardProps {
  title: string
  value: string
  icon: any
  gradient: string
}

function StatCard({ title, value, icon: Icon, gradient }: StatCardProps) {
  return (
    <div className="card card-hover overflow-hidden">
      <div className="p-6">
        <div className="flex items-start justify-between mb-4">
          <div className={`p-3 rounded-xl bg-gradient-to-br ${gradient}`}>
            <Icon className="w-6 h-6 text-white" />
          </div>
        </div>
        <div>
          <p className="text-sm font-medium text-slate-600 mb-1">{title}</p>
          <p className="text-3xl font-bold text-slate-900">{value}</p>
        </div>
      </div>
      <div className={`h-1 bg-gradient-to-r ${gradient}`} />
    </div>
  )
}

interface FeatureCardProps {
  title: string
  description: string
  icon: string
}

function FeatureCard({ title, description, icon }: FeatureCardProps) {
  return (
    <div className="card card-hover p-6">
      <div className="text-4xl mb-4">{icon}</div>
      <h3 className="text-lg font-semibold text-slate-900 mb-2">{title}</h3>
      <p className="text-slate-600 leading-relaxed">{description}</p>
    </div>
  )
}
