import { LineChart, Activity, TrendingUp, TrendingDown, Minus, AlertTriangle, CheckCircle2 } from 'lucide-react'
import type { Asset, TechSignals } from '../types'

interface TechAnalysisProps {
  asset: Asset
  signals: TechSignals | null
}

export function TechAnalysis({ asset, signals }: TechAnalysisProps) {
  if (!signals) {
    return (
      <div className="card p-4 h-full flex items-center justify-center">
        <div className="text-center text-text-muted">
          <Activity className="w-8 h-8 mx-auto mb-2 animate-pulse" />
          <p className="text-sm">正在分析技术指标...</p>
        </div>
      </div>
    )
  }

  const getSignalBadge = (signal: string) => {
    switch (signal) {
      case 'golden_cross':
        return <span className="badge-bullish">金叉</span>
      case 'death_cross':
        return <span className="badge-bearish">死叉</span>
      case 'divergence':
        return <span className="badge-warning">背离</span>
      default:
        return <span className="badge-neutral">中性</span>
    }
  }

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'bullish':
        return <TrendingUp className="w-4 h-4 text-bullish" />
      case 'bearish':
        return <TrendingDown className="w-4 h-4 text-bearish" />
      default:
        return <Minus className="w-4 h-4 text-neutral" />
    }
  }

  const getOverallBadge = (overall: string) => {
    const configs: Record<string, { class: string; text: string }> = {
      'STRONG_BUY': { class: 'bg-bullish text-black', text: '强烈买入' },
      'BUY': { class: 'bg-bullish/80 text-black', text: '买入' },
      'HOLD': { class: 'bg-warning text-black', text: '持有' },
      'SELL': { class: 'bg-bearish/80 text-black', text: '卖出' },
      'STRONG_SELL': { class: 'bg-bearish text-black', text: '强烈卖出' },
    }
    const config = configs[overall] || configs['HOLD']
    return <span className={`px-3 py-1 rounded-lg text-sm font-bold ${config.class}`}>{config.text}</span>
  }

  return (
    <div className="card p-4">
      {/* 头部 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-neutral/10 flex items-center justify-center">
            <LineChart className="w-5 h-5 text-neutral" />
          </div>
          <div>
            <h3 className="font-semibold text-text-primary">{asset.name}</h3>
            <p className="text-xs text-text-muted">技术分析</p>
          </div>
        </div>
        {getOverallBadge(signals.overall)}
      </div>

      {/* MACD 信号 */}
      <div className="mb-3 p-3 rounded-lg bg-bg-primary border border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-text-primary">MACD</span>
            <span className="text-xs text-text-muted">指标</span>
          </div>
          {getSignalBadge(signals.macd.signal)}
        </div>
        <div className="mt-2 flex items-center gap-2">
          <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
            <div 
              className={`h-full ${signals.macd.signal === 'golden_cross' ? 'bg-bullish' : signals.macd.signal === 'death_cross' ? 'bg-bearish' : 'bg-neutral'}`}
              style={{ width: `${signals.macd.strength * 100}%` }}
            />
          </div>
          <span className="text-xs text-text-muted">{(signals.macd.strength * 100).toFixed(0)}%</span>
        </div>
        <div className="mt-1 text-xs text-text-muted">
          {signals.macd.signal === 'golden_cross' && 'DIF上穿DEA，买入信号'}
          {signals.macd.signal === 'death_cross' && 'DIF下穿DEA，卖出信号'}
          {signals.macd.signal === 'divergence' && '价格与MACD背离，注意反转'}
          {signals.macd.signal === 'neutral' && '暂无明确信号'}
        </div>
      </div>

      {/* 均线信号 */}
      <div className="mb-3 p-3 rounded-lg bg-bg-primary border border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-text-primary">均线系统</span>
            <span className="text-xs text-text-muted">MA5/MA10/MA20</span>
          </div>
          {getTrendIcon(signals.ma.trend)}
        </div>
        <div className="mt-2 text-sm text-text-primary">
          {signals.ma.alignment}
        </div>
        <div className="mt-1 text-xs text-text-muted">
          {signals.ma.trend === 'bullish' && '短期均线在长期均线上方，趋势向上'}
          {signals.ma.trend === 'bearish' && '短期均线在长期均线下方，趋势向下'}
          {signals.ma.trend === 'neutral' && '均线交织，趋势不明'}
        </div>
      </div>

      {/* 综合评估 */}
      <div className={`
        p-3 rounded-lg border
        ${signals.overall.includes('BUY') ? 'bg-bullish/5 border-bullish/30' : 
          signals.overall.includes('SELL') ? 'bg-bearish/5 border-bearish/30' : 
          'bg-warning/5 border-warning/30'}
      `}>
        <div className="flex items-start gap-2">
          {signals.overall.includes('BUY') ? (
            <CheckCircle2 className="w-4 h-4 text-bullish mt-0.5 flex-shrink-0" />
          ) : signals.overall.includes('SELL') ? (
            <AlertTriangle className="w-4 h-4 text-bearish mt-0.5 flex-shrink-0" />
          ) : (
            <Minus className="w-4 h-4 text-warning mt-0.5 flex-shrink-0" />
          )}
          <div>
            <span className="text-sm font-medium text-text-primary">综合建议：{getOverallBadge(signals.overall).props.children}</span>
            <p className="text-xs text-text-muted mt-1">
              {signals.overall.includes('BUY') && '技术指标共振，建议逢低买入'}
              {signals.overall.includes('SELL') && '技术指标走弱，建议减仓观望'}
              {signals.overall === 'HOLD' && '信号不明确，建议持仓观望'}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}