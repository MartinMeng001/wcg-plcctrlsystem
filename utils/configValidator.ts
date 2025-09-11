// src/utils/configValidator.ts
import type {
  Template,
  ConfigBaseSettings,
  ScoreRule,
  LevelConfig,
  DetectorConfig
} from '@/types/config'

export interface ConfigValidationResult {
  valid: boolean
  errors: string[]
  warnings: string[]
}

/**
 * 验证基础配置设置
 */
export const validateBaseConfig = (config: ConfigBaseSettings): ConfigValidationResult => {
  const result: ConfigValidationResult = {
    valid: true,
    errors: [],
    warnings: []
  }

  // 验证模板ID
  if (!config.current_template_id || config.current_template_id.trim() === '') {
    result.valid = false
    result.errors.push('当前模板ID不能为空')
  }

  // 验证偏移量
  if (typeof config.weight_offset !== 'number' || isNaN(config.weight_offset)) {
    result.valid = false
    result.errors.push('重量偏移量必须是有效数字')
  }

  if (typeof config.water_offset !== 'number' || isNaN(config.water_offset)) {
    result.valid = false
    result.errors.push('水分偏移量必须是有效数字')
  }

  // 偏移量范围建议
  if (Math.abs(config.weight_offset) > 100) {
    result.warnings.push(`重量偏移量${config.weight_offset}较大，请确认是否正确`)
  }

  if (Math.abs(config.water_offset) > 50) {
    result.warnings.push(`水分偏移量${config.water_offset}较大，请确认是否正确`)
  }

  return result
}

/**
 * 验证评分规则
 */
export const validateScoreRules = (scoreRules: ScoreRule[]): ConfigValidationResult => {
  const result: ConfigValidationResult = {
    valid: true,
    errors: [],
    warnings: []
  }

  if (scoreRules.length === 0) {
    result.warnings.push('未配置评分规则')
    return result
  }

  // 检查重复的out/subout组合
  const outCombinations = scoreRules.map(rule => `${rule.out}-${rule.subout || ''}`)
  const duplicates = outCombinations.filter((combo, index) => outCombinations.indexOf(combo) !== index)

  if (duplicates.length > 0) {
    result.valid = false
    result.errors.push('存在重复的输出通道组合')
  }

  scoreRules.forEach((rule, index) => {
    // 验证输出通道
    if (!rule.out || rule.out.trim() === '') {
      result.valid = false
      result.errors.push(`第${index + 1}个评分规则: 输出通道不能为空`)
    }

    // 验证分数
    if (typeof rule.score !== 'number' || isNaN(rule.score)) {
      result.valid = false
      result.errors.push(`第${index + 1}个评分规则: 分数必须是有效数字`)
    } else if (rule.score < 0 || rule.score > 100) {
      result.valid = false
      result.errors.push(`第${index + 1}个评分规则: 分数必须在0-100之间`)
    }

    // 警告低分数设置
    if (rule.score < 20) {
      result.warnings.push(`第${index + 1}个评分规则: 分数${rule.score}较低，请确认是否正确`)
    }
  })

  return result
}

/**
 * 验证级别配置（好坏级别）
 */
export const validateLevels = (levels: LevelConfig[], levelType: 'good' | 'bad'): ConfigValidationResult => {
  const result: ConfigValidationResult = {
    valid: true,
    errors: [],
    warnings: []
  }

  levels.forEach((level, index) => {
    const prefix = `${levelType === 'good' ? '良好' : '不良'}级别第${index + 1}项`

    // 验证输出通道
    if (!level.out || level.out.trim() === '') {
      result.valid = false
      result.errors.push(`${prefix}: 输出通道不能为空`)
    }

    // 验证范围
    if (typeof level.min !== 'number' || typeof level.max !== 'number') {
      result.valid = false
      result.errors.push(`${prefix}: 最小值和最大值必须是有效数字`)
    } else if (level.min >= level.max) {
      result.valid = false
      result.errors.push(`${prefix}: 最小值必须小于最大值`)
    }

    // 检查合理性
    if (level.min < -1000 || level.max > 10000) {
      result.warnings.push(`${prefix}: 数值范围可能过大，请确认是否正确`)
    }
  })

  // 检查重叠范围
  for (let i = 0; i < levels.length; i++) {
    for (let j = i + 1; j < levels.length; j++) {
      const level1 = levels[i]
      const level2 = levels[j]

      if (level1.max > level2.min && level1.min < level2.max) {
        result.warnings.push(`${levelType === 'good' ? '良好' : '不良'}级别存在范围重叠: [${level1.min}, ${level1.max}] 与 [${level2.min}, ${level2.max}]`)
      }
    }
  }

  return result
}

/**
 * 验证检测器配置
 */
