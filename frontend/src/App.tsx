import { useState } from 'react'
import { DecisionChain } from './components/DecisionChain'
import { NewsTicker } from './components/NewsTicker'
import { IndustryAnalysis } from './components/IndustryAnalysis'
import { AssetList } from './components/AssetList'
import { TechAnalysis } from './components/TechAnalysis'
import { TVChart } from './components/TVChart'
import { FinEngineering } from './components/FinEngineering'
import { Header } from './components/Header'
import type { NewsItem, AnalysisResult, Asset, TechSignals } from './types'

function App() {
  const [currentStep, setCurrentStep] = useState(1)
  const [selectedNews, setSelectedNews] = useState<NewsItem | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null)
  const [techSignals, setTechSignals] = useState<TechSignals | null>(null)

  const handleNewsSelect = (news: NewsItem) => {
    setSelectedNews(news)
    setCurrentStep(2)
    // 模拟AI分析
    setTimeout(() => {
      setAnalysis({
        industry: news.industry || '银行',
        sentiment: ['optimistic', 'neutral', 'pessimistic'][Math.floor(Math.random() * 3)] as any,
        confidence: 0.75 + Math.random() * 0.2,
        summary: `基于"${news.title}"的分析，该事件对${news.industry || '相关行业'}产生${Math.random() > 0.5 ? '积极' : '中性'}影响`,
        keyPoints: ['流动性改善', '政策支持力度加大', '市场预期向好'],
      })
      setCurrentStep(3)
    }, 1500)
  }

  const handleAssetSelect = (asset: Asset) => {
    setSelectedAsset(asset)
    setCurrentStep(4)
    // 模拟技术分析
    setTimeout(() => {
      setTechSignals({
        macd: { signal: Math.random() > 0.5 ? 'golden_cross' : 'death_cross', strength: 0.6 + Math.random() * 0.3 },
        ma: { trend: Math.random() > 0.5 ? 'bullish' : 'bearish', alignment: '多头排列' },
        overall: Math.random() > 0.5 ? 'BUY' : 'HOLD',
      })
      setCurrentStep(5)
    }, 1000)
  }

  return (
    <div className="min-h-screen bg-bg-primary">
      <Header />
      
      {/* 决策链条导航 */}
      <DecisionChain currentStep={currentStep} />
      
      {/* 主内容区 */}
      <div className="flex h-[calc(100vh-120px)]">
        {/* 左侧：新闻流 */}
        <div className="w-1/3 border-r border-border">
          <NewsTicker 
            selectedNews={selectedNews} 
            onSelect={handleNewsSelect} 
          />
        </div>
        
        {/* 右侧：动态内容 */}
        <div className="w-2/3 p-4 overflow-y-auto scrollbar-thin">
          {!selectedNews && (
            <div className="h-full flex items-center justify-center text-text-secondary">
              <div className="text-center">
                <div className="text-6xl mb-4">📰</div>
                <p className="text-lg">点击左侧新闻开始分析</p>
                <p className="text-sm mt-2 text-text-muted">决策链条：新闻 → 行业分析 → 核心资产 → 技术分析 → 下单</p>
              </div>
            </div>
          )}
          
          {selectedNews && (
            <div className="space-y-4">
              {/* 行业分析 */}
              {analysis && (
                <IndustryAnalysis 
                  news={selectedNews}
                  analysis={analysis}
                />
              )}
              
              {/* 核心资产 */}
              {analysis && (
                <AssetList 
                  industry={analysis.industry}
                  onSelect={handleAssetSelect}
                />
              )}
              
              {/* 技术分析 + 图表 */}
              {selectedAsset && (
                <div className="grid grid-cols-2 gap-4">
                  <TechAnalysis 
                    asset={selectedAsset}
                    signals={techSignals}
                  />
                  <TVChart ticker={selectedAsset.ticker} />
                </div>
              )}
              
              {/* 金融工程分析 */}
              {selectedAsset && (
                <FinEngineering ticker={selectedAsset.ticker} />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default App