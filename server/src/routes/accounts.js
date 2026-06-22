const express = require('express');
const { getDB } = require('../db');
const { authMiddleware } = require('../middleware/auth');
const { logOperation } = require('../middleware/logger');

const router = express.Router();
router.use(authMiddleware);

// GET /api/accounts
router.get('/', (req, res) => {
  const { platform, page = 1, pageSize = 20 } = req.query;
  const p = Math.max(1, parseInt(page));
  const ps = Math.max(1, Math.min(100, parseInt(pageSize)));
  const offset = (p - 1) * ps;

  const db = getDB();
  let where = '1=1';
  const params = [];
  if (platform) { where += ' AND platform = ?'; params.push(platform); }
  if (req.user.role !== 'admin') { where += ' AND user_id = ?'; params.push(req.user.id); }

  const total = db.prepare(`SELECT COUNT(*) as c FROM platform_account WHERE ${where}`).get(...params).c;
  const rows = db.prepare(`SELECT * FROM platform_account WHERE ${where} ORDER BY id DESC LIMIT ? OFFSET ?`).all(...params, ps, offset);

  res.json({
    code: 0,
    data: {
      list: rows.map(r => ({
        id: r.id, userId: r.user_id, platform: r.platform, nickname: r.nickname,
        avatarUrl: r.avatar_url, status: r.status, worksCount: r.works_count,
        totalPlays: r.total_plays, todayPublish: r.today_publish,
        lastLogin: r.last_login, createdAt: r.created_at,
      })),
      total, page: p, pageSize: ps,
    },
    message: 'ok',
  });
});

// POST /api/accounts
router.post('/', (req, res) => {
  const { platform, nickname, avatarUrl, cookie } = req.body;
  if (!platform || !nickname) return res.json({ code: 400, data: null, message: '平台和昵称不能为空' });

  const db = getDB();
  const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
  const result = db.prepare('INSERT INTO platform_account (user_id, platform, nickname, avatar_url, cookie, created_at) VALUES (?,?,?,?,?,?)')
    .run(req.user.id, platform, nickname, avatarUrl || null, cookie || null, now);

  logOperation({ userId: req.user.id, username: req.user.username, module: '平台账号', action: '添加账号', detail: `添加 ${platform} 账号: ${nickname}` });
  res.json({ code: 0, data: { id: result.lastInsertRowid }, message: 'ok' });
});

// PUT /api/accounts/:id
router.put('/:id', (req, res) => {
  const { id } = req.params;
  const db = getDB();
  const acct = db.prepare('SELECT * FROM platform_account WHERE id = ?').get(id);
  if (!acct) return res.json({ code: 404, data: null, message: '账号不存在' });
  if (req.user.role !== 'admin' && acct.user_id !== req.user.id) return res.json({ code: 403, data: null, message: '无权操作' });

  const { nickname, avatarUrl, cookie, status } = req.body;
  const updates = []; const params = [];
  if (nickname) { updates.push('nickname = ?'); params.push(nickname); }
  if (avatarUrl !== undefined) { updates.push('avatar_url = ?'); params.push(avatarUrl); }
  if (cookie !== undefined) { updates.push('cookie = ?'); params.push(cookie); }
  if (status) { updates.push('status = ?'); params.push(status); }
  if (updates.length === 0) return res.json({ code: 400, data: null, message: '没有需要更新的字段' });

  params.push(id);
  db.prepare(`UPDATE platform_account SET ${updates.join(', ')} WHERE id = ?`).run(...params);

  logOperation({ userId: req.user.id, username: req.user.username, module: '平台账号', action: '更新账号', detail: `更新账号 ID=${id}` });
  res.json({ code: 0, data: null, message: 'ok' });
});

// DELETE /api/accounts/:id
router.delete('/:id', (req, res) => {
  const { id } = req.params;
  const db = getDB();
  const acct = db.prepare('SELECT * FROM platform_account WHERE id = ?').get(id);
  if (!acct) return res.json({ code: 404, data: null, message: '账号不存在' });
  if (req.user.role !== 'admin' && acct.user_id !== req.user.id) return res.json({ code: 403, data: null, message: '无权操作' });

  db.prepare('DELETE FROM platform_account WHERE id = ?').run(id);
  logOperation({ userId: req.user.id, username: req.user.username, module: '平台账号', action: '删除账号', detail: `删除账号 ${acct.nickname}` });
  res.json({ code: 0, data: null, message: 'ok' });
});

// POST /api/accounts/:id/check
router.post('/:id/check', (req, res) => {
  const { id } = req.params;
  const db = getDB();
  const acct = db.prepare('SELECT * FROM platform_account WHERE id = ?').get(id);
  if (!acct) return res.json({ code: 404, data: null, message: '账号不存在' });

  const newStatus = Math.random() > 0.3 ? 'active' : 'expired';
  db.prepare('UPDATE platform_account SET status = ? WHERE id = ?').run(newStatus, id);

  logOperation({ userId: req.user.id, username: req.user.username, module: '平台账号', action: '检测状态', detail: `检测账号 ${acct.nickname} -> ${newStatus}` });
  res.json({ code: 0, data: { id: acct.id, status: newStatus }, message: 'ok' });
});

module.exports = router;
