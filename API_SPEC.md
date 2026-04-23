# Athena SQL 查询后端 API 接口规范

## 概述

本文档定义了前端 Athena SQL 查询组件所需的后端 API 接口规范。后端需要实现以下接口以支持多环境 Athena 查询功能。

---

## 通用响应格式

所有 API 响应应遵循以下统一格式：

### 成功响应
```json
{
  "status": "success",
  "data": { ... }
}
```

### 错误响应
```json
{
  "status": "error",
  "message": "错误信息描述",
  "detail": "详细错误信息（可选，用于调试）"
}
```

---

## API 接口列表

### 1. 获取环境列表

用于初始化页面时获取所有可用的 AWS 环境。

**请求信息：**
- 方法: `GET`
- 路径: `/api/aws/athena/environments`
- 认证: 需要登录认证

**请求参数：**
无

**响应示例：**
```json
{
  "status": "success",
  "data": [
    {
      "id": "prod",
      "name": "生产环境",
      "is_default": true,
      "region": "us-east-1",
      "account_id": "123456789012"
    },
    {
      "id": "staging",
      "name": "预发布环境",
      "is_default": false,
      "region": "us-west-2",
      "account_id": "987654321098"
    },
    {
      "id": "test",
      "name": "测试环境",
      "is_default": false,
      "region": "eu-west-1",
      "account_id": "111222333444"
    }
  ]
}
```

**响应字段说明：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 环境唯一标识符 |
| name | string | 是 | 环境显示名称 |
| is_default | boolean | 是 | 是否为默认环境 |
| region | string | 否 | AWS 区域 |
| account_id | string | 否 | AWS 账号 ID |


---

### 2. 获取数据库列表

获取指定环境下的所有 Athena 数据库。

**请求信息：**
- 方法: `GET`
- 路径: `/api/aws/athena/databases`
- 认证: 需要登录认证

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| env | string | 是 | 环境 ID（来自环境列表接口） |

**请求示例：**
```
GET /api/aws/athena/databases?env=prod
```

**响应示例：**
```json
{
  "status": "success",
  "data": [
    "default",
    "analytics_db",
    "logs_db",
    "reports_db",
    "metrics_db"
  ]
}
```

**响应字段说明：**
- 返回数据库名称的字符串数组


---

### 3. 获取数据表列表

获取指定数据库下的所有数据表。

**请求信息：**
- 方法: `GET`
- 路径: `/api/aws/athena/tables`
- 认证: 需要登录认证

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| env | string | 是 | 环境 ID |
| database | string | 是 | 数据库名称 |

**请求示例：**
```
GET /api/aws/athena/tables?env=prod&database=analytics_db
```

**响应示例：**
```json
{
  "status": "success",
  "data": [
    "user_events",
    "page_views",
    "clickstream",
    "transactions",
    "session_logs"
  ]
}
```

**响应字段说明：**
- 返回数据表名称的字符串数组

---

### 4. 执行 SQL 查询 (核心接口)

执行 Athena SQL 查询并返回结果。

**请求信息：**
- 方法: `POST`
- 路径: `/api/aws/athena/query`
- 认证: 需要登录认证
- Content-Type: `application/json`

**请求头：**
```
X-CSRFToken: <csrf_token>
```

**请求参数 (JSON Body)：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| environment | string | 是 | 环境 ID |
| database | string | 否 | 默认数据库（SQL 中未指定数据库时使用） |
| sql | string | 是 | 要执行的 SQL 语句 |
| limit | integer | 否 | 限制返回行数，默认 100 |

**请求示例：**
```json
{
  "environment": "prod",
  "database": "analytics_db",
  "sql": "SELECT user_id, event_name, timestamp FROM user_events WHERE date = '2024-01-01' LIMIT 50",
  "limit": 100
}
```

**响应示例 (成功)：**
```json
{
  "status": "success",
  "data": {
    "query_info": {
      "query_id": "12345678-1234-1234-1234-123456789012",
      "status": "SUCCEEDED",
      "data_scanned_bytes": 10485760,
      "execution_time_ms": 2345,
      "output_location": "s3://aws-athena-query-results-123456789012-us-east-1/Unsaved/2024/01/01/...",
      "submission_time": "2024-01-01T12:00:00Z"
    },
    "columns": [
      {
        "name": "user_id",
        "type": "varchar"
      },
      {
        "name": "event_name",
        "type": "varchar"
      },
      {
        "name": "timestamp",
        "type": "timestamp"
      }
    ],
    "data": [
      {
        "user_id": "u123456",
        "event_name": "page_view",
        "timestamp": "2024-01-01T10:30:00Z"
      },
      {
        "user_id": "u789012",
        "event_name": "click",
        "timestamp": "2024-01-01T10:31:00Z"
      }
    ],
    "row_count": 2,
    "execution_time": 2.35
  }
}
```

**响应示例 (错误)：**
```json
{
  "status": "error",
  "message": "SQL 语法错误",
  "detail": "line 1:8: mismatched input 'SELEC' expecting {'SELECT', ...}"
}
```

**响应字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| query_info | object | 查询执行详细信息 |
| query_info.query_id | string | Athena 查询 ID |
| query_info.status | string | 查询状态 (SUCCEEDED/FAILED/CANCELLED) |
| query_info.data_scanned_bytes | integer | 扫描数据量（字节） |
| query_info.execution_time_ms | integer | 执行时间（毫秒） |
| query_info.output_location | string | 结果 S3 位置 |
| query_info.submission_time | string | 提交时间 |
| columns | array | 列定义数组 |
| columns[].name | string | 列名 |
| columns[].type | string | 列数据类型 |
| data | array | 查询结果数据行数组 |
| row_count | integer | 返回行数 |
| execution_time | float | 执行时间（秒，简化显示用） |

---

### 5. 获取查询状态 (可选，用于异步查询)

**请求信息：**
- 方法: `GET`
- 路径: `/api/aws/athena/query_status`
- 认证: 需要登录认证

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| env | string | 是 | 环境 ID |
| query_id | string | 是 | 查询 ID |

**响应示例：**
```json
{
  "status": "success",
  "data": {
    "query_id": "12345678-1234-1234-1234-123456789012",
    "status": "RUNNING",
    "state_change_reason": null,
    "submission_time": "2024-01-01T12:00:00Z",
    "completion_time": null
  }
}
```

---

## 前端调用示例

### JavaScript (Axios)

```javascript
// 获取环境列表
const getEnvironments = async () => {
  const response = await axios.get('/api/aws/athena/environments');
  return response.data.data;
};

// 获取数据库列表
const getDatabases = async (env) => {
  const response = await axios.get(`/api/aws/athena/databases?env=${env}`);
  return response.data.data;
};

// 获取表列表
const getTables = async (env, database) => {
  const response = await axios.get(`/api/aws/athena/tables?env=${env}&database=${database}`);
  return response.data.data;
};

// 执行查询
const executeQuery = async (params) => {
  const csrftoken = document.cookie.match(/csrftoken=([\w-]+)/)?.[1];
  
  const response = await axios.post('/api/aws/athena/query', params, {
    headers: {
      'X-CSRFToken': csrftoken
    }
  });
  
  return response.data;
};
```

---

## 错误码建议

| HTTP 状态码 | 含义 | 场景 |
|-------------|------|------|
| 400 | 错误请求 | SQL 语法错误、参数缺失 |
| 401 | 未授权 | 用户未登录 |
| 403 | 禁止访问 | 无权限访问该环境/数据库 |
| 404 | 未找到 | 环境不存在、数据库不存在 |
| 408 | 请求超时 | 查询执行超时 |
| 429 | 请求过多 | 超过并发限制 |
| 500 | 服务器错误 | AWS 服务错误、内部错误 |


---

---

## 总结

本文档定义了 Athena SQL 查询功能所需的后端 API 接口。核心接口是 `POST /api/aws/athena/query`，用于执行 SQL 查询并返回结果。

