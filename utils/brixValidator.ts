// src/utils/brixValidator.ts
import type { BrixConfig } from '@/types/brix'

// 配置验证结果接口
export interface BrixValidationResult {
  valid: boolean
  errors: string[]
  warnings: string[]
}

// 验证糖度配置
export const validateBrixConfigs = (configs: BrixConfig[]): BrixValidationResult => {
  const result: BrixValidationResult = {
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

  // 检查糖度范围重叠
  const sortedByMin = [...configs].sort((a, b) => a.brix_min - b.brix_min)
  for (let i = 0; i < sortedByMin.length - 1; i++) {
    const current = sortedByMin[i]
    const next = sortedByMin[i + 1]

    if (current.brix_max >= next.brix_min) {
      result.valid = false
      result.errors.push(`糖度范围重叠: 分级${current.grade_id}(${current.brix_min}-${current.brix_max}°Bx) 与 分级${next.grade_id}(${next.brix_min}-${next.brix_max}°Bx)`)
    }
  }

  // 检查糖度范围间隙
  for (let i = 0; i < sortedByMin.length - 1; i++) {
    const current = sortedByMin[i]
    const next = sortedByMin[i + 1]

    if (current.brix_max + 0.1 < next.brix_min) {
      result.warnings.push(`糖度范围存在间隙: ${current.brix_max}°Bx 到 ${next.brix_min}°Bx`)
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

    if (config.brix_min < 0) {
      result.errors.push(`第${index + 1}项: 最小糖度值不能小于0`)
      result.valid = false
    }

    if (config.brix_max > 30) {
      result.warnings.push(`第${index + 1}项: 最大糖度值${config.brix_max}°Bx较高，请确认是否正确`)
    }

    if (config.brix_min >= config.brix_max) {
      result.errors.push(`第${index + 1}项: 最小糖度值必须小于最大糖度值`)
      result.valid = false
    }

    if (config.kick_channel < 1 || config.kick_channel > 20) {
      result.errors.push(`第${index + 1}项: 踢出通道必须在1-20之间`)
      result.valid = false
    }

    if (config.target_weight_ratio && (config.target_weight_ratio < 0 || config.target_weight_ratio > 1)) {
      result.errors.push(`第${index + 1}项: 目标重量比例必须在0-1之间`)
      result.valid = false
    }
  })

  // 检查目标重量比例总和
  const totalRatio = configs
    .filter(c => c.enabled && c.target_weight_ratio)
    .reduce((sum, c) => sum + (c.target_weight_ratio || 0), 0)

  if (totalRatio > 1.01) {
    result.warnings.push(`所有分级的目标重量比例总和为${totalRatio.toFixed(2)}，超过1.0`)
  } else if (totalRatio < 0.99 && totalRatio > 0) {
    result.warnings.push(`所有分级的目标重量比例总和为${totalRatio.toFixed(2)}，小于1.0`)
  }

  return result
}

// 验证糖度值
export const validateBrix = (brix: number): boolean => {
  return typeof brix === 'number' && !isNaN(brix) && brix >= 0 && brix <= 30
}

// 验证温度值
export const validateTemperature = (temperature: number): boolean => {
  return typeof temperature === 'number' && !isNaN(temperature) && temperature >= -10 && temperature <= 50
}

// 验证糖度范围
export const validateBrixRange = (min: number, max: number): boolean => {
  return validateBrix(min) && validateBrix(max) && min < max
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

// 格式化糖度值显示
export const formatBrix = (brix: number): string => {
  return `${brix.toFixed(1)}°Bx`
}

// 格式化温度值显示
export const formatTemperature = (temperature: number): string => {
  return `${temperature.toFixed(1)}°C`
}

// 根据糖度值获取对应的分级
export const getBrixGrade = (brix: number, configs: BrixConfig[]): BrixConfig | null => {
  return configs.find(config =>
    config.enabled &&
    brix >= config.brix_min &&
    brix <= config.brix_max
  ) || null
}

// 计算糖度分布覆盖率
export const calculateBrixCoverage = (configs: BrixConfig[]): {
  totalRange: [number, number]
  coveredRanges: Array<[number, number]>
  coveragePercent: number
  gaps: Array<[number, number]>
} => {
  const enabledConfigs = configs.filter(c => c.enabled)
  if (enabledConfigs.length === 0) {
    return {
      totalRange: [0, 25],
      coveredRanges: [],
      coveragePercent: 0,
      gaps: [[0, 25]]
    }
  }

  const sortedConfigs = [...enabledConfigs].sort((a, b) => a.brix_min - b.brix_min)
  const totalMin = Math.min(...sortedConfigs.map(c => c.brix_min))
  const totalMax = Math.max(...sortedConfigs.map(c => c.brix_max))
  const totalRange: [number, number] = [totalMin, totalMax]

  const coveredRanges: Array<[number, number]> = sortedConfigs.map(c => [c.brix_min, c.brix_max])

  // 计算间隙
  const gaps: Array<[number, number]> = []
  for (let i = 0; i < sortedConfigs.length - 1; i++) {
    const current = sortedConfigs[i]
    const next = sortedConfigs[i + 1]
    if (current.brix_max < next.brix_min) {
      gaps.push([current.brix_max, next.brix_min])
    }
  }

  // 计算覆盖率
  const coveredLength = sortedConfigs.reduce((sum, config) => sum + (config.brix_max - config.brix_min), 0)
  const gapLength = gaps.reduce((sum, gap) => sum + (gap[1] - gap[0]), 0)
  const coveragePercent = coveredLength / (totalMax - totalMin + gapLength)

  return {
    totalRange,
    coveredRanges,
    coveragePercent,
    gaps
  }
}