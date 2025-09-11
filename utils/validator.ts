// src/utils/validator.ts
import type { WeightConfig } from '@/types/weight'

// 配置验证结果接口
export interface ValidationResult {
  valid: boolean
  errors: string[]
  warnings: string[]
}

// 验证重量配置
export const validateWeightConfigs = (configs: WeightConfig[]): ValidationResult => {
  const result: ValidationResult = {
    valid: true,
    errors: [],
    warnings: []
  }

  if (configs.length === 0) {
    result.valid = false
    result.errors.push('至少需要一个配置项')
    return result
  }

  // 检查分级ID重复
  const gradeIds = configs.map(c => c.grade_id)
  const duplicateIds = gradeIds.filter((id, index) => gradeIds.indexOf(id) !== index)
  if (duplicateIds.length > 0) {
    result.valid = false
    result.errors.push(`分级ID重复: ${[...new Set(duplicateIds)].join(', ')}`)
  }

  // 检查重量阈值递增
  const sortedByThreshold = [...configs].sort((a, b) => a.weight_threshold - b.weight_threshold)
  for (let i = 1; i < sortedByThreshold.length; i++) {
    if (sortedByThreshold[i].weight_threshold <= sortedByThreshold[i-1].weight_threshold) {
      result.valid = false
      result.errors.push(`重量阈值必须严格递增: ${sortedByThreshold[i-1].weight_threshold}g >= ${sortedByThreshold[i].weight_threshold}g`)
    }
  }

  // 检查通道冲突
  const enabledConfigs = configs.filter(c => c.enabled)
  const channelGroups = enabledConfigs.reduce((groups, config) => {
    if (!groups[config.kick_channel]) {
      groups[config.kick_channel] = []
    }
    groups[config.kick_channel].push(config.grade_id)
    return groups
  }, {} as Record<number, number[]>)

  Object.entries(channelGroups).forEach(([channel, gradeIds]) => {
    if (gradeIds.length > 1) {
      result.warnings.push(`通道 ${channel} 被多个分级使用: ${gradeIds.join(', ')}`)
    }
  })

  // 检查有效范围
  configs.forEach((config, index) => {
    if (config.grade_id < 1 || config.grade_id > 10) {
      result.errors.push(`第${index + 1}项: 分级ID必须在1-10之间`)
      result.valid = false
    }

    if (config.weight_threshold <= 0) {
      result.errors.push(`第${index + 1}项: 重量阈值必须大于0`)
      result.valid = false
    }

    if (config.kick_channel < 1 || config.kick_channel > 20) {
      result.errors.push(`第${index + 1}项: 踢出通道必须在1-20之间`)
      result.valid = false
    }
  })

  return result
}

// 验证重量值
export const validateWeight = (weight: number): boolean => {
  return typeof weight === 'number' && !isNaN(weight) && weight >= 0 && weight <= 10000
}

// 验证日期范围
export const validateDateRange = (startDate: string, endDate: string): boolean => {
  try {
    const start = new Date(startDate)
    const end = new Date(endDate)
    return start <= end && start <= new Date()
  } catch {
    return false
  }
}
