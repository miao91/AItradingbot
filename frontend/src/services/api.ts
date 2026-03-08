import axios from 'axios'
import type { NewsItem, AnalysisResult, Asset, TechSignals, MonteCarloResult } from '../types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const newsApi = {
  getStream: async (): Promise<NewsItem[]> => {
    const response = await api.get('/api/news/stream')
    return response.data
  },
}

export const analysisApi = {
  analyzeIndustry: async (newsId: string, newsTitle: string): Promise<AnalysisResult> => {
    const response = await api.post('/api/analysis/industry', {
      news_id: newsId,
      news_title: newsTitle,
    })
    return response.data
  },
}

export const assetsApi = {
  getByIndustry: async (industry: string): Promise<Asset[]> => {
    const response = await api.get(`/api/assets/industry/${industry}`)
    return response.data
  },
}

export const technicalApi = {
  getAnalysis: async (ticker: string): Promise<TechSignals> => {
    const response = await api.get(`/api/technical/${ticker}`)
    return response.data
  },
}

export const financialApi = {
  getMonteCarlo: async (ticker: string): Promise<MonteCarloResult> => {
    const response = await api.get(`/api/financial/monte-carlo/${ticker}`)
    return response.data
  },
}