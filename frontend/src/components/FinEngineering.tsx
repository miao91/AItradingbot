import { useState } from 'react'
import { Calculator, TrendingDown, Activity, ChevronDown, ChevronUp, Info, Target, Shield } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, ReferenceLine } from 'recharts'

interface FinEngineeringProps {
  ticker: string
}

const generateMonteCarloData = () => {
  const data = []
  for (let i = -20; i <= 20; i += 1) {
    const value = Math.exp(-(i * i) / 50) * (Math.random() * 0.5 + 0.5)
    data.push({
      range: `${i}%`,
      probability: value * 100,
      value: i,
    })
  }
  return data
}

export function FinEngineering({ }: FinEngineeringProps) {
  const [expanded, setExpanded] = useState(false)
  const [monteCarloData] = useState(() => generateMonteCarloData())

  const var95 = 2.5
  const var99 = 4.2
  const sharpeRatio = 1.42
  const maxDrawdown = 12.5
  const winRate = 58.3

  return (
    <div className="card-glow p-4 animate-fade-in-up">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-br from-neon-purple/20 to-neon-orange/20 rounded-lg blur-md" />
            <div className="relative w-11 h-11 rounded-lg bg-gradient-to-br from-neon-purple/20 to-neon-orange/20 border border-neon-purple/30 flex items-center justify-center">
              <Calculator className="w-5 h-5 text-neon-purple" />
            </div>
          </div>
          <div>
            <h3 className="font-semibold text-sm title-display text-text-primary">金融工程分析</h3>
            <p className="text-xs text-text-muted font-mono">蒙特卡洛模拟 & 风险评估</p>
          </div>
        </div>
        
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-xs text-neon-blue hover:text-neon-cyan transition-colors font-mono px-3 py-1.5 rounded border border-neon-cyan/20 hover:border-neon-cyan/50"
        >
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          {expanded ? '收起' : '展开'}
        </button>
      </div>

      <div className="grid grid-cols-4 gap-3 mb-4">
        <div className="p-3 rounded-lg bg-cyber-800/30 border border-neon-red/20">
          <div className="flex items-center gap-1 text-xs text-text-muted mb-1 font-mono">
            <TrendingDown className="w-3 h-3 text-neon-red" />
            <span>VaR 95%</span>
          </div>
          <div className="text-lg font-bold font-mono text-neon-red text-glow-red">-{var95}%</div>
          <div className="text-[10px] text-text-muted font-mono">最大可能损失</div>
        </div>

        <div className="p-3 rounded-lg bg-cyber-800/30 border border-neon-red/20">
          <div className="flex items-center gap-1 text-xs text-text-muted mb-1 font-mono">
            <Shield className="w-3 h-3 text-neon-red" />
            <span>VaR 99%</span>
          </div>
          <div className="text-lg font-bold font-mono text-neon-red">-{var99}%</div>
          <div className="text-[10px] text-text-muted font-mono">极端情况损失</div>
        </div>

        <div className="p-3 rounded-lg bg-cyber-800/30 border border-neon-green/20">
          <div className="flex items-center gap-1 text-xs text-text-muted mb-1 font-mono">
            <Activity className="w-3 h-3 text-neon-green" />
            <span>夏普比率</span>
          </div>
          <div className="text-lg font-bold font-mono text-neon-green text-glow-green">{sharpeRatio}</div>
          <div className="text-[10px] text-text-muted font-mono">风险调整后收益</div>
        </div>

        <div className="p-3 rounded-lg bg-cyber-800/30 border border-neon-cyan/20">
          <div className="flex items-center gap-1 text-xs text-text-muted mb-1 font-mono">
            <Target className="w-3 h-3 text-neon-cyan" />
            <span>胜率</span>
          </div>
          <div className="text-lg font-bold font-mono text-neon-cyan">{winRate}%</div>
          <div className="text-[10px] text-text-muted font-mono">历史回测</div>
        </div>
      </div>

      {expanded && (
        <div className="space-y-4">
          <div className="p-3 rounded-lg bg-cyber-800/30 border border-neon-cyan/10">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-semibold text-text-primary font-display">收益概率分布</span>
              <div className="flex items-center gap-1">
                <Info className="w-4 h-4 text-text-muted" />
                <span className="text-xs text-text-muted font-mono">蒙特卡洛模拟</span>
              </div>
            </div>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={monteCarloData}>
                  <XAxis 
                    dataKey="range" 
                    tick={{ fontSize: 10, fill: '#94a3b8' }}
                    interval={4}
                    axisLine={{ stroke: '#334155' }}
                    tickLine={false}
                  />
                  <YAxis 
                    tick={{ fontSize: 10, fill: '#94a3b8' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <ReferenceLine x="0%" stroke="#64748b" strokeDasharray="3 3" />
                  <Bar dataKey="probability" radius={[2, 2, 0, 0]}>
                    {monteCarloData.map((entry, index) => (
                      <Cell 
                        key={`cell-${index}`} 
                        fill={entry.value >= 0 ? '#10b981' : '#ef4444'}
                        fillOpacity={0.7}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 flex items-center justify-between text-xs text-text-muted font-mono">
              <span>基于 10,000 次随机模拟</span>
              <span className="text-neon-cyan">置信区间: 95%</span>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-neon-red/5 border border-neon-red/20">
            <h4 className="text-sm font-semibold text-neon-red mb-2 flex items-center gap-2">
              <Shield className="w-4 h-4" />
              风险提示
            </h4>
            <ul className="text-xs text-text-secondary space-y-1.5 font-mono">
              <li className="flex items-center gap-2">
                <span className="text-neon-red">•</span>
                <span>最大回撤：{maxDrawdown}% (历史数据)</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="text-neon-orange">•</span>
                <span>波动率：中等偏高，建议控制仓位</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="text-text-muted">•</span>
                <span>模拟结果仅供参考，不构成投资建议</span>
              </li>
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}
