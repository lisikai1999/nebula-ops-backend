# Workflow 工作流后端 API 文档

> 文档版本: v1.0\
> 基础路径: `/api/workflow`\
> 创建日期: 2026-04-24

***

## 目录

1. [通用说明](#一通用说明)
2. [工作流管理 API](#二工作流管理-api)
3. [工作流执行 API](#三工作流执行-api)
4. [数据模型定义](#四数据模型定义)
5. [步骤类型配置](#五步骤类型配置)
6. [注意事项](#六注意事项)

***

## 一、通用说明

### 1.1 认证方式

所有 API 都需要认证 Token，请求头格式如下：

```http
Authorization: Bearer {token}
Content-Type: application/json
```

前端通过 `authStore.getAuthHeaders()` 获取认证头。

### 1.2 响应格式

#### 成功响应

```json
{
  "code": 200,
  "data": { ... }
}
```

#### 错误响应

```json
{
  "code": 400,
  "message": "错误描述信息"
}
```

#### 常见错误码

| 错误码 | 说明       |
| --- | -------- |
| 400 | 请求参数错误   |
| 401 | 未授权，请先登录 |
| 403 | 权限不足     |
| 404 | 资源不存在    |
| 500 | 服务器内部错误  |

***

## 二、工作流管理 API

### 2.1 获取工作流列表

**接口:** `GET /api/workflow/list`

**功能:** 获取当前用户的所有工作流列表

**请求头:**

```http
Authorization: Bearer {token}
```

**响应示例:**

```json
{
  "code": 200,
  "data": [
    {
      "id": "workflow_1713926400000",
      "name": "生产环境部署流水线",
      "description": "自动化部署应用到生产环境",
      "templateId": null,
      "steps": [
        {
          "id": "step_1713926400001",
          "name": "Jenkins构建",
          "actionType": "jenkins_execute",
          "config": {
            "jenkinsUrl": "https://jenkins.example.com",
            "jobName": "app-build",
            "waitForBuild": true
          },
          "dependsOn": [],
          "retryPolicy": {
            "enabled": true,
            "maxRetries": 3,
            "delay": 5000
          },
          "timeout": 300000
        }
      ],
      "variables": {
        "env": "production",
        "version": "v1.0.0"
      },
      "settings": {
        "maxRetries": 3,
        "retryDelay": 1000,
        "timeout": 600000
      },
      "createdAt": "2026-04-24T08:00:00.000Z",
      "updatedAt": "2026-04-24T08:30:00.000Z",
      "version": 1
    }
  ]
}
```

***

### 2.2 获取单个工作流详情

**接口:** `GET /api/workflow/{workflowId}`

**功能:** 根据 ID 获取工作流详细信息

**路径参数:**

| 参数名        | 类型     | 必填 | 说明      |
| ---------- | ------ | -- | ------- |
| workflowId | string | 是  | 工作流唯一标识 |

**请求头:**

```http
Authorization: Bearer {token}
```

**响应示例:** 同上单个工作流对象

***

### 2.3 创建工作流

**接口:** `POST /api/workflow/create`

**功能:** 创建新的工作流

**请求头:**

```http
Authorization: Bearer {token}
Content-Type: application/json
```

**请求体:**

```json
{
  "name": "工作流名称",
  "description": "工作流描述信息",
  "templateId": "template_001",
  "steps": [],
  "variables": {
    "env": "production"
  },
  "settings": {
    "maxRetries": 3,
    "retryDelay": 1000,
    "timeout": 300000
  }
}
```

**请求字段说明:**

| 字段名         | 类型     | 必填 | 默认值  | 说明      |
| ----------- | ------ | -- | ---- | ------- |
| name        | string | 是  | -    | 工作流名称   |
| description | string | 否  | ""   | 工作流描述   |
| templateId  | string | 否  | null | 使用的模板ID |
| steps       | array  | 否  | \[]  | 步骤列表    |
| variables   | object | 否  | {}   | 工作流变量   |
| settings    | object | 否  | 见下   | 全局设置    |

**settings 字段:**

| 字段名        | 类型     | 默认值    | 说明       |
| ---------- | ------ | ------ | -------- |
| maxRetries | number | 3      | 最大重试次数   |
| retryDelay | number | 1000   | 重试间隔(毫秒) |
| timeout    | number | 300000 | 执行超时(毫秒) |

**响应示例:**

```json
{
  "code": 200,
  "data": {
    "id": "workflow_1713926400000",
    "name": "工作流名称",
    "...": "其他字段"
  }
}
```

***

### 2.4 更新工作流

**接口:** `PUT /api/workflow/{workflowId}`

**功能:** 更新工作流信息

**路径参数:**

| 参数名        | 类型     | 必填 | 说明      |
| ---------- | ------ | -- | ------- |
| workflowId | string | 是  | 工作流唯一标识 |

**请求头:**

```http
Authorization: Bearer {token}
Content-Type: application/json
```

**请求体:** 可更新字段 (name, description, steps, variables, settings 等)

```json
{
  "name": "新的工作流名称",
  "description": "更新后的描述",
  "steps": [
    {
      "id": "step_1",
      "name": "步骤名称",
      "actionType": "webhook",
      "config": {},
      "dependsOn": []
    }
  ]
}
```

**响应示例:** 更新后的完整工作流对象

***

### 2.5 删除工作流

**接口:** `DELETE /api/workflow/{workflowId}`

**功能:** 删除指定工作流

**路径参数:**

| 参数名        | 类型     | 必填 | 说明      |
| ---------- | ------ | -- | ------- |
| workflowId | string | 是  | 工作流唯一标识 |

**请求头:**

```http
Authorization: Bearer {token}
```

**响应示例:**

```json
{
  "code": 200,
  "message": "删除成功"
}
```

***

## 三、工作流执行 API

### 3.1 执行工作流

**接口:** `POST /api/workflow/execute`

**功能:** 启动工作流执行

**请求头:**

```http
Authorization: Bearer {token}
Content-Type: application/json
```

**请求体:**

```json
{
  "workflowId": "workflow_1713926400000",
  "variables": {
    "env": "production",
    "version": "v1.0.0"
  },
  "workflowSnapshot": {
    "id": "workflow_1713926400000",
    "name": "部署流水线",
    "steps": [],
    "...": "完整工作流快照"
  }
}
```

**请求字段说明:**

| 字段名              | 类型     | 必填 | 说明                |
| ---------------- | ------ | -- | ----------------- |
| workflowId       | string | 是  | 工作流ID             |
| variables        | object | 否  | 运行时变量，会覆盖工作流定义的变量 |
| workflowSnapshot | object | 是  | 完整的工作流快照，包含所有步骤配置 |

**响应示例:**

```json
{
  "code": 200,
  "data": {
    "executionId": "exec_1713926400000_abcdefg"
  }
}
```

**说明:**

- 后端应创建执行记录，返回执行ID
- 执行应该异步进行，不阻塞接口响应
- 前端会通过轮询接口获取执行状态

***

### 3.2 获取执行状态

**接口:** `GET /api/workflow/execution/{executionId}`

**功能:** 获取执行实例的当前状态（轮询接口）

**路径参数:**

| 参数名         | 类型     | 必填 | 说明     |
| ----------- | ------ | -- | ------ |
| executionId | string | 是  | 执行实例ID |

**请求头:**

```http
Authorization: Bearer {token}
```

**响应示例:**

```json
{
  "code": 200,
  "data": {
    "id": "exec_1713926400000_abcdefg",
    "workflowId": "workflow_1713926400000",
    "status": "running",
    "stepStatuses": {
      "step_1713926400001": {
        "status": "completed",
        "startTime": "2026-04-24T08:00:00.000Z",
        "endTime": "2026-04-24T08:00:30.000Z",
        "retries": 0,
        "error": null
      },
      "step_1713926400002": {
        "status": "running",
        "startTime": "2026-04-24T08:00:30.000Z",
        "endTime": null,
        "retries": 0,
        "error": null
      }
    },
    "stepResults": {
      "step_1713926400001": {
        "buildNumber": 123,
        "buildUrl": "https://jenkins.example.com/job/123",
        "output": "构建成功..."
      }
    },
    "logs": [
      {
        "type": "info",
        "message": "步骤1: Jenkins构建已完成",
        "timestamp": "2026-04-24T08:00:30.000Z",
        "stepId": "step_1713926400001"
      },
      {
        "type": "workflow_started",
        "message": "工作流已提交到后端执行",
        "timestamp": "2026-04-24T08:00:00.000Z",
        "workflowId": "workflow_1713926400000",
        "workflowName": "部署流水线"
      }
    ],
    "startTime": "2026-04-24T08:00:00.000Z",
    "endTime": null,
    "error": null
  }
}
```

**轮询说明:**

- 前端默认每 2 秒轮询一次此接口
- 当状态为 `completed`、`failed` 或 `cancelled` 时，前端停止轮询
- 建议后端控制日志返回量，避免单次返回过多数据

***

### 3.3 获取执行日志

**接口:** `GET /api/workflow/execution/{executionId}/logs`

**功能:** 获取执行实例的完整日志

**路径参数:**

| 参数名         | 类型     | 必填 | 说明     |
| ----------- | ------ | -- | ------ |
| executionId | string | 是  | 执行实例ID |

**请求头:**

```http
Authorization: Bearer {token}
```

**响应示例:**

```json
{
  "code": 200,
  "data": [
    {
      "type": "info",
      "message": "工作流开始执行",
      "timestamp": "2026-04-24T08:00:00.000Z"
    },
    {
      "type": "error",
      "message": "步骤2执行失败: 连接超时",
      "timestamp": "2026-04-24T08:05:00.000Z",
      "stepId": "step_2"
    }
  ]
}
```

***

### 3.4 取消执行

**接口:** `POST /api/workflow/execution/{executionId}/cancel`

**功能:** 取消正在执行的工作流

**路径参数:**

| 参数名         | 类型     | 必填 | 说明     |
| ----------- | ------ | -- | ------ |
| executionId | string | 是  | 执行实例ID |

**请求头:**

```http
Authorization: Bearer {token}
```

**请求体:** 空对象 `{}`

**响应示例:**

```json
{
  "code": 200,
  "data": {
    "status": "cancelled",
    "message": "执行已取消"
  }
}
```

***

### 3.5 暂停执行

**接口:** `POST /api/workflow/execution/{executionId}/pause`

**功能:** 暂停正在执行的工作流

**路径参数:**

| 参数名         | 类型     | 必填 | 说明     |
| ----------- | ------ | -- | ------ |
| executionId | string | 是  | 执行实例ID |

**请求头:**

```http
Authorization: Bearer {token}
```

**请求体:** 空对象 `{}`

**响应示例:**

```json
{
  "code": 200,
  "data": {
    "status": "paused",
    "message": "执行已暂停"
  }
}
```

***

### 3.6 恢复执行

**接口:** `POST /api/workflow/execution/{executionId}/resume`

**功能:** 恢复已暂停的工作流

**路径参数:**

| 参数名         | 类型     | 必填 | 说明     |
| ----------- | ------ | -- | ------ |
| executionId | string | 是  | 执行实例ID |

**请求头:**

```http
Authorization: Bearer {token}
```

**请求体:** 空对象 `{}`

**响应示例:**

```json
{
  "code": 200,
  "data": {
    "status": "running",
    "message": "执行已恢复"
  }
}
```

***

### 3.7 获取执行历史

**接口:** `GET /api/workflow/history`

**功能:** 获取执行历史记录

**查询参数 (可选):**

| 参数名        | 类型     | 说明           |
| ---------- | ------ | ------------ |
| workflowId | string | 筛选指定工作流的执行历史 |

**请求头:**

```http
Authorization: Bearer {token}
```

**响应示例:**

```json
{
  "code": 200,
  "data": [
    {
      "id": "exec_1713926400000_abcdefg",
      "workflowId": "workflow_1713926400000",
      "workflowName": "部署流水线",
      "status": "completed",
      "startTime": "2026-04-24T08:00:00.000Z",
      "endTime": "2026-04-24T08:05:00.000Z",
      "savedAt": "2026-04-24T08:05:00.000Z"
    },
    {
      "id": "exec_1713926300000_hijklmn",
      "workflowId": "workflow_1713926400000",
      "workflowName": "部署流水线",
      "status": "failed",
      "startTime": "2026-04-24T07:00:00.000Z",
      "endTime": "2026-04-24T07:03:00.000Z",
      "savedAt": "2026-04-24T07:03:00.000Z"
    }
  ]
}
```

***

## 四、数据模型定义

### 4.1 工作流状态 (WorkflowStatus)

| 值           | 说明     | 前端展示   |
| ----------- | ------ | ------ |
| `idle`      | 空闲/未执行 | 灰色     |
| `running`   | 执行中    | 蓝色(动画) |
| `paused`    | 已暂停    | 黄色     |
| `completed` | 已完成    | 绿色     |
| `failed`    | 执行失败   | 红色     |
| `cancelled` | 已取消    | 灰色     |

### 4.2 步骤状态 (StepStatus)

| 值           | 说明              |
| ----------- | --------------- |
| `pending`   | 等待执行            |
| `running`   | 执行中             |
| `completed` | 已完成             |
| `failed`    | 执行失败            |
| `skipped`   | 已跳过(依赖失败或条件不满足) |

### 4.3 工作流对象 (Workflow)

```typescript
interface Workflow {
  id: string;                    // 工作流唯一标识
  name: string;                  // 工作流名称
  description: string;           // 工作流描述
  templateId: string | null;     // 使用的模板ID
  steps: Step[];                 // 步骤列表
  variables: Record<string, string>;  // 工作流变量
  triggers: any[];               // 触发器配置(预留)
  settings: WorkflowSettings;    // 全局设置
  createdAt: string;             // 创建时间 (ISO 8601)
  updatedAt: string;             // 更新时间 (ISO 8601)
  version: number;               // 版本号
}

interface WorkflowSettings {
  maxRetries: number;    // 最大重试次数
  retryDelay: number;    // 重试间隔(毫秒)
  timeout: number;       // 整体超时(毫秒)
}
```

### 4.4 步骤对象 (Step)

```typescript
interface Step {
  id: string;                    // 步骤唯一标识
  name: string;                  // 步骤名称
  actionType: ActionType;        // 步骤类型
  config: StepConfig;            // 步骤配置(根据类型不同)
  description: string;           // 步骤描述
  dependsOn: string[];           // 依赖的步骤ID列表
  conditions: Condition[];       // 执行条件(预留)
  retryPolicy: RetryPolicy;      // 重试策略
  timeout: number;               // 步骤超时(毫秒)
}

interface RetryPolicy {
  enabled: boolean;      // 是否启用重试
  maxRetries: number;    // 最大重试次数
  delay: number;         // 重试间隔(毫秒)
}
```

### 4.5 执行对象 (Execution)

```typescript
interface Execution {
  id: string;                    // 执行实例ID
  workflowId: string;            // 关联的工作流ID
  workflowSnapshot: Workflow;    // 工作流快照
  status: WorkflowStatus;        // 执行状态
  variables: Record<string, any>; // 运行时变量
  stepResults: Record<string, StepResult>;  // 各步骤执行结果
  stepStatuses: Record<string, StepStatusInfo>;  // 各步骤状态
  logs: LogEntry[];              // 执行日志
  startTime: string | null;      // 开始时间
  endTime: string | null;        // 结束时间
  error: string | null;          // 错误信息
  createdAt: string;             // 创建时间
}

interface StepStatusInfo {
  status: StepStatus;    // 步骤状态
  startTime: string | null;  // 开始时间
  endTime: string | null;    // 结束时间
  retries: number;       // 已重试次数
  error: string | null;  // 错误信息
}

interface StepResult {
  [key: string]: any;    // 步骤返回的任意数据
}

interface LogEntry {
  type: 'info' | 'error' | 'warning' | 'workflow_started';
  message: string;               // 日志内容
  timestamp: string;             // 时间戳
  stepId?: string;               // 关联的步骤ID
  workflowId?: string;           // 关联的工作流ID
  workflowName?: string;         // 工作流名称(用于展示)
}
```

***

## 五、步骤类型配置

### 5.1 步骤类型枚举 (ActionType)

| 值                     | 中文名称         | 分类  | 说明                 |
| --------------------- | ------------ | --- | ------------------ |
| `jenkins_execute`     | Jenkins 任务执行 | 集成  | 触发并监控 Jenkins 构建任务 |
| `aws_ecs_check`       | AWS ECS 服务检查 | 集成  | 检查 AWS ECS 服务更新状态  |
| `wework_notification` | 企业微信通知       | 通知  | 通过企业微信机器人发送通知      |
| `webhook`             | Webhook 调用   | 集成  | 调用外部 Webhook       |
| `delay`               | 延迟等待         | 控制  | 延迟一段时间后继续执行        |
| `condition`           | 条件判断         | 控制  | 根据条件选择执行路径         |
| `parallel`            | 并行执行         | 控制  | 并行执行多个步骤           |
| `custom_action`       | 自定义动作        | 自定义 | 自定义的工作流动作          |

### 5.2 各类型详细配置

#### 5.2.1 Jenkins 任务执行 (jenkins\_execute)

```json
{
  "jenkinsUrl": "https://jenkins.example.com",
  "jobName": "app-build",
  "username": "jenkins-user",
  "apiToken": "xxxxxx",
  "parameters": {
    "BRANCH": "main",
    "ENV": "production"
  },
  "waitForBuild": true,
  "pollInterval": 5000,
  "timeout": 300000
}
```

| 字段名          | 类型      | 必填 | 默认值    | 说明            |
| ------------ | ------- | -- | ------ | ------------- |
| jenkinsUrl   | string  | 是  | -      | Jenkins 服务器地址 |
| jobName      | string  | 是  | -      | 任务名称          |
| username     | string  | 是  | -      | Jenkins 用户名   |
| apiToken     | string  | 是  | -      | API Token     |
| parameters   | object  | 否  | {}     | 构建参数          |
| waitForBuild | boolean | 否  | true   | 是否等待构建完成      |
| pollInterval | number  | 否  | 5000   | 轮询间隔(毫秒)      |
| timeout      | number  | 否  | 300000 | 超时时间(毫秒)      |

#### 5.2.2 AWS ECS 服务检查 (aws\_ecs\_check)

```json
{
  "region": "cn-north-1",
  "cluster": "production-cluster",
  "serviceName": "app-service",
  "expectedCount": 2,
  "checkInterval": 30000,
  "maxRetries": 10,
  "accessKeyId": "AKIAxxxxxx",
  "secretAccessKey": "xxxxxx"
}
```

| 字段名             | 类型     | 必填 | 默认值        | 说明             |
| --------------- | ------ | -- | ---------- | -------------- |
| region          | string | 是  | cn-north-1 | AWS 区域         |
| cluster         | string | 是  | -          | ECS 集群名称       |
| serviceName     | string | 是  | -          | 服务名称           |
| expectedCount   | number | 否  | null       | 期望的任务数         |
| checkInterval   | number | 否  | 30000      | 检查间隔(毫秒)       |
| maxRetries      | number | 否  | 10         | 最大重试次数         |
| accessKeyId     | string | 是  | -          | AWS Access Key |
| secretAccessKey | string | 是  | -          | AWS Secret Key |

#### 5.2.3 企业微信通知 (wework\_notification)

```json
{
  "webhookUrl": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
  "messageType": "template_card",
  "content": "部署成功，版本: {{version}}",
  "title": "部署通知",
  "description": "应用已成功部署到生产环境",
  "url": "https://dashboard.example.com",
  "picUrl": "https://example.com/image.png",
  "mentions": ["user1", "user2"],
  "mentionsText": "@user1 @user2",
  "mentionAll": false
}
```

| 字段名          | 类型      | 必填 | 默认值   | 说明                                      |
| ------------ | ------- | -- | ----- | --------------------------------------- |
| webhookUrl   | string  | 是  | -     | 机器人 Webhook 地址                          |
| messageType  | string  | 是  | text  | 消息类型: text/markdown/news/template\_card |
| content      | string  | 是  | -     | 消息内容                                    |
| title        | string  | 否  | -     | 标题(用于卡片类型)                              |
| description  | string  | 否  | -     | 描述                                      |
| url          | string  | 否  | -     | 跳转链接                                    |
| picUrl       | string  | 否  | -     | 图片链接                                    |
| mentions     | array   | 否  | \[]   | @用户列表                                   |
| mentionsText | string  | 否  | ""    | @用户文本                                   |
| mentionAll   | boolean | 否  | false | 是否@所有人                                  |

#### 5.2.4 Webhook 调用 (webhook)

```json
{
  "url": "https://api.example.com/deploy",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer token",
    "Content-Type": "application/json"
  },
  "headersJson": "{\"Authorization\":\"Bearer token\"}",
  "payload": {
    "version": "{{version}}",
    "env": "{{env}}"
  },
  "payloadJson": "{\"version\":\"{{version}}\"}",
  "timeout": 30000
}
```

| 字段名         | 类型     | 必填 | 默认值   | 说明                           |
| ----------- | ------ | -- | ----- | ---------------------------- |
| url         | string | 是  | -     | Webhook URL                  |
| method      | string | 否  | POST  | HTTP 方法: GET/POST/PUT/DELETE |
| headers     | object | 否  | {}    | 请求头                          |
| headersJson | string | 否  | ""    | 请求头 JSON 字符串                 |
| payload     | object | 否  | {}    | 请求体                          |
| payloadJson | string | 否  | ""    | 请求体 JSON 字符串                 |
| timeout     | number | 否  | 30000 | 超时时间(毫秒)                     |

#### 5.2.5 延迟等待 (delay)

```json
{
  "delay": 5000
}
```

| 字段名   | 类型     | 必填 | 默认值  | 说明       |
| ----- | ------ | -- | ---- | -------- |
| delay | number | 是  | 1000 | 延迟时间(毫秒) |

#### 5.2.6 条件判断 (condition) - 预留

```json
{
  "conditions": [
    {
      "variable": "step_1_output.success",
      "operator": "eq",
      "value": true
    }
  ],
  "trueSteps": ["step_3"],
  "falseSteps": ["step_4"]
}
```

#### 5.2.7 并行执行 (parallel) - 预留

```json
{
  "parallelSteps": ["step_2", "step_3", "step_4"]
}
```

#### 5.2.8 自定义动作 (custom\_action)

```json
{
  "script": "console.log('自定义逻辑')",
  "config": {
    "param1": "value1"
  }
}
```

***

## 六、注意事项

### 6.1 轮询机制

- 前端默认每 2 秒调用一次 `GET /api/workflow/execution/{executionId}` 获取执行状态
- 当状态为 `completed`、`failed` 或 `cancelled` 时，前端停止轮询
- 建议后端在执行完成后及时更新状态，避免前端长时间轮询

### 6.2 变量替换

- 步骤配置中支持 `{{变量名}}` 语法进行变量替换
- 变量来源优先级: 运行时变量 > 工作流定义变量 > 步骤输出变量
- 后端执行时需要解析并替换这些变量

示例:

```
配置值: "部署版本: {{version}} 到 {{env}} 环境"
变量: { version: "v1.0.0", env: "production" }
替换后: "部署版本: v1.0.0 到 production 环境"
```

### 6.3 步骤依赖 (dependsOn)

- 步骤可以通过 `dependsOn` 字段指定依赖的步骤ID列表
- 只有当所有依赖步骤都成功完成后，当前步骤才会执行
- 如果依赖步骤失败，当前步骤状态应为 `skipped`

### 6.4 工作流快照

- 执行工作流时，前端会发送完整的工作流快照 (`workflowSnapshot`)
- 后端可以选择:
  1. 使用快照中的配置执行 (推荐，保证执行时的配置一致性)
  2. 忽略快照，从数据库加载最新版本

### 6.5 认证与权限

- 所有 API 都需要验证用户身份
- 工作流应该与创建者关联，用户只能查看和操作自己的工作流
- 执行历史也应该按用户隔离

### 6.6 错误处理

- 执行失败时，应记录详细的错误信息到 `error` 字段
- 步骤级别的错误记录到 `stepStatuses[stepId].error`
- 建议保存完整的执行日志，便于问题排查

### 6.7 并发控制

- 同一工作流可以有多个执行实例同时运行
- 建议支持限制同一工作流的并发执行数 (可选)
- 执行ID应全局唯一

### 6.8 CSRF Token

部分框架(如 Django)需要 CSRF Token，前端会尝试从 Cookie 获取。如果后端使用 Django，需要确保:

- GET 请求返回 `csrftoken` Cookie
- POST/PUT/DELETE 请求允许携带 CSRF Token

***

## 七、接口汇总

| 方法     | 路径                                           | 功能         | 优先级 |
| ------ | -------------------------------------------- | ---------- | --- |
| GET    | /api/workflow/list                           | 获取工作流列表    | 高   |
| GET    | /api/workflow/{workflowId}                   | 获取工作流详情    | 高   |
| POST   | /api/workflow/create                         | 创建工作流      | 高   |
| PUT    | /api/workflow/{workflowId}                   | 更新工作流      | 高   |
| DELETE | /api/workflow/{workflowId}                   | 删除工作流      | 高   |
| POST   | /api/workflow/execute                        | 执行工作流      | 高   |
| GET    | /api/workflow/execution/{executionId}        | 获取执行状态(轮询) | 高   |
| GET    | /api/workflow/execution/{executionId}/logs   | 获取执行日志     | 中   |
| POST   | /api/workflow/execution/{executionId}/cancel | 取消执行       | 中   |
| POST   | /api/workflow/execution/{executionId}/pause  | 暂停执行       | 低   |
| POST   | /api/workflow/execution/{executionId}/resume | 恢复执行       | 低   |
| GET    | /api/workflow/history                        | 获取执行历史     | 中   |

***

> 文档结束\
> 如有问题请联系前端开发团队

