// src/api/weight.ts
import api from './index'
import type { WeightConfig, ApiResponse } from '@/types/weight'

export const weightAPI = {
  // 健康检查
  healthCheck: () => api.get('/health'),

  // 获取配置
  getConfig: (): Promise<ApiResponse> => api.get('/weight/config'),

  // 更新配置
  updateConfig: (configs: WeightConfig[]): Promise<ApiResponse> =>
    api.post('/weight/config', { configs }),

  // 验证配置
  validateConfig: (configs: WeightConfig[]): Promise<ApiResponse> =>
    api.post('/weight/config/validate', { configs }),

  // 获取记录
  getRecords: (limit = 100): Promise<ApiResponse> =>
    api.get('/weight/records', { params: { limit } }),

  // 获取统计
  getStatistics: (date?: string): Promise<ApiResponse> =>
    api.get('/weight/statistics', { params: date ? { date } : {} }),

  // 获取实时数据
  getRealtime: (): Promise<ApiResponse> => api.get('/weight/realtime'),

  // 获取状态
  getStatus: (): Promise<ApiResponse> => api.get('/weight/status')
}