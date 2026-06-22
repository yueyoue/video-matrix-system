# API 接口规范

## 基础信息
- Base URL: `/api`
- 认证: Bearer Token (JWT)
- 响应格式: `{ code: 0, data: ..., message: "ok" }` (code=0 成功, 其他失败)

## 一、认证模块

### POST /api/auth/login
登录接口
```json
Request: { "username": "admin", "password": "123456" }
Response: { code: 0, data: { token: "xxx", user: { id, username, role, dailyQuota, usedQuota } } }
```

### GET /api/auth/profile
获取当前用户信息（需认证）
```json
Response: { code: 0, data: { id, username, role, dailyQuota, usedQuota, status } }
```

## 二、用户管理（管理员）

### GET /api/users
用户列表 ?page=1&pageSize=20&keyword=xxx

### POST /api/users
创建用户 { username, password, role, dailyQuota }

### PUT /api/users/:id
更新用户 { username, role, dailyQuota, status, password? }

### DELETE /api/users/:id
删除用户

## 三、平台账号管理

### GET /api/accounts
账号列表 ?platform=douyin&page=1&pageSize=20

### POST /api/accounts
添加账号 { platform, nickname, cookie }

### PUT /api/accounts/:id
更新账号

### DELETE /api/accounts/:id
删除账号

### POST /api/accounts/:id/check
检测登录状态

## 四、视频任务

### GET /api/videos
视频列表 ?page=1&pageSize=20&status=pending

### POST /api/videos/cut
裁切视频 { fileId, segments, namingRule }

### POST /api/videos/mix
混剪视频 { sourceIds, mixRule, dubbingText?, voiceId?, voiceSpeed?, bgmFileId?, bgmVolume?, subtitle? }

### DELETE /api/videos/:id
删除视频

## 五、发布调度

### GET /api/publish/queue
待发布队列

### POST /api/publish/rule
保存发布规则 { platforms, dailyLimit, publishTimes, order, autoRemove }

### GET /api/publish/rule
获取发布规则

### POST /api/publish/:id/publishNow
立即发布

### DELETE /api/publish/:id
取消任务

## 六、数据统计

### GET /api/stats/overview
总览数据（今日）
```json
Response: { code: 0, data: { totalUsers, todayVideos, todaySuccess, todayFail, successRate } }
```

### GET /api/stats/users
用户工作量排行 ?date=today

### GET /api/stats/platforms
平台统计 ?date=today

### GET /api/stats/analysis
数据分析 ?startDate=&endDate=&platform=&accountId=&page=1&pageSize=20
```json
Response: { code: 0, data: { summary: { plays, likes, comments, shares, yesterdayPlays... }, 
  platformDetail: [...], videos: { list: [...], total } } }
```

## 七、AI配音配置

### GET /api/ai/voices
音色列表

### POST /api/ai/voices
添加音色 { name, voiceId, type, scene }

### PUT /api/ai/voices/:id
更新音色

### GET /api/ai/config
获取AI接口配置

### PUT /api/ai/config
更新AI接口配置 { provider, appId, secret, dailyLimit }

### POST /api/ai/test
测试接口连通性

## 八、平台接口配置

### GET /api/platform-config/:platform
获取平台配置

### PUT /api/platform-config/:platform
更新平台配置 { fields: [...] }

### POST /api/platform-config/:platform/reset
恢复默认

## 九、版本管理

### GET /api/versions
版本列表

### POST /api/versions
发布版本 { version, changelog, downloadUrl }

### PUT /api/versions/:id
更新版本状态 { status: 'current'|'archived'|'delisted' }

### GET /api/versions/latest
获取最新版本（客户端用）

## 十、系统日志

### GET /api/logs
日志列表 ?page=1&pageSize=20&level=INFO&keyword=xxx&startDate=&endDate=

### GET /api/logs/export
导出日志

## 十一、文件上传

### POST /api/upload
上传文件，返回 { fileId, url }
