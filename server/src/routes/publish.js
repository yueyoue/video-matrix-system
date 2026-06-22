const express = require('express');
const { getDB } = require('../db');
const { authMiddleware } = require('../middleware/auth');
const { logOperation } = require('../middleware/logger');

const router = express.Router();
router.use(authMiddleware);

const publishRules = {};

// GET /api/publish/queue
router.get('/queue', (req, res) => {
  const { page = 1, pageSize = 20, status } = req.query;
  const p = Math.max(1, parseInt(page));
  const ps = Math.max(1, Math.min(100, parseInt(pageSize)));
  const offset = (p - 1) * ps;

  const db = getDB();
  let where = '1=1';
  const params = [];
  if (status) { where += ' AND pr.status = ?'; params.push(status); }
  if (req.user.role !== 'admin') { where += ' AND pr.user_id = ?'; params.push(req.user.id); }

  const total = db.prepare(`SELECT COUNT(*) as c FROM publish_record pr WHERE ${where}`).get(...params).c;
  const rows = db.prepare(`SELECT pr.* FROM publish_record pr WHERE ${where} ORDER BY pr.id DESC LIMIT ? OFFSET ?`).all(...params, ps, offset);

  res.json({
    code: 0,
    data: {
      list: rows.map(r => ({
        id: r.id, userId: r.user_id, accountId: r.account_id, videoId: r.video_id,
        platform: r.platform, accountName: r.account_name, videoTitle: r.video_title,
        scheduledTime: r.scheduled_time, publishedTime: r.published_time,
        status: r.status, errorMsg: r.error_msg, createdAt: r.created_at,
      })),
      total, page: p, pageSize: ps,
    },
    message: 'ok',
  });
});

// GET /api/publish/rule
router.get('/rule', (req, res) => {
  const rule = publishRules[req.user.id] || {
    publishInterval: 60, dailyLimit: 10,
    timeWindows: [{ start: '08:00', end: '12:00' }, { start: '14:00', end: '22:00' }],
    autoRetry: true, maxRetries: 3,
  };
  res.json({ code: 0, data: rule, message: 'ok' });
});

// POST /api/publish/rule
router.post('/rule', (req, res) => {
  publishRules[req.user.id] = req.body;
  logOperation({ userId: req.user.id, username: req.user.username, module: '发布调度', action: '保存规则', detail: '更新发布规则' });
  res.json({ code: 0, data: null, message: 'ok' });
});

// POST /api/publish/:id/publishNow
router.post('/:id/publishNow', (req, res) => {
  const { id } = req.params;
  const db = getDB();
  const record = db.prepare('SELECT * FROM publish_record WHERE id = ?').get(id);
  if (!record) return res.json({ code: 404, data: null, message: '记录不存在' });

  const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
  db.prepare('UPDATE publish_record SET status = ?, published_time = ? WHERE id = ?').run('success', now, id);

  logOperation({ userId: req.user.id, username: req.user.username, module: '发布调度', action: '立即发布', detail: `发布记录 ID=${id}` });
  res.json({ code: 0, data: { id: parseInt(id), status: 'success', publishedTime: now }, message: 'ok' });
});

// DELETE /api/publish/:id
router.delete('/:id', (req, res) => {
  const { id } = req.params;
  const db = getDB();
  const record = db.prepare('SELECT * FROM publish_record WHERE id = ?').get(id);
  if (!record) return res.json({ code: 404, data: null, message: '记录不存在' });
  if (record.status !== 'waiting') return res.json({ code: 400, data: null, message: '只能取消等待中的任务' });

  db.prepare('DELETE FROM publish_record WHERE id = ?').run(id);
  logOperation({ userId: req.user.id, username: req.user.username, module: '发布调度', action: '取消发布', detail: `取消记录 ID=${id}` });
  res.json({ code: 0, data: null, message: 'ok' });
});

module.exports = router;