export const validateDetectorConfig = (detector: DetectorConfig, detectorName: string): ConfigValidationResult => {
  const result: ConfigValidationResult = {
    valid: true,
    errors: [],
    warnings: []
  }

  const prefix = `${detectorName}检测器`

  // 验证权重
  if (!detector.wg || detector.wg.trim() === '') {
    result.valid = false
    result.errors.push(`${prefix}: 权重值不能为空`)
  } else {
    const weight = parseFloat(detector.wg)
    if (isNaN(weight) || weight < 0 || weight > 100) {
      result.valid = false
      result.errors.push(`${prefix}: 权重值必须在0-100之间`)
    }
  }

  // 验证最大值
  if (detector.max !== null && detector.max !== '') {
    const maxValue = parseFloat(detector.max)
    if (isNaN(maxValue) || maxValue <= 0) {
      result.valid = false
      result.errors.push(`${prefix}: 最大值必须是大于0的有效数字`)
    }
  }

  // 验证级别配置
  const badLevelsResult = validateLevels(detector.bad_levels, 'bad')
  const goodLevelsResult = validateLevels(detector.good_levels, 'good')

  result.errors.push(...badLevelsResult.errors, ...goodLevelsResult.errors)
  result.warnings.push(...badLevelsResult.warnings, ...goodLevelsResult.warnings)

  if (!badLevelsResult.valid || !goodLevelsResult.valid) {
    result.valid = false
  }

  // 检查是否至少有一个级别配置
  if (detector.bad_levels.length === 0 && detector.good_levels.length === 0) {
    result.warnings.push(`${prefix}: 没有配置任何检测级别`)
  }

  return result
}

/**
 * 验证完整模板配置
 */
export const validateTemplate = (template: Template): ConfigValidationResult => {
  const result: ConfigValidationResult = {
    valid: true,
    errors: [],
    warnings: []
  }

  // 验证基础信息
  if (!template.id || template.id.trim() === '') {
    result.valid = false
    result.errors.push('模板ID不能为空')
  }

  if (!template.name || template.name.trim() === '') {
    result.valid = false
    result.errors.push('模板名称不能为空')
  }

  // 验证评分配置
  if (template.scores.enabled && template.scores.score_rules) {
    const scoresResult = validateScoreRules(template.scores.score_rules)
    result.errors.push(...scoresResult.errors)
    result.warnings.push(...scoresResult.warnings)
    if (!scoresResult.valid) result.valid = false
  }

  // 验证检测器配置
  Object.entries(template.detectors).forEach(([detectorName, detectorConfig]) => {
    const detectorResult = validateDetectorConfig(detectorConfig, detectorName)
    result.errors.push(...detectorResult.errors)
    result.warnings.push(...detectorResult.warnings)
    if (!detectorResult.valid) result.valid = false
  })

  // 验证权重总和
  const totalWeight = Object.values(template.detectors)
    .reduce((sum, detector) => sum + parseFloat(detector.wg || '0'), 0)

  if (totalWeight !== 100) {
    result.warnings.push(`检测器权重总和为${totalWeight}%，建议调整为100%`)
  }

  return result
}

/**
 * 验证多个模板配置
 */
export const validateTemplates = (templates: Template[]): ConfigValidationResult => {
  const result: ConfigValidationResult = {
    valid: true,
    errors: [],
    warnings: []
  }

  if (templates.length === 0) {
    result.valid = false
    result.errors.push('至少需要一个模板')
    return result
  }

  // 检查模板ID重复
  const templateIds = templates.map(t => t.id)
  const duplicateIds = templateIds.filter((id, index) => templateIds.indexOf(id) !== index)

  if (duplicateIds.length > 0) {
    result.valid = false
    result.errors.push(`模板ID重复: ${[...new Set(duplicateIds)].join(', ')}`)
  }

  // 检查模板名称重复
  const templateNames = templates.map(t => t.name).filter(name => name && name.trim())
  const duplicateNames = templateNames.filter((name, index) => templateNames.indexOf(name) !== index)

  if (duplicateNames.length > 0) {
    result.warnings.push(`模板名称重复: ${[...new Set(duplicateNames)].join(', ')}`)
  }

  // 验证每个模板
  templates.forEach((template, index) => {
    const templateResult = validateTemplate(template)

    // 为错误和警告添加模板标识
    templateResult.errors.forEach(error => {
      result.errors.push(`模板${template.id || index + 1}: ${error}`)
    })

    templateResult.warnings.forEach(warning => {
      result.warnings.push(`模板${template.id || index + 1}: ${warning}`)
    })

    if (!templateResult.valid) result.valid = false
  })

  return result
}

/**
 * 验证XML内容格式
 */
