// src/utils/format.ts
// 格式化工具函数

// 格式化重量显示
export const formatWeight = (weight: number): string => {
  if (typeof weight !== 'number' || isNaN(weight)) {
    return '0.0g'
  }
  return `${weight.toFixed(1)}g`
}

// 格式化时间显示
export const formatTime = (timestamp: string): string => {
  try {
    return new Date(timestamp).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch (error) {
    return '无效时间'
  }
}

// 格式化数字
export const formatNumber = (num: number): string => {
  if (typeof num !== 'number' || isNaN(num)) {
    return '0'
  }
  return num.toLocaleString()
}

// 格式化文件大小
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'

  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 格式化百分比
export const formatPercentage = (value: number, total: number): string => {
  if (total === 0) return '0%'
  return `${Math.round((value / total) * 100)}%`
}

// 格式化持续时间
export const formatDuration = (milliseconds: number): string => {
  const seconds = Math.floor(milliseconds / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)

  if (hours > 0) {
    return `${hours}小时${minutes % 60}分钟`
  } else if (minutes > 0) {
    return `${minutes}分钟${seconds % 60}秒`
  } else {
    return `${seconds}秒`
  }
}

// 格式化相对时间
export const formatRelativeTime = (timestamp: string): string => {
  try {
    const now = new Date()
    const time = new Date(timestamp)
    const diffMs = now.getTime() - time.getTime()

    if (diffMs < 60000) { // 1分钟内
      return '刚刚'
    } else if (diffMs < 3600000) { // 1小时内
      return `${Math.floor(diffMs / 60000)}分钟前`
    } else if (diffMs < 86400000) { // 1天内
      return `${Math.floor(diffMs / 3600000)}小时前`
    } else {
      return formatTime(timestamp)
    }
  } catch (error) {
    return '未知时间'
  }
}