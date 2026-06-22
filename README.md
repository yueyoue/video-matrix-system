# 短视频矩阵运营系统

面向短视频矩阵运营团队的全流程管理系统。

## 项目结构

```
├── server/             # 后端API (PHP + MySQL)
├── web-admin/          # Web管理后台 (Vue 3)
├── client/             # 桌面客户端 (Python + PyQt6)
└── docs/               # 文档
```

## 🚀 宝塔面板部署（3步完成）

### 第一步：上传文件
1. 下载 `server.zip` 和 `web-admin.zip`
2. 在宝塔创建网站（绑定域名）
3. 将 `server.zip` 解压到网站根目录
4. 将 `web-admin.zip` 解压到同一目录（会生成 index.html 和 assets/）

### 第二步：自动安装
1. 浏览器访问 `http://你的域名/install`
2. 按页面提示：
   - ✅ 环境检测（自动）
   - 🗄️ 填写数据库信息（数据库名、用户名、密码）
   - 👤 设置管理员账号
3. 安装完成后 **删除 install 目录**

### 第三步：配置 Nginx 伪静态
在宝塔网站设置 → 伪静态，添加：
```nginx
location /api/ {
    try_files $uri $uri/ /index.php?$query_string;
}
location / {
    try_files $uri $uri/ /index.html;
}
```

### 访问地址
- **管理后台**：`http://你的域名/`
- **API接口**：`http://你的域名/api/`

## 默认账号
安装时自行设置管理员账号。

## 桌面客户端
1. 下载 `VideoMatrix.exe`
2. 双击运行
3. 登录时填写服务器地址（如 `https://你的域名/api`）

## 技术栈
- **后端**: PHP 7.4+ + MySQL 5.7+ + PDO
- **前端**: Vue 3 + Vite + Tailwind CSS
- **客户端**: Python 3.11 + PyQt6
- **部署**: 宝塔面板一键安装