export const validateXMLFormat = (xmlContent: string): ConfigValidationResult => {
  const result: ConfigValidationResult = {
    valid: true,
    errors: [],
    warnings: []
  }

  if (!xmlContent || xmlContent.trim() === '') {
    result.valid = false
    result.errors.push('XML内容不能为空')
    return result
  }

  // 基础XML格式检查
  try {
    // 简单的XML标签匹配检查
    const openTags = xmlContent.match(/<[^/][^>]*>/g) || []
    const closeTags = xmlContent.match(/<\/[^>]+>/g) || []

    if (openTags.length !== closeTags.length) {
      result.warnings.push('XML标签可能不匹配')
    }

    // 检查必要的XML声明
    if (!xmlContent.includes('<?xml')) {
      result.warnings.push('建议添加XML声明')
    }

    // 检查必要的根节点
    if (!xmlContent.includes('<s>') || !xmlContent.includes('</s>')) {
      result.valid = false
      result.errors.push('缺少根节点<s>')
    }

    // 检查必要的config节点
    if (!xmlContent.includes('<config>')) {
      result.valid = false
      result.errors.push('缺少config节点')
    }

    // 检查必要的templates节点
    if (!xmlContent.includes('<templates>')) {
      result.valid = false
      result.errors.push('缺少templates节点')
    }

  } catch (error) {
    result.valid = false
    result.errors.push(`XML解析错误: ${error instanceof Error ? error.message : '未知错误'}`)
  }

  return result
}

/**
 * 验证配置完整性（模板ID引用等）
 */
export const validateConfigIntegrity = (
  baseConfig: ConfigBaseSettings,
  templates: Template[]
): ConfigValidationResult => {
  const result: ConfigValidationResult = {
    valid: true,
    errors: [],
    warnings: []
  }

  // 检查当前模板ID是否存在
  const currentTemplateExists = templates.some(t => t.id === baseConfig.current_template_id)
  if (!currentTemplateExists) {
    result.valid = false
    result.errors.push(`当前模板ID "${baseConfig.current_template_id}" 在模板列表中不存在`)
  }

  // 检查是否有启用的模板
  const hasEnabledTemplate = templates.some(t =>
    t.scores.enabled ||
    Object.values(t.detectors).some(d => parseFloat(d.wg || '0') > 0)
  )

  if (!hasEnabledTemplate) {
    result.warnings.push('所有模板都未启用，系统可能无法正常工作')
  }

  return result
}

/**
 * 生成配置摘要信息
 */
export const generateConfigSummary = (
  baseConfig: ConfigBaseSettings,
  templates: Template[]
) => {
  const currentTemplate = templates.find(t => t.id === baseConfig.current_template_id)

  return {
    currentTemplate: currentTemplate?.name || '未知模板',
    totalTemplates: templates.length,
    enabledTemplates: templates.filter(t =>
      t.scores.enabled ||
      Object.values(t.detectors).some(d => parseFloat(d.wg || '0') > 0)
    ).length,
    scoreEnabled: currentTemplate?.scores.enabled || false,
    scoreRulesCount: currentTemplate?.scores.score_rules?.length || 0,
    detectorsCount: Object.keys(currentTemplate?.detectors || {}).length,
    weightOffset: baseConfig.weight_offset,
    waterOffset: baseConfig.water_offset
  }
}

/**
 * 检查配置变更的影响
 */
export const assessConfigChangeImpact = (
  oldConfig: ConfigBaseSettings,
  newConfig: Partial<ConfigBaseSettings>,
  templates: Template[]
): {
  impact: 'low' | 'medium' | 'high'
  changes: string[]
  recommendations: string[]
} => {
  const changes: string[] = []
  const recommendations: string[] = []
  let impact: 'low' | 'medium' | 'high' = 'low'

  // 检查模板切换
  if (newConfig.current_template_id && newConfig.current_template_id !== oldConfig.current_template_id) {
    const oldTemplate = templates.find(t => t.id === oldConfig.current_template_id)
    const newTemplate = templates.find(t => t.id === newConfig.current_template_id)

    changes.push(`模板切换: ${oldTemplate?.name || oldConfig.current_template_id} → ${newTemplate?.name || newConfig.current_template_id}`)
    impact = 'high'
    recommendations.push('模板切换会影响检测行为，建议先备份配置')
  }

  // 检查偏移量变更
  if (newConfig.weight_offset !== undefined && newConfig.weight_offset !== oldConfig.weight_offset) {
    const diff = newConfig.weight_offset - oldConfig.weight_offset
    changes.push(`重量偏移量变更: ${oldConfig.weight_offset} → ${newConfig.weight_offset} (${diff > 0 ? '+' : ''}${diff})`)

    if (Math.abs(diff) > 10) {
      impact = impact === 'high' ? 'high' : 'medium'
      recommendations.push('重量偏移量变更较大，可能影响检测精度')
    }
  }

  if (newConfig.water_offset !== undefined && newConfig.water_offset !== oldConfig.water_offset) {
    const diff = newConfig.water_offset - oldConfig.water_offset
    changes.push(`水分偏移量变更: ${oldConfig.water_offset} → ${newConfig.water_offset} (${diff > 0 ? '+' : ''}${diff})`)

    if (Math.abs(diff) > 5) {
      impact = impact === 'high' ? 'high' : 'medium'
      recommendations.push('水分偏移量变更较大，可能影响检测精度')
    }
  }

  return { impact, changes, recommendations }
}