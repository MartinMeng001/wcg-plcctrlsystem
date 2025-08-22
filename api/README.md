# Weight Detection System API 文档

## 概述

Weight Detection System API 提供了完整的重量检测系统管理接口，支持配置管理、实时监控、历史数据查询等功能。

**Base URL**: `http://localhost:5000`  
**API版本**: v1.0  
**内容类型**: `application/json`

## 通用响应格式

所有API响应都采用统一的JSON格式：

```json
{
    "success": true,           // 请求是否成功
    "message": "操作成功",      // 响应消息
    "data": { ... },          // 响应数据
    "timestamp": "2024-01-15T10:30:00Z"  // 响应时间戳（可选）
}
```

### HTTP状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 1. 系统健康检查

### GET /health

检查API服务器健康状态

#### 请求
无需参数

#### 响应示例
```json
{
    "status": "healthy",
    "timestamp": "2024-01-15T10:30:00Z",
    "version": "1.0.0"
}
```

---

## 2. 重量检测配置管理

### GET /api/weight/config

获取当前重量分级配置

#### 请求
无需参数

#### 响应示例
```json
{
    "success": true,
    "message": "获取配置成功",
    "data": {
        "version": 3,
        "created_at": "2024-01-15T08:00:00Z",
        "updated_at": "2024-01-15T10:00:00Z",
        "configs": [
            {
                "grade_id": 1,
                "weight_threshold": 50.0,
                "kick_channel": 1,
                "enabled": true,
                "description": "轻量级果子"
            },
            {
                "grade_id": 2,
                "weight_threshold": 100.0,
                "kick_channel": 2,
                "enabled": true,
                "description": "中量级果子"
            },
            {
                "grade_id": 3,
                "weight_threshold": 150.0,
                "kick_channel": 3,
                "enabled": true,
                "description": "重量级果子"
            }
        ]
    }
}
```

#### 错误响应
```json
{
    "success": false,
    "message": "未找到配置",
    "data": null
}
```

### POST /api/weight/config

更新重量分级配置

#### 请求体
```json
{
    "configs": [
        {
            "grade_id": 1,
            "weight_threshold": 50.0,
            "kick_channel": 1,
            "enabled": true,
            "description": "轻量级果子"
        },
        {
            "grade_id": 2,
            "weight_threshold": 100.0,
            "kick_channel": 2,
            "enabled": true,
            "description": "中量级果子"
        }
    ]
}
```

#### 请求参数说明
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| grade_id | integer | 是 | 分级ID (1-10) |
| weight_threshold | number | 是 | 重量阈值(克) |
| kick_channel | integer | 是 | 踢出通道编号 |
| enabled | boolean | 否 | 是否启用，默认true |
| description | string | 否 | 描述信息 |

#### 成功响应
```json
{
    "success": true,
    "message": "配置更新成功",
    "data": {
        "version": 4
    }
}
```

#### 错误响应
```json
{
    "success": false,
    "message": "重量阈值必须严格递增，第2项配置有误",
    "data": null
}
```

### POST /api/weight/config/validate

验证重量配置（不保存）

#### 请求体
与 `POST /api/weight/config` 相同

#### 响应示例
```json
{
    "success": true,
    "message": "配置验证通过",
    "data": {
        "valid": true
    }
}
```

---

## 3. 检测记录查询

### GET /api/weight/records

获取重量检测记录

#### 请求参数
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| limit | integer | 否 | 100 | 记录数量限制(1-1000) |

#### 请求示例
```
GET /api/weight/records?limit=50
```

#### 响应示例
```json
{
    "success": true,
    "message": "获取到50条记录",
    "data": {
        "records": [
            {
                "id": 1001,
                "timestamp": "2024-01-15T10:30:15Z",
                "weight": 75.5,
                "determined_grade": 2,
                "kick_channel": 2,
                "detection_success": true
            },
            {
                "id": 1002,
                "timestamp": "2024-01-15T10:30:20Z",
                "weight": 45.2,
                "determined_grade": 1,
                "kick_channel": 1,
                "detection_success": true
            }
        ],
        "total": 50
    }
}
```

---

## 4. 统计数据查询

### GET /api/weight/statistics

获取重量检测统计数据

#### 请求参数
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| date | string | 否 | 今天 | 日期(YYYY-MM-DD格式) |

#### 请求示例
```
GET /api/weight/statistics?date=2024-01-15
```

#### 响应示例
```json
{
    "success": true,
    "message": "获取2024-01-15统计数据成功",
    "data": {
        "date": "2024-01-15",
        "statistics": [
            {
                "grade_id": 1,
                "total_count": 150,
                "weight_sum": 7500.0,
                "weight_avg": 50.0
            },
            {
                "grade_id": 2,
                "total_count": 200,
                "weight_sum": 15000.0,
                "weight_avg": 75.0
            },
            {
                "grade_id": 3,
                "total_count": 100,
                "weight_sum": 12000.0,
                "weight_avg": 120.0
            }
        ],
        "summary": {
            "total_count": 450,
            "total_weight": 34500.0
        }
    }
}
```

---

## 5. 系统状态监控

### GET /api/weight/status

获取重量检测服务状态

#### 响应示例
```json
{
    "success": true,
    "message": "获取状态成功",
    "data": {
        "status": "active",
        "recent_records_count": 100,
        "last_detection_time": "2024-01-15T10:30:15Z",
        "config_info": {
            "total_grades": 5,
            "enabled_grades": 4,
            "version": 3,
            "updated_at": "2024-01-15T10:00:00Z"
        },
        "performance": {
            "detection_count": 1500,
            "avg_detection_time": 0.003,
            "queue_overflow_count": 0,
            "last_detection_time": 0.002,
            "record_queue_size": 5,
            "statistics_queue_size": 2,
            "recent_records_count": 100,
            "background_threads_running": true
        }
    }
}
```

### GET /api/weight/realtime

获取实时数据快照

#### 响应示例
```json
{
    "success": true,
    "message": "获取实时数据成功",
    "data": {
        "timestamp": "2024-01-15T10:30:15Z",
        "latest_records": [
            {
                "timestamp": "2024-01-15T10:30:15Z",
                "weight": 75.5,
                "grade": 2,
                "channel": 2
            },
            {
                "timestamp": "2024-01-15T10:30:10Z",
                "weight": 45.2,
                "grade": 1,
                "channel": 1
            }
        ],
        "today_summary": {
            "total_count": 450,
            "by_grade": {
                "1": {
                    "count": 150,
                    "avg_weight": 50.0
                },
                "2": {
                    "count": 200,
                    "avg_weight": 75.0
                },
                "3": {
                    "count": 100,
                    "avg_weight": 120.0
                }
            }
        },
        "service_status": {
            "status": "active",
            "recent_records_count": 100
        }
    }
}
```

---

## 6. 错误响应

### 参数错误 (400)
```json
{
    "success": false,
    "message": "请求参数错误：缺少configs字段",
    "data": null
}
```

### 资源不存在 (404)
```json
{
    "success": false,
    "message": "未找到配置",
    "data": null
}
```

### 服务器错误 (500)
```json
{
    "success": false,
    "message": "获取配置失败: 数据库连接异常",
    "data": null
}
```

---

## 7. 数据模型

### WeightGradeConfig
重量分级配置模型

| 字段 | 类型 | 说明 |
|------|------|------|
| grade_id | integer | 分级ID (1-10) |
| weight_threshold | number | 重量阈值(克) |
| kick_channel | integer | 踢出通道编号 |
| enabled | boolean | 是否启用 |
| description | string | 描述信息 |

### WeightDetectionRecord
重量检测记录模型

| 字段 | 类型 | 说明 |
|------|------|------|
| id | integer | 记录ID |
| timestamp | string | 检测时间(ISO 8601格式) |
| weight | number | 检测重量(克) |
| determined_grade | integer | 判定的分级 |
| kick_channel | integer | 踢出通道 |
| detection_success | boolean | 检测是否成功 |

### WeightStatistics
重量统计数据模型

| 字段 | 类型 | 说明 |
|------|------|------|
| date | string | 统计日期(YYYY-MM-DD) |
| grade_id | integer | 分级ID |
| total_count | integer | 总数量 |
| weight_sum | number | 重量总和(克) |
| weight_avg | number | 平均重量(克) |

---

## 8. 使用示例

### JavaScript/Fetch API

#### 获取配置
```javascript
const response = await fetch('/api/weight/config');
const result = await response.json();

if (result.success) {
    console.log('配置信息:', result.data);
} else {
    console.error('获取配置失败:', result.message);
}
```

#### 更新配置
```javascript
const newConfig = {
    configs: [
        {
            grade_id: 1,
            weight_threshold: 50.0,
            kick_channel: 1,
            enabled: true,
            description: "轻量级"
        }
    ]
};

const response = await fetch('/api/weight/config', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify(newConfig)
});

const result = await response.json();
console.log('更新结果:', result);
```

#### 获取实时数据
```javascript
const fetchRealtimeData = async () => {
    try {
        const response = await fetch('/api/weight/realtime');
        const result = await response.json();
        
        if (result.success) {
            return result.data;
        } else {
            throw new Error(result.message);
        }
    } catch (error) {
        console.error('获取实时数据失败:', error);
        return null;
    }
};

// 定期获取实时数据
setInterval(async () => {
    const data = await fetchRealtimeData();
    if (data) {
        updateDashboard(data);
    }
}, 1000); // 每秒更新一次
```

### Python/requests

```python
import requests
import json

# API基础URL
BASE_URL = 'http://localhost:5000'

class WeightAPI:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
    
    def get_config(self):
        """获取配置"""
        response = requests.get(f'{self.base_url}/api/weight/config')
        return response.json()
    
    def update_config(self, configs):
        """更新配置"""
        data = {'configs': configs}
        response = requests.post(
            f'{self.base_url}/api/weight/config',
            json=data,
            headers={'Content-Type': 'application/json'}
        )
        return response.json()
    
    def get_records(self, limit=100):
        """获取记录"""
        response = requests.get(
            f'{self.base_url}/api/weight/records',
            params={'limit': limit}
        )
        return response.json()
    
    def get_statistics(self, date=None):
        """获取统计数据"""
        params = {'date': date} if date else {}
        response = requests.get(
            f'{self.base_url}/api/weight/statistics',
            params=params
        )
        return response.json()

# 使用示例
api = WeightAPI()

# 获取配置
config = api.get_config()
print(f"当前配置版本: {config['data']['version']}")

# 获取今日统计
stats = api.get_statistics()
print(f"今日总检测数: {stats['data']['summary']['total_count']}")
```

---

## 9. 部署说明

### 集成模式启动
```bash
# 启动主程序（包含API服务器）
python main.py

# API服务器将在 http://localhost:5000 启动
```

### 独立模式启动
```bash
# 启动检测主程序
python main.py

# 在另一个终端启动API服务器
python -m api.server --host 0.0.0.0 --port 5000
```

### 环境要求
- Python 3.7+
- Flask 2.0+
- flask-cors 3.0+
- pymodbus 3.0+

### 配置CORS
API服务器默认配置了CORS支持，允许以下前端地址访问：
- http://localhost:3000 (React开发服务器)
- http://localhost:8080 (Vue.js开发服务器)

如需支持其他地址，请修改 `api/app.py` 中的CORS配置。

---

## 10. 常见问题

### Q: API响应时间慢？
A: 检查数据库连接和查询优化，考虑使用集成模式以减少数据库查询。

### Q: 实时数据不更新？
A: 确保使用集成模式，独立模式无法获取内存中的实时数据。

### Q: 配置更新失败？
A: 检查配置格式是否正确，重量阈值必须严格递增，启用的配置通道不能重复。

### Q: CORS错误？
A: 确认前端地址是否在CORS允许列表中，或在开发环境中禁用浏览器安全策略。

---

## 11. 版本信息

**当前版本**: v1.0.0  
**最后更新**: 2024-01-15  
**维护状态**: 活跃开发中

如有问题或建议，请联系开发团队。