import { Target, ArrowRight, TrendingUp, TrendingDown, Star } from 'lucide-react'
import type { Asset } from '../types'

interface AssetListProps {
  industry: string
  onSelect: (asset: Asset) => void
}

const mockAssets: Record<string, Asset[]> = {
  '银行': [
    { ticker: '600036.SH', name: '招商银行', type: '核心资产', weight: '高', price: 35.68, change: 0.89, changePct: 2.56 },
    { ticker: '000001.SZ', name: '平安银行', type: '核心资产', weight: '高', price: 12.58, change: -0.12, changePct: -0.94 },
    { ticker: '600016.SH', name: '民生银行', type: '一般资产', weight: '中', price: 3.92, change: 0.03, changePct: 0.77 },
  ],
  '新能源': [
    { ticker: '300750.SZ', name: '宁德时代', type: '核心资产', weight: '高', price: 198.50, change: 5.20, changePct: 2.69 },
    { ticker: '002594.SZ', name: '比亚迪', type: '核心资产', weight: '高', price: 268.00, change: 3.50, changePct: 1.32 },
    { ticker: '601012.SH', name: '隆基绿能', type: '一般资产', weight: '中', price: 22.35, change: -0.45, changePct: -1.97 },
  ],
  '白酒': [
    { ticker: '600519.SH', name: '贵州茅台', type: '核心资产', weight: '高', price: 1689.00, change: 18.50, changePct: 1.11 },
    { ticker: '000858.SZ', name: '五粮液', type: '核心资产', weight: '高', price: 148.20, change: 2.10, changePct: 1.44 },
    { ticker: '000568.SZ', name: '泸州老窖', type: '一般资产', weight: '中', price: 185.30, change: 1.80, changePct: 0.98 },
  ],
  '半导体': [
    { ticker: '688981.SH', name: '中芯国际', type: '核心资产', weight: '高', price: 58.90, change: 2.85, changePct: 5.08 },
    { ticker: '688256.SH', name: '寒武纪', type: '成长资产', weight: '中', price: 125.60, change: 8.20, changePct: 6.99 },
    { ticker: '603501.SH', name: '韦尔股份', type: '一般资产', weight: '中', price: 98.50, change: 1.20, changePct: 1.23 },
  ],
}

export function AssetList({ industry, onSelect }: AssetListProps) {
  const assets = mockAssets[industry] || mockAssets['银行']

  return (
    <div className="card-glow p-4 animate-fade-in-up">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-br from-neon-purple/20 to-neon-orange/20 rounded-lg blur-md" />
            <div className="relative w-11 h-11 rounded-lg bg-gradient-to-br from-neon-purple/20 to-neon-orange/20 border border-neon-purple/30 flex items-center justify-center">
              <Target className="w-5 h-5 text-neon-purple" />
            </div>
          </div>
          <div>
            <h3 className="font-semibold text-sm title-display text-text-primary">{industry} 核心资产</h3>
            <p className="text-xs text-text-muted font-mono">点击股票查看技术分析</p>
          </div>
        </div>
      </div>

      <div className="space-y-2">
        {assets.map((asset) => {
          const isPositive = (asset.changePct || 0) >= 0
          
          return (
            <div
              key={asset.ticker}
              onClick={() => onSelect(asset)}
              className="group flex items-center justify-between p-3 rounded-lg bg-cyber-800/30 border border-border hover:border-neon-purple/40 hover:bg-cyber-800/50 cursor-pointer transition-all duration-300"
            >
              <div className="flex items-center gap-3">
                <div className={`
                  w-8 h-8 rounded-md flex items-center justify-center text-[10px] font-bold font-mono border
                  ${asset.weight === '高' ? 'bg-neon-green/10 border-neon-green/30 text-neon-green' : 
                    asset.weight === '中' ? 'bg-neon-orange/10 border-neon-orange/30 text-neon-orange' : 
                    'bg-cyber-700 border-border text-text-muted'}
                `}>
                  {asset.weight === '高' ? 'AAA' : asset.weight === '中' ? 'AA' : 'A'}
                </div>
                
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-text-primary">{asset.name}</span>
                    {asset.type === '核心资产' && (
                      <Star className="w-3 h-3 text-neon-orange fill-neon-orange" />
                    )}
                  </div>
                  <span className="text-xs text-text-muted font-mono">{asset.ticker}</span>
                </div>
              </div>

              <div className="text-right">
                <div className="font-semibold text-text-primary font-mono">{asset.price?.toFixed(2)}</div>
                <div className={`
                  flex items-center gap-1 text-xs justify-end font-mono
                  ${isPositive ? 'text-neon-green' : 'text-neon-red'}
                `}>
                  {isPositive ? (
                    <TrendingUp className="w-3 h-3" />
                  ) : (
                    <TrendingDown className="w-3 h-3" />
                  )}
                  <span>{isPositive ? '+' : ''}{asset.changePct?.toFixed(2)}%</span>
                </div>
              </div>

              <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-neon-purple transition-colors group-hover:translate-x-1" />
            </div>
          )
        })}
      </div>
    </div>
  )
}
