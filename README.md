# 短视频矩阵运营系统

面向短视频矩阵运营团队的全流程管理系统。

## 项目结构

```
├── server/             # 后端API服务 (Node.js + Express + SQLite)
├── web-admin/          # Web管理后台 (Vue 3 + Vite + Tailwind)
├── client/             # 桌面客户端 (Python + PyQt6)
├── docs/               # 项目文档
└── .github/workflows/  # CI/CD 自动构建发布
```

## 快速启动

### 1. 后端 API
```bash
cd server
npm install
npm start
# 服务运行在 http://localhost:3000
```

### 2. Web 管理后台
```bash
cd web-admin
npm install
npm run dev
# 开发服务运行在 http://localhost:5173
# 自动代理 API 请求到 localhost:3000
```

### 3. 桌面客户端
```bash
cd client
pip install -r requirements.txt
python main.py
```

## 默认账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | admin123 |
| 运营员 | operator1 | 123456 |

## 功能模块

### Web 管理后台
- 📊 数据统计中心 - 全局数据概览、用户排行、平台统计
- 👥 用户管理 - 增删改查、角色权限、配额管控
- 🎙️ AI配音配置 - 接口配置、音色管理
- 🔌 平台接口配置 - 多平台统一管理
- 📦 软件版本管理 - 版本发布、更新日志
- 📋 系统日志 - 操作记录、异常追踪

### 桌面客户端
- 📈 数据总览 - 今日工作量、异常预警
- 📊 数据分析 - 多维度筛选、数据导出
- 👤 账号管理 - 多平台账号、扫码添加
- 🎬 视频处理 - 裁切、混剪、AI配音
- 🚀 发布调度 - 定时发布、队列管理
- ⚙️ 接口配置 - 平台参数同步
- 📝 日志中心 - 运行日志、一键导出

## 部署

### 服务器部署
1. 上传 `server.zip` 到服务器，解压后 `npm install && npm start`
2. 上传 `web-admin.zip` 到 Nginx 静态目录，配置反向代理 `/api` 到 `localhost:3000`

### GitHub Actions 自动构建
```bash
git tag v1.0.0
git push origin v1.0.0
# 自动构建并发布到 Releases
```

## 技术栈

- **后端**: Node.js + Express + SQLite + JWT
- **前端**: Vue 3 + Vite + Tailwind CSS + Pinia
- **客户端**: Python 3.11 + PyQt6
- **CI/CD**: GitHub Actions
