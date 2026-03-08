import { TrendingUp, Activity, Wifi, Cpu } from 'lucide-react'

interface HeaderProps {
  className?: string
}

export function Header({ className = '' }: HeaderProps) {
  return (
    <header className={`glass border-b border-neon-cyan/20 px-6 py-3 ${className}`}>
      <div className="flex items-center justify-between">
        {/* Logo区域 - 带发光效果 */}
        <div className="flex items-center gap-4">
          <div className="relative">
            {/* 发光背景 */}
            <div className="absolute inset-0 bg-gradient-to-br from-neon-cyan/30 to-neon-blue/30 rounded-lg blur-lg" />
            <div className="relative w-12 h-12 bg-gradient-to-br from-neon-cyan/20 to-neon-blue/20 rounded-lg flex items-center justify-center border border-neon-cyan/30 shadow-glow-cyan">
              <TrendingUp className="w-6 h-6 text-neon-cyan" />
            </div>
          </div>
          <div>
            <h1 className="text-xl font-bold title-display text-gradient-cyan">
              AI TradeBot <span className="text-neon-green text-sm font-normal ml-1">QUANT</span>
            </h1>
            <p className="text-xs text-text-secondary font-mono tracking-wider">华尔街级智能决策系统 v2.0</p>
          </div>
        </div>
        
        {/* 状态指示器 - HUD风格 */}
        <div className="flex items-center gap-6">
          {/* 运行状态 */}
          <div className="flex items-center gap-2 px-4 py-2 rounded-md bg-cyber-800/50 border border-neon-green/20">
            <div className="relative">
              <div className="absolute inset-0 bg-neon-green/50 rounded-full animate-ping opacity-75" />
              <div className="relative w-2.5 h-2.5 bg-neon-green rounded-full shadow-glow-green" />
            </div>
            <span className="text-xs text-neon-green font-mono font-semibold tracking-wide">系统运行中</span>
          </div>
          
          {/* 技术指标 */}
          <div className="flex items-center gap-4 text-xs font-mono">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-cyber-800/30 border border-border">
              <Wifi className="w-3.5 h-3.5 text-neon-cyan" />
              <span className="text-text-secondary">延迟:</span>
              <span className="text-neon-cyan font-semibold">12ms</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-cyber-800/30 border border-border">
              <Activity className="w-3.5 h-3.5 text-neon-blue" />
              <span className="text-text-secondary">API:</span>
              <span className="text-neon-green font-semibold">在线</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-cyber-800/30 border border-border">
              <Cpu className="w-3.5 h-3.5 text-neon-purple" />
              <span className="text-text-secondary">AI:</span>
              <span className="text-neon-green font-semibold">正常</span>
            </div>
          </div>
          
          {/* 时间显示 */}
          <div className="text-xs text-text-muted font-mono px-4 py-2 rounded bg-cyber-900/50 border border-border">
            {new Date().toLocaleString('zh-CN', { 
              year: 'numeric', 
              month: '2-digit', 
              day: '2-digit',
              hour: '2-digit', 
              minute: '2-digit',
              second: '2-digit'
            })}
          </div>
        </div>
      </div>
    </header>
  )
}
