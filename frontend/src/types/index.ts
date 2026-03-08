export interface NewsItem {
  id: string
  time: string
  title: string
  source: string
  relatedTickers?: string[]
  category?: string
  industry?: string
}

export interface AnalysisResult {
  industry: string
  sentiment: 'optimistic' | 'neutral' | 'pessimistic'
  confidence: number
  summary: string
  detailedAnalysis?: string
  keyPoints: string[]
}

export interface Asset {
  ticker: string
  name: string
  type: string
  weight: '高' | '中' | '低'
  price?: number
  change?: number
  changePct?: number
}

export interface TechSignals {
  macd: {
    signal: 'golden_cross' | 'death_cross' | 'divergence' | 'neutral'
    strength: number
  }
  ma: {
    trend: 'bullish' | 'bearish' | 'neutral'
    alignment: string
  }
  overall: 'BUY' | 'SELL' | 'HOLD' | 'STRONG_BUY' | 'STRONG_SELL'
}

export interface MonteCarloResult {
  var95: number
  var99: number
  sharpeRatio: number
  maxDrawdown: number
  distribution: number[]
}