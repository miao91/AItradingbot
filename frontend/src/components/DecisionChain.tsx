import { Newspaper, Brain, Target, LineChart, ShoppingCart } from 'lucide-react'

interface DecisionChainProps {
  currentStep: number
}

const steps = [
  { id: 1, name: '新闻流', icon: Newspaper, description: '实时财经资讯' },
  { id: 2, name: '行业分析', icon: Brain, description: 'AI智能研判' },
  { id: 3, name: '核心资产', icon: Target, description: '标的筛选' },
  { id: 4, name: '技术分析', icon: LineChart, description: '买卖点判断' },
  { id: 5, name: '交易决策', icon: ShoppingCart, description: '下单执行' },
]

export function DecisionChain({ currentStep }: DecisionChainProps) {
  return (
    <div className="glass border-b border-neon-cyan/10 px-6 py-3">
      <div className="flex items-center justify-center">
        <div className="flex items-center gap-1">
          {steps.map((step, index) => {
            const isActive = step.id === currentStep
            const isCompleted = step.id < currentStep
            const Icon = step.icon

            return (
              <div key={step.id} className="flex items-center">
                {/* 步骤节点 */}
                <div
                  className={`
                    relative flex items-center gap-2 px-4 py-2.5 rounded-lg transition-all duration-300 cursor-default
                    ${isActive 
                      ? 'bg-gradient-to-r from-neon-cyan/20 to-neon-blue/20 border border-neon-cyan/40 shadow-glow-cyan' 
                      : isCompleted 
                        ? 'bg-gradient-to-r from-neon-green/10 to-transparent border border-neon-green/30' 
                        : 'bg-cyber-800/30 border border-border opacity-40'
                    }
                  `}
                >
                  {/* 发光效果 - 激活状态 */}
                  {isActive && (
                    <div className="absolute inset-0 bg-gradient-to-r from-neon-cyan/5 to-transparent rounded-lg animate-pulse" />
                  )}
                  
                  {/* 图标 */}
                  <div
                    className={`
                      relative w-7 h-7 rounded-md flex items-center justify-center text-xs font-bold
                      ${isActive 
                        ? 'bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/50' 
                        : isCompleted 
                          ? 'bg-neon-green/20 text-neon-green border border-neon-green/50' 
                          : 'bg-cyber-700 text-text-muted border border-border'
                      }
                    `}
                  >
                    {isCompleted ? (
                      <span className="text-neon-green">✓</span>
                    ) : (
                      <Icon className={`w-4 h-4 ${isActive ? 'text-neon-cyan' : ''}`} />
                    )}
                  </div>
                  
                  {/* 文字 */}
                  <div className="flex flex-col">
                    <span
                      className={`text-sm font-semibold font-display tracking-wide ${
                        isActive 
                          ? 'text-neon-cyan text-glow-cyan' 
                          : isCompleted 
                            ? 'text-neon-green' 
                            : 'text-text-muted'
                      }`}
                    >
                      {step.name}
                    </span>
                    <span className="text-[10px] text-text-muted font-mono">{step.description}</span>
                  </div>
                </div>
                
                {/* 连接线 */}
                {index < steps.length - 1 && (
                  <div className="relative w-10 h-0.5 mx-1">
                    <div className={`absolute inset-0 ${isCompleted ? 'bg-gradient-to-r from-neon-green to-neon-cyan' : 'bg-border'}`} />
                    {isCompleted && (
                      <div className="absolute inset-0 bg-gradient-to-r from-neon-green to-neon-cyan animate-pulse opacity-50" />
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
