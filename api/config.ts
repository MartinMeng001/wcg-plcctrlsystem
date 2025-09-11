// src/api/config.ts
import api from './index'
import type {
  ConfigBaseSettings,
  Template,
  ConfigXMLData,
  ConfigValidationResult,
  ConfigBackupResult,
  ConfigReloadResult,
  SystemOverview,
  ConfigApiResponse
} from '@/types/config'

export const configAPI = {
  // 1. 基础配置管理

  /**
   * 获取完整的XML配置文件内容
   * @returns Promise<ConfigApiResponse<ConfigXMLData>>
   */
  getFullConfig: (): Promise<ConfigApiResponse<ConfigXMLData>> =>
    api.get('/config/xml'),

  /**
   * 更新基础配置项（当前模板ID、偏移量等）
   * @param config 基础配置对象
   * @returns Promise<ConfigApiResponse<ConfigBaseSettings>>
   */
  updateBaseConfig: (config: Partial<ConfigBaseSettings>): Promise<ConfigApiResponse<ConfigBaseSettings>> =>
    api.post('/config/xml/base', config),

  // 2. 模板管理

  /**
   * 获取所有可用的检测模板
   * @returns Promise<ConfigApiResponse<{current_template_id: string, templates: Template[]}>>
   */
  getTemplates: (): Promise<ConfigApiResponse<{
    current_template_id: string
    templates: Template[]
  }>> =>
    api.get('/config/xml/templates'),

  /**
   * 更新指定模板的配置
   * @param templateId 模板ID
   * @param templateConfig 模板配置
   * @returns Promise<ConfigApiResponse<{template_id: string, updated_at: string}>>
   */
  updateTemplate: (templateId: string, templateConfig: Partial<Template>): Promise<ConfigApiResponse<{
    template_id: string
    updated_at: string
  }>> =>
    api.post(`/config/xml/templates/${templateId}`, templateConfig),

  // 3. 配置操作

  /**
   * 重新从文件加载配置
   * @returns Promise<ConfigApiResponse<ConfigReloadResult>>
   */
  reloadConfig: (): Promise<ConfigApiResponse<ConfigReloadResult>> =>
    api.post('/config/xml/reload'),

  /**
   * 创建当前配置文件的备份
   * @returns Promise<ConfigApiResponse<ConfigBackupResult>>
   */
  createBackup: (): Promise<ConfigApiResponse<ConfigBackupResult>> =>
    api.post('/config/xml/backup'),

  /**
   * 验证XML配置内容的格式正确性
   * @param xmlContent 要验证的XML内容
   * @returns Promise<ConfigApiResponse<ConfigValidationResult>>
   */
  validateXML: (xmlContent: string): Promise<ConfigApiResponse<ConfigValidationResult>> =>
    api.post('/config/xml/validate', { xml_content: xmlContent }),

  // 4. 增强系统状态

  /**
   * 获取包含配置状态的系统整体概览
   * @returns Promise<ConfigApiResponse<SystemOverview>>
   */
  getSystemOverview: (): Promise<ConfigApiResponse<SystemOverview>> =>
    api.get('/system/overview'),

  // 5. 便捷方法

  /**
   * 安全的模板切换（备份 → 切换 → 重新加载）
   * @param templateId 新的模板ID
   * @param options 可选的偏移量设置
   * @returns Promise<{success: boolean, message: string, backup_path?: string}>
   */
  safeTemplateSwitch: async (
    templateId: string,
    options?: {
      weight_offset?: number
      water_offset?: number
    }
  ): Promise<{
    success: boolean
    message: string
    backup_path?: string
  }> => {
    try {
      // 1. 创建备份
      const backupResult = await configAPI.createBackup()
      if (!backupResult.success) {
        return {
          success: false,
          message: `备份失败: ${backupResult.message}`
        }
      }

      // 2. 切换模板
      const switchData: Partial<ConfigBaseSettings> = {
        current_template_id: templateId
      }

      if (options?.weight_offset !== undefined) {
        switchData.weight_offset = options.weight_offset
      }
      if (options?.water_offset !== undefined) {
        switchData.water_offset = options.water_offset
      }

      const switchResult = await configAPI.updateBaseConfig(switchData)
      if (!switchResult.success) {
        return {
          success: false,
          message: `切换失败: ${switchResult.message}`,
          backup_path: backupResult.data.backup_path
        }
      }

      // 3. 重新加载配置
      const reloadResult = await configAPI.reloadConfig()
      if (!reloadResult.success) {
        return {
          success: false,
          message: `重新加载失败: ${reloadResult.message}`,
          backup_path: backupResult.data.backup_path
        }
      }

      return {
        success: true,
        message: `模板切换成功，已切换到模板${templateId}`,
        backup_path: backupResult.data.backup_path
      }
    } catch (error: any) {
      return {
        success: false,
        message: `模板切换过程中发生错误: ${error.message || '未知错误'}`
      }
    }
  },

  /**
   * 配置更新工作流（备份 → 更新 → 重新加载）
   * @param templateId 模板ID
   * @param templateConfig 新的模板配置
   * @returns Promise<{success: boolean, message: string, backup_path?: string}>
   */
  updateTemplateWorkflow: async (
    templateId: string,
    templateConfig: Partial<Template>
  ): Promise<{
    success: boolean
    message: string
    backup_path?: string
  }> => {
    try {
      // 1. 创建备份
      const backupResult = await configAPI.createBackup()
      if (!backupResult.success) {
        return {
          success: false,
          message: `备份失败: ${backupResult.message}`
        }
      }

      // 2. 更新模板
      const updateResult = await configAPI.updateTemplate(templateId, templateConfig)
      if (!updateResult.success) {
        return {
          success: false,
          message: `模板更新失败: ${updateResult.message}`,
          backup_path: backupResult.data.backup_path
        }
      }

      // 3. 重新加载配置
      const reloadResult = await configAPI.reloadConfig()
      if (!reloadResult.success) {
        return {
          success: false,
          message: `重新加载失败: ${reloadResult.message}`,
          backup_path: backupResult.data.backup_path
        }
      }

      return {
        success: true,
        message: `模板${templateId}更新成功`,
        backup_path: backupResult.data.backup_path
      }
    } catch (error: any) {
      return {
        success: false,
        message: `配置更新过程中发生错误: ${error.message || '未知错误'}`
      }
    }
  }
}