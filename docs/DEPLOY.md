# 宝塔面板部署教程

## 前提条件
- 宝塔面板已安装
- 已安装 **Node.js 版本管理器** 插件（宝塔软件商店搜索安装）
- 域名已解析到服务器（如 sp.tthsdd.top）

---

## 第一步：部署后端 API

### 1. 上传代码
- 在宝塔文件管理中，进入 `/www/wwwroot/` 目录
- 创建文件夹 `video-matrix-server`
- 将 `server/` 目录下所有文件上传到此文件夹

### 2. 安装 Node.js
- 宝塔面板 → **Node项目** → **Node版本管理器**
- 安装 Node.js 18.x 或 20.x

### 3. 安装依赖
- 进入 `/www/wwwroot/video-matrix-server/`
- 在宝塔终端中执行：
```bash
npm install --production
```

### 4. 启动项目
- 宝塔面板 → **Node项目** → **添加Node项目**
- 项目目录：`/www/wwwroot/video-matrix-server`
- 启动选项：
  - 启动文件：`src/app.js`
  - 运行用户：www
  - 端口：`3000`
  - 包管理器：npm
  - Node版本：18.x 或 20.x
- 点击 **提交**，项目会自动启动

### 5. 测试
```bash
curl http://localhost:3000/api/health
# 应返回: {"code":0,"data":{"status":"ok"}}
```

---

## 第二步：部署 Web 管理后台

### 方式一：使用构建好的文件
1. 从 GitHub Releases 下载 `web-admin.zip`
2. 解压到 `/www/wwwroot/sp.tthsdd.top/`
3. 跳到「配置 Nginx」步骤

### 方式二：在服务器上构建
```bash
cd /www/wwwroot/video-matrix-server
# 上传 web-admin 目录
cd web-admin
npm install
npm run build
# 构建产物在 web-admin/dist/ 目录
cp -r dist/* /www/wwwroot/sp.tthsdd.top/
```

### 配置 Nginx（反向代理）
1. 宝塔面板 → **网站** → 找到 `sp.tthsdd.top` → **设置**
2. 点击 **反向代理** → **添加反向代理**
3. 配置：
   - 代理名称：`api`
   - 目标URL：`http://127.0.0.1:3000`
   - 发送域名：`$host`
4. 点击 **配置文件**，确认有以下规则：
```nginx
location /api/ {
    proxy_pass http://127.0.0.1:3000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

### 配置前端路由（Vue History 模式）
在 Nginx 配置文件中添加：
```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```

---

## 第三步：验证部署

1. 访问 `https://sp.tthsdd.top`
2. 应看到登录页面
3. 使用 `admin / admin123` 登录
4. 测试各功能页面

---

## 常见问题

### Q: API 请求 502 Bad Gateway
A: 后端服务未启动，检查 Node项目 状态

### Q: 页面刷新后 404
A: Nginx 缺少 `try_files` 配置，按上面步骤添加

### Q: 如何修改默认密码？
A: 登录后在「用户管理」页面修改 admin 密码

### Q: 如何更新版本？
A: 
1. 上传新代码
2. 重启 Node 项目
3. 重新构建前端 `npm run build`

### Q: 数据库在哪里？
A: SQLite 数据库文件在 `server/data/database.db`，自动创建，备份此文件即可
