const express = require('express');
const bcrypt = require('bcryptjs');
const { getDB } = require('../db');
const { signToken, authMiddleware } = require('../middleware/auth');
const { logOperation } = require('../middleware/logger');

const router = express.Router();

// POST /api/auth/login
router.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.json({ code: 400, data: null, message: '用户名和密码不能为空' });
  }

  const db = getDB();
  const user = db.prepare('SELECT * FROM sys_user WHERE username = ?').get(username);
  if (!user) {
    return res.json({ code: 401, data: null, message: '用户名或密码错误' });
  }

  if (user.status === 'disabled') {
    return res.json({ code: 403, data: null, message: '账号已被禁用' });
  }

  if (!bcrypt.compareSync(password, user.password_hash)) {
    return res.json({ code: 401, data: null, message: '用户名或密码错误' });
  }

  const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
  db.prepare('UPDATE sys_user SET last_login = ? WHERE id = ?').run(now, user.id);

  const token = signToken({ id: user.id, username: user.username, role: user.role });

  logOperation({ userId: user.id, username: user.username, level: 'INFO', module: '认证', action: '登录', detail: `${user.username} 登录系统` });

  res.json({
    code: 0,
    data: {
      token,
      user: {
        id: user.id, username: user.username, role: user.role,
        dailyQuota: user.daily_quota, usedQuota: user.used_quota, status: user.status,
      },
    },
    message: 'ok',
  });
});

// GET /api/auth/profile
router.get('/profile', authMiddleware, (req, res) => {
  const db = getDB();
  const user = db.prepare('SELECT id, username, role, daily_quota, used_quota, status, last_login, created_at FROM sys_user WHERE id = ?').get(req.user.id);
  if (!user) {
    return res.json({ code: 404, data: null, message: '用户不存在' });
  }
  res.json({
    code: 0,
    data: {
      id: user.id, username: user.username, role: user.role,
      dailyQuota: user.daily_quota, usedQuota: user.used_quota, status: user.status,
      lastLogin: user.last_login, createdAt: user.created_at,
    },
    message: 'ok',
  });
});

module.exports = router;
