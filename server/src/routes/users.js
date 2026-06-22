const express = require('express');
const bcrypt = require('bcryptjs');
const { getDB } = require('../db');
const { authMiddleware, adminOnly } = require('../middleware/auth');
const { logOperation } = require('../middleware/logger');

const router = express.Router();
router.use(authMiddleware);

// GET /api/users
router.get('/', adminOnly, (req, res) => {
  const { page = 1, pageSize = 20, keyword } = req.query;
  const p = Math.max(1, parseInt(page));
  const ps = Math.max(1, Math.min(100, parseInt(pageSize)));
  const offset = (p - 1) * ps;

  const db = getDB();
  let where = '1=1';
  const params = [];
  if (keyword) { where += ' AND username LIKE ?'; params.push(`%${keyword}%`); }

  const total = db.prepare(`SELECT COUNT(*) as c FROM sys_user WHERE ${where}`).get(...params).c;
  const rows = db.prepare(`SELECT id, username, role, daily_quota, used_quota, status, last_login, created_at, updated_at FROM sys_user WHERE ${where} ORDER BY id DESC LIMIT ? OFFSET ?`).all(...params, ps, offset);

  res.json({
    code: 0,
    data: {
      list: rows.map(r => ({
        id: r.id, username: r.username, role: r.role, dailyQuota: r.daily_quota,
        usedQuota: r.used_quota, status: r.status, lastLogin: r.last_login,
        createdAt: r.created_at, updatedAt: r.updated_at,
      })),
      total, page: p, pageSize: ps,
    },
    message: 'ok',
  });
});

// POST /api/users
router.post('/', adminOnly, (req, res) => {
  const { username, password, role = 'operator', dailyQuota = 50 } = req.body;
  if (!username || !password) return res.json({ code: 400, data: null, message: '用户名和密码不能为空' });

  const db = getDB();
  const existing = db.prepare('SELECT id FROM sys_user WHERE username = ?').get(username);
  if (existing) return res.json({ code: 400, data: null, message: '用户名已存在' });

  const hash = bcrypt.hashSync(password, 10);
  const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
  const result = db.prepare('INSERT INTO sys_user (username, password_hash, role, daily_quota, created_at, updated_at) VALUES (?,?,?,?,?,?)').run(username, hash, role, dailyQuota, now, now);

  logOperation({ userId: req.user.id, username: req.user.username, module: '用户管理', action: '创建用户', detail: `创建用户 ${username}` });
  res.json({ code: 0, data: { id: result.lastInsertRowid }, message: 'ok' });
});

// PUT /api/users/:id
router.put('/:id', adminOnly, (req, res) => {
  const { id } = req.params;
  const { password, role, dailyQuota, status } = req.body;

  const db = getDB();
  const user = db.prepare('SELECT * FROM sys_user WHERE id = ?').get(id);
  if (!user) return res.json({ code: 404, data: null, message: '用户不存在' });

  const updates = []; const params = [];
  if (password) { updates.push('password_hash = ?'); params.push(bcrypt.hashSync(password, 10)); }
  if (role) { updates.push('role = ?'); params.push(role); }
  if (dailyQuota !== undefined) { updates.push('daily_quota = ?'); params.push(dailyQuota); }
  if (status) { updates.push('status = ?'); params.push(status); }
  if (updates.length === 0) return res.json({ code: 400, data: null, message: '没有需要更新的字段' });

  updates.push("updated_at = datetime('now')");
  params.push(id);
  db.prepare(`UPDATE sys_user SET ${updates.join(', ')} WHERE id = ?`).run(...params);

  logOperation({ userId: req.user.id, username: req.user.username, module: '用户管理', action: '更新用户', detail: `更新用户 ID=${id}` });
  res.json({ code: 0, data: null, message: 'ok' });
});

// DELETE /api/users/:id
router.delete('/:id', adminOnly, (req, res) => {
  const { id } = req.params;
  const db = getDB();
  const user = db.prepare('SELECT * FROM sys_user WHERE id = ?').get(id);
  if (!user) return res.json({ code: 404, data: null, message: '用户不存在' });
  if (user.role === 'admin') return res.json({ code: 400, data: null, message: '不能删除管理员账号' });

  db.prepare('DELETE FROM sys_user WHERE id = ?').run(id);
  logOperation({ userId: req.user.id, username: req.user.username, module: '用户管理', action: '删除用户', detail: `删除用户 ${user.username}` });
  res.json({ code: 0, data: null, message: 'ok' });
});

module.exports = router;
