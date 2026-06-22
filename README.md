# 短视频矩阵运营系统

面向短视频矩阵运营团队的全流程管理系统，包含 Web 管理后台和桌面客户端。

## 项目结构

```
├── web-admin/          # Web管理后台（管理员端）
├── client/             # 桌面客户端（运营人员端）
├── docs/               # 项目文档
└── .github/workflows/  # CI/CD 配置
```

## 功能模块

### Web 管理后台
- 📊 数据统计中心
- 👥 用户管理
- 🎙️ AI配音配置
- 🔌 平台接口配置
- 📦 软件版本管理
- 📋 系统日志

### 桌面客户端
- 📈 数据总览 & 数据分析
- 👤 账号管理（抖音/快手/小红书/视频号）
- 🎬 视频处理（裁切/混剪/AI配音）
- 🚀 发布调度
- ⚙️ 接口配置
- 📝 日志中心

## 快速开始

### 本地预览
直接用浏览器打开 `web-admin/index.html` 或 `client/index.html` 即可查看交互原型。

### 自动构建
推送 `v*` 标签后，GitHub Actions 自动打包并发布到 Releases。

```bash
git tag v1.0.0
git push origin v1.0.0
```

## 技术栈

- **前端原型**: HTML + Tailwind CSS + Vanilla JavaScript
- **规划技术栈**: PHP 8.0+ (ThinkPHP 6) + MySQL 5.7+ + Python 3.11 (PyQt6)
