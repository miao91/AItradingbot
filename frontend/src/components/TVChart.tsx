import { useEffect, useRef } from 'react'
import { BarChart3, Maximize2 } from 'lucide-react'

interface TVChartProps {
  ticker: string
}

export function TVChart({ ticker }: TVChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  // 转换股票代码格式
  const getTVSymbol = (ticker: string) => {
    // 中国A股代码转换
    if (ticker.endsWith('.SH')) {
      return `SSE:${ticker.replace('.SH', '')}`
    } else if (ticker.endsWith('.SZ'))
    {
      return `SZSE:${ticker.replace('.SZ', '')}`
    }
    return ticker
  }

  useEffect(() => {
    if (!containerRef.current) return

    // 清除之前的内容
    containerRef.current.innerHTML = ''

    // 创建 TradingView Widget
    const script = document.createElement('script')
    script.src = 'https://s3.tradingview.com/tv.js'
    script.async = true
    script.onload = () => {
      if ((window as any).TradingView) {
        new (window as any).TradingView.widget({
          autosize: true,
          symbol: getTVSymbol(ticker),
          interval: 'D',
          timezone: 'Asia/Shanghai',
          theme: 'dark',
          style: '1',
          locale: 'zh_CN',
          toolbar_bg: '#141414',
          enable_publishing: false,
          allow_symbol_change: false,
          container_id: 'tradingview_chart',
          hide_side_toolbar: false,
          studies: ['MASimple@tv-basicstudies', 'MACD@tv-basicstudies'],
          show_popup_button: true,
          popup_width: '1000',
          popup_height: '650',
        })
      }
    }

    document.head.appendChild(script)

    return () => {
      if (script.parentNode) {
        script.parentNode.removeChild(script)
      }
    }
  }, [ticker])

  return (
    <div className="card p-4 h-full">
      {/* 头部 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-neutral/10 flex items-center justify-center">
            <BarChart3 className="w-5 h-5 text-neutral" />
          </div>
          <div>
            <h3 className="font-semibold text-text-primary">K线图表</h3>
            <p className="text-xs text-text-muted">TradingView 实时行情</p>
          </div>
        </div>
        <button 
          className="p-2 rounded-lg hover:bg-bg-hover transition-colors"
          onClick={() => {
            const chart = document.getElementById('tradingview_chart')
            if (chart) {
              chart.requestFullscreen()
            }
          }}
        >
          <Maximize2 className="w-4 h-4 text-text-muted" />
        </button>
      </div>

      {/* TradingView 容器 */}
      <div 
        id="tradingview_chart" 
        ref={containerRef}
        className="w-full h-[300px] rounded-lg overflow-hidden"
      />

      {/* 图例说明 */}
      <div className="mt-3 flex items-center gap-4 text-xs text-text-muted">
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-bullish" />
          <span>MA均线</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-neutral" />
          <span>MACD</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-warning" />
          <span>成交量</span>
        </div>
      </div>
    </div>
  )
}