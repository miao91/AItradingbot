import { useEffect, useState, useCallback } from 'react'
import { Newspaper, Clock, Loader2, Zap, RefreshCw, AlertCircle } from 'lucide-react'
import type { NewsItem as NewsItemType } from '../types'
import { newsApi } from '../services/api'

interface NewsTickerProps {
  selectedNews: NewsItemType | null
  onSelect: (news: NewsItemType) => void
}

export function NewsTicker({ selectedNews, onSelect }: NewsTickerProps) {
  const [news, setNews] = useState<NewsItemType[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)

  const fetchNews = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await newsApi.getStream()
      setNews(data)
      setLastUpdate(new Date())
    } catch (err) {
      console.error('获取新闻失败:', err)
      setError('获取新闻失败，请检查后端服务')
    } finally {
      setLoading(false)
    }
  }, [])

  // 首次加载
  useEffect(() => {
    fetchNews()
  }, [fetchNews])

  // 自动刷新 - 每30秒
  useEffect(() => {
    const interval = setInterval(() => {
      fetchNews()
    }, 30000)
    return () => clearInterval(interval)
  }, [fetchNews])

  const getCategoryStyle = (category: string | undefined) => {
    const categoryStr = category || ''
    const styles: Record<string, { bg: string, border: string, text: string }> = {
      '宏观政策': { bg: 'bg-neon-orange/10', border: 'border-neon-orange/30', text: 'text-neon-orange' },
      '公司新闻': { bg: 'bg-neon-blue/10', border: 'border-neon-blue/30', text: 'text-neon-blue' },
      '业绩快报': { bg: 'bg-neon-green/10', border: 'border-neon-green/30', text: 'text-neon-green' },
      '板块异动': { bg: 'bg-neon-purple/10', border: 'border-neon-purple/30', text: 'text-neon-purple' },
      '行业新闻': { bg: 'bg-neon-blue/10', border: 'border-neon-blue/30', text: 'text-neon-blue' },
      '市场行情': { bg: 'bg-neon-red/10', border: 'border-neon-red/30', text: 'text-neon-red' },
    }
    return styles[categoryStr] || { bg: 'bg-cyber-700/30', border: 'border-border', text: 'text-text-secondary' }
  }

  return (
    <div className="h-full flex flex-col glass">
      <div className="flex items-center justify-between px-4 py-3 border-b border-neon-cyan/10 bg-cyber-800/30">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-md bg-gradient-to-br from-neon-cyan/20 to-neon-blue/20 border border-neon-cyan/30 flex items-center justify-center">
            <Newspaper className="w-4 h-4 text-neon-cyan" />
          </div>
          <span className="font-semibold text-sm title-display text-text-primary">实时新闻</span>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={fetchNews}
            className="p-1.5 rounded hover:bg-cyber-700/50 transition-colors"
            title="刷新新闻"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-neon-cyan ${loading ? 'animate-spin' : ''}`} />
          </button>
          <span className="text-xs text-text-muted font-mono">TUSHARE API</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin p-2 space-y-2">
        {loading && news.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <Loader2 className="w-8 h-8 mx-auto mb-3 text-neon-cyan animate-spin" />
              <p className="text-sm text-text-muted font-mono">正在获取实时新闻...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-full">
<div className="text-center px-4">
              <AlertCircle className="w-8 h-8 mx-auto mb-3 text-neon-red" />
              <p className="text-sm text-neon-red font-mono">{error}</p>
              <button 
                onClick={fetchNews}
                className="mt-3 px-4 py-2 text-xs bg-cyber-700/50 border border-neon-cyan/30 rounded text-neon-cyan hover:bg-cyber-700/80 transition-colors"
              >
                重试
              </button>
            </div>
          </div>
        ) : news.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <Newspaper className="w-8 h-8 mx-auto mb-3 text-text-muted" />
              <p className="text-sm text-text-muted font-mono">暂无新闻数据</p>
            </div>
          </div>
        ) : (
          news.map((item) => {
            const categoryStyle = getCategoryStyle(item.category)
            const isSelected = selectedNews?.id === item.id
            
            return (
              <div
                key={item.id}
                onClick={() => onSelect(item)}
                className={`
                  group relative p-3 rounded-lg cursor-pointer transition-all duration-300
                  ${isSelected 
                    ? 'bg-gradient-to-r from-neon-cyan/10 to-transparent border border-neon-cyan/40 shadow-glow-cyan' 
                    : 'hover:bg-cyber-800/50 border border-transparent hover:border-neon-cyan/20'
                  }
                `}
              >
                {isSelected && (
                  <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-neon-cyan to-neon-blue rounded-l-lg" />
                )}
                
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Clock className="w-3 h-3 text-neon-cyan" />
                    <span className="text-xs text-text-muted font-mono">{item.time}</span>
                  </div>
                  <span className={`text-[10px] px-2 py-0.5 rounded border ${categoryStyle.bg} ${categoryStyle.border} ${categoryStyle.text} font-mono`}>
                    {item.category || '市场行情'}
                  </span>
                </div>

                <h3 className={`text-sm leading-relaxed transition-colors ${isSelected ? 'text-neon-cyan' : 'text-text-primary group-hover:text-neon-cyan'}`}>
                  {item.title}
                </h3>

                <div className="flex items-center justify-between mt-3">
                  <span className="text-xs text-text-muted font-mono">{item.source}</span>
                  {item.relatedTickers && item.relatedTickers.length > 0 && (
                    <div className="flex gap-1">
                      {item.relatedTickers.slice(0, 2).map((ticker) => (
                        <span 
                          key={ticker} 
                          className="text-[10px] px-2 py-0.5 rounded bg-cyber-700/50 border border-border text-text-secondary font-mono"
                        >
                          {ticker}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>

      <div className="px-4 py-2 border-t border-neon-cyan/10 bg-cyber-800/30">
        <div className="flex items-center justify-between text-xs text-text-muted font-mono">
          <span>共 {news.length} 条新闻</span>
          <div className="flex items-center gap-2">
            <Zap className="w-3 h-3 text-neon-orange" />
            <span className="text-neon-green">实时更新</span>
            {lastUpdate && (
              <span className="text-text-muted">
                ({lastUpdate.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })})
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
