# 视频矩阵系统 - 后端API服务

基于 Node.js + Express + SQLite 的视频矩阵管理系统后端。

## 技术栈

- **运行时**: Node.js
- **框架**: Express
- **数据库**: SQLite (better-sqlite3)
- **认证**: JWT (jsonwebtoken)
- **加密**: bcryptjs
- **文件上传**: multer
- **跨域**: cors

## 快速开始

```bash
# 1. 安装依赖
npm install

# 2. 启动服务
npm start

# 或者开发模式（自动重启）
npm run dev
```

服务将在 `http://localhost:3000` 启动。

## 默认账号

| 用户名 | 密码 | 角色 | 每日配额 |
|--------|------|------|----------|
| admin | admin123 | admin | 999 |
| operator1 | 123456 | operator | 50 |

## API 接口

所有接口以 `/api` 为前缀，响应格式：

```json
{
  "code": 0,
  "data": {},
  "message": "ok"
}
```

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/login | 登录 |
| GET | /api/auth/profile | 获取当前用户信息 |

### 用户管理 (需要admin权限)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/users | 用户列表 |
| POST | /api/users | 创建用户 |
| PUT | /api/users/:id | 更新用户 |
| DELETE | /api/users/:id | 删除用户 |

### 平台账号

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/accounts | 账号列表 |
| POST | /api/accounts | 添加账号 |
| PUT | /api/accounts/:id | 更新账号 |
| DELETE | /api/accounts/:id | 删除账号 |
| POST | /api/accounts/:id/check | 检测状态 |

### 视频任务

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/videos | 任务列表 |
| POST | /api/videos/cut | 创建裁切任务 |
| POST | /api/videos/mix | 创建混剪任务 |
| DELETE | /api/videos/:id | 删除任务 |

### 发布调度

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/publish/queue | 发布队列 |
| GET | /api/publish/rule | 获取规则 |
| POST | /api/publish/rule | 保存规则 |
| POST | /api/publish/:id/publishNow | 立即发布 |
| DELETE | /api/publish/:id | 取消发布 |

### 数据统计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/stats/overview | 今日总览 |
| GET | /api/stats/users | 用户排行 |
| GET | /api/stats/platforms | 平台统计 |
| GET | /api/stats/analysis | 分析数据 |

### AI配音

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/ai/voices | 音色列表 |
| POST | /api/ai/voices | 添加音色 |
| PUT | /api/ai/voices/:id | 更新音色 |
| GET | /api/ai/config | 获取配置 |
| PUT | /api/ai/config | 更新配置 |
| POST | /api/ai/test | 测试连通 |

### 平台配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/platform-config/:platform | 获取配置 |
| PUT | /api/platform-config/:platform | 更新配置 |
| POST | /api/platform-config/:platform/reset | 恢复默认 |

### 版本管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/versions | 版本列表 |
| POST | /api/versions | 发布版本 |
| PUT | /api/versions/:id | 更新版本 |
| GET | /api/versions/latest | 最新版本 |

### 日志

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/logs | 日志列表 |
| GET | /api/logs/export | 导出CSV |

### 文件上传

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/upload | 上传文件 |

### 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/health | 服务状态 |

## 目录结构

```
server/
├── package.json
├── README.md
├── data/           # SQLite数据库文件（自动创建）
├── uploads/        # 上传文件目录（自动创建）
└── src/
    ├── app.js      # 入口文件
    ├── db.js       # 数据库初始化 + 种子数据
    ├── middleware/
    │   ├── auth.js   # JWT认证中间件
    │   └── logger.js # 操作日志
    └── routes/
        ├── auth.js           # 认证
        ├── users.js          # 用户管理
        ├── accounts.js       # 平台账号
        ├── videos.js         # 视频任务
        ├── publish.js        # 发布调度
        ├── stats.js          # 数据统计
        ├── ai.js             # AI配音
        ├── platform-config.js # 平台配置
        ├── versions.js       # 版本管理
        ├── logs.js           # 操作日志
        └── upload.js         # 文件上传
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| PORT | 3000 | 服务端口 |
| JWT_SECRET | video-matrix-secret-key-2024 | JWT密钥 |

## 注意事项

- 首次启动自动创建数据库并插入示例数据
- CORS 已开放所有来源（开发阶段）
- 上传文件大小限制 500MB
- JWT Token 有效期 7 天
