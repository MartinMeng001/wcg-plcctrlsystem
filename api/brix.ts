// src/api/brix.ts
import api from './index'
import type {
  BrixConfig,
  BrixCalibrationRequest,
  BrixExportRequest
} from '@/types/brix'
import type {
  ApiResponse
} from '@/types/weight'

export const brixAPI = {
  // 健康检查
  healthCheck: () => api.get('/health'),

  // 配置管理
  getConfig: (): Promise<ApiResponse> => api.get('/brix/config'),

  updateConfig: (configs: BrixConfig[]): Promise<ApiResponse> =>
    api.post('/brix/config', { configs }),

  validateConfig: (configs: BrixConfig[]): Promise<ApiResponse> =>
    api.post('/brix/config/validate', { configs }),

  // 实时监控
  getRealtime: (params?: {
    channels?: string
    include_raw?: boolean
  }): Promise<ApiResponse> =>
    api.get('/brix/realtime', { params }),

  getStatus: (): Promise<ApiResponse> =>
    api.get('/brix/status'),

  // 历史数据
  getRecords: (params?: {
    limit?: number
    start_time?: string
    end_time?: string
    grade_id?: number
    min_brix?: number
    max_brix?: number
  }): Promise<ApiResponse> =>
    api.get('/brix/records', { params }),

  // 统计分析
  getStatistics: (params?: {
    date?: string
    period?: 'hour' | 'day' | 'week' | 'month'
    group_by?: 'grade' | 'hour' | 'channel'
  }): Promise<ApiResponse> =>
    api.get('/brix/statistics', { params }),

  // 设备控制
  calibrateSensor: (data: BrixCalibrationRequest): Promise<ApiResponse> =>
    api.post('/brix/calibration', data),

  resetSensor: (data: {
    reset_type: 'soft' | 'hard'
    reason?: string
  }): Promise<ApiResponse> =>
    api.post('/brix/sensor/reset', data),

  // 报警管理
  getAlerts: (params?: {
    level?: 'info' | 'warning' | 'error' | 'critical' | 'all'
    status?: 'active' | 'resolved' | 'all'
    limit?: number
  }): Promise<ApiResponse> =>
    api.get('/brix/alerts', { params }),

  resolveAlert: (alertId: string, data: {
    resolution: string
    resolved_by: string
  }): Promise<ApiResponse> =>
    api.post(`/brix/alerts/${alertId}/resolve`, data),

  // 数据导出
  exportData: (data: BrixExportRequest): Promise<ApiResponse> =>
    api.post('/brix/export', data),

  getExportStatus: (taskId: string): Promise<ApiResponse> =>
    api.get(`/brix/export/${taskId}`)
}