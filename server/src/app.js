const express = require('express');
const cors = require('cors');
const path = require('path');
const { initDB } = require('./db');

async function main() {
  // Initialize database (async for sql.js)
  await initDB();

  const app = express();
  const PORT = process.env.PORT || 3000;

  // Middleware
  app.use(cors());
  app.use(express.json({ limit: '10mb' }));
  app.use(express.urlencoded({ extended: true }));
  app.use('/uploads', express.static(path.join(__dirname, '..', 'uploads')));

  // Routes
  app.use('/api/auth', require('./routes/auth'));
  app.use('/api/users', require('./routes/users'));
  app.use('/api/accounts', require('./routes/accounts'));
  app.use('/api/videos', require('./routes/videos'));
  app.use('/api/publish', require('./routes/publish'));
  app.use('/api/stats', require('./routes/stats'));
  app.use('/api/ai', require('./routes/ai'));
  app.use('/api/platform-config', require('./routes/platform-config'));
  app.use('/api/versions', require('./routes/versions'));
  app.use('/api/logs', require('./routes/logs'));
  app.use('/api/upload', require('./routes/upload'));

  // Health check
  app.get('/api/health', (req, res) => {
    res.json({ code: 0, data: { status: 'ok', uptime: process.uptime() }, message: 'ok' });
  });

  // 404
  app.use((req, res) => {
    res.status(404).json({ code: 404, data: null, message: `接口不存在: ${req.method} ${req.path}` });
  });

  // Error handler
  app.use((err, req, res, next) => {
    console.error('Server error:', err);
    if (err.code === 'LIMIT_FILE_SIZE') {
      return res.status(400).json({ code: 400, data: null, message: '文件大小超出限制' });
    }
    res.status(500).json({ code: 500, data: null, message: err.message || '服务器内部错误' });
  });

  app.listen(PORT, () => {
    console.log(`\n🚀 视频矩阵系统 API 服务已启动`);
    console.log(`📡 地址: http://localhost:${PORT}`);
    console.log(`📋 健康检查: http://localhost:${PORT}/api/health`);
    console.log(`👤 管理员: admin / admin123`);
    console.log(`👤 运营: operator1 / 123456\n`);
  });
}

main().catch(err => {
  console.error('Failed to start server:', err);
  process.exit(1);
});
