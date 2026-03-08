import { Brain, TrendingUp, TrendingDown, Minus, Target, Lightbulb, ChevronDown, ChevronUp, Sparkles } from 'lucide-react'
import { useState } from 'react'
import type { NewsItem, AnalysisResult } from '../types'

interface IndustryAnalysisProps {
  news: NewsItem
  analysis: AnalysisResult
}

export function IndustryAnalysis({ news, analysis }: IndustryAnalysisProps) {
  const [expanded, setExpanded] = useState(false)

  const getSentimentConfig = (sentiment: string) => {
    switch (sentiment) {
      case 'optimistic':
        return {
          icon: TrendingUp,
          label: '乐观',
          color: 'text-neon-green',
          bgColor: 'bg-neon-green/10',
          borderColor: 'border-neon-green/30',
          barColor: 'bg-neon-green',
          glow: 'shadow-glow-green',
        }
      case 'pessimistic':
        return {
          icon: TrendingDown,
          label: '悲观',
          color: 'text-neon-red',
          bgColor: 'bg-neon-red/10',
          borderColor: 'border-neon-red/30',
          barColor: 'bg-neon-red',
          glow: 'shadow-glow-red',
        }
      default:
        return {
          icon: Minus,
          label: '中性',
          color: 'text-neon-blue',
          bgColor: 'bg-neon-blue/10',
          borderColor: 'border-neon-blue/30',
          barColor: 'bg-neon-blue',
          glow: 'shadow-glow-cyan',
        }
    }
  }

  const config = getSentimentConfig(analysis.sentiment)
  const Icon = config.icon

  return (
    <div className="card-glow p-4 animate-fade-in-up">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className={`absolute inset-0 bg-gradient-to-br from-neon-cyan/20 to-neon-blue/20 rounded-lg blur-md`} />
            <div className={`relative w-11 h-11 rounded-lg flex items-center justify-center ${config.bgColor} border ${config.borderColor}`}>
              <Brain className={`w-5 h-5 ${config.color}`} />
            </div>
          </div>
          <div>
            <h3 className="font-semibold text-sm title-display text-text-primary">AI 行业分析</h3>
            <p className="text-xs text-text-muted font-mono">基于：{news.title.slice(0, 30)}...</p>
          </div>
        </div>
        
        <div className={`flex items-center gap-2 px-4 py-2 rounded-lg ${config.bgColor} border ${config.borderColor} ${config.glow}`}>
          <Icon className={`w-5 h-5 ${config.color}`} />
          <div>
            <div className={`text-lg font-bold font-display ${config.color} text-glow-${config.color.split('-')[1]}`}>{config.label}</div>
            <div className="text-xs text-text-muted font-mono">置信度 {(analysis.confidence * 100).toFixed(0)}%</div>
          </div>
        </div>
      </div>

      <div className="mt-4 p-3 rounded-lg bg-cyber-800/50 border border-neon-cyan/20">
        <div className="flex items-start gap-2">
          <Target className="w-4 h-4 text-neon-cyan mt-0.5 flex-shrink-0" />
          <p className="text-sm text-text-primary">{analysis.summary}</p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {analysis.keyPoints.map((point, idx) => (
          <span 
            key={idx} 
            className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded border bg-cyber-800/30 border-border text-text-secondary font-mono"
          >
            <Lightbulb className="w-3 h-3 text-neon-orange" />
            {point}
          </span>
        ))}
      </div>

      <button
        onClick={() => setExpanded(!expanded)}
        className="mt-4 flex items-center gap-1 text-xs text-neon-blue hover:text-neon-cyan transition-colors font-mono"
      >
        {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        {expanded ? '收起详细分析' : '查看详细分析'}
      </button>

      {expanded && (
        <div className="mt-3 p-4 rounded-lg bg-cyber-800/30 border border-neon-cyan/10 text-sm text-text-secondary leading-relaxed">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="w-4 h-4 text-neon-purple" />
            <p className="text-text-primary font-semibold">行业影响分析</p>
          </div>
          <p>该新闻对{analysis.industry}行业产生{config.label}影响。从基本面来看，政策支持力度加大，市场预期向好。从资金面来看，相关板块资金流入明显，短期动能充足。</p>
          <p className="mt-3"><span className="text-neon-orange font-semibold">风险提示：</span> 需关注后续政策落地情况及市场情绪变化。建议结合技术分析进一步确认入场时机。</p>
        </div>
      )}
    </div>
  )
}
