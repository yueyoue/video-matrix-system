const express = require('express');
const { getDB } = require('../db');
const { authMiddleware, adminOnly } = require('../middleware/auth');

const router = express.Router();
router.use(authMiddleware);

// GET /api/logs
router.get('/', adminOnly, (req, res) => {
  const { page = 1, pageSize = 20, level, keyword } = req.query;
  const p = Math.max(1, parseInt(page));
  const ps = Math.max(1, Math.min(100, parseInt(pageSize)));
  const offset = (p - 1) * ps;

  const db = getDB();
  let where = '1=1';
  const params = [];
  if (level) { where += ' AND level = ?'; params.push(level); }
  if (keyword) {
    where += ' AND (username LIKE ? OR module LIKE ? OR action LIKE ? OR detail LIKE ?)';
    const kw = `%${keyword}%`;
    params.push(kw, kw, kw, kw);
  }

  const total = db.prepare(`SELECT COUNT(*) as c FROM operation_log WHERE ${where}`).get(...params).c;
  const rows = db.prepare(`SELECT * FROM operation_log WHERE ${where} ORDER BY id DESC LIMIT ? OFFSET ?`).all(...params, ps, offset);

  res.json({
    code: 0,
    data: {
      list: rows.map(r => ({
        id: r.id, userId: r.user_id, username: r.username, level: r.level,
        module: r.module, action: r.action, detail: r.detail, createdAt: r.created_at,
      })),
      total, page: p, pageSize: ps,
    },
    message: 'ok',
  });
});

// GET /api/logs/export
router.get('/export', adminOnly, (req, res) => {
  const { level, keyword } = req.query;
  const db = getDB();
  let where = '1=1';
  const params = [];
  if (level) { where += ' AND level = ?'; params.push(level); }
  if (keyword) {
    where += ' AND (username LIKE ? OR module LIKE ? OR action LIKE ? OR detail LIKE ?)';
    const kw = `%${keyword}%`;
    params.push(kw, kw, kw, kw);
  }

  const rows = db.prepare(`SELECT * FROM operation_log WHERE ${where} ORDER BY id DESC`).all(...params);

  const header = 'ID,用户ID,用户名,级别,模块,操作,详情,时间\n';
  const csv = header + rows.map(r =>
    `${r.id},${r.user_id || ''},${r.username || ''},${r.level},${r.module || ''},${r.action || ''},"${(r.detail || '').replace(/"/g, '""')}",${r.created_at}`
  ).join('\n');

  res.setHeader('Content-Type', 'text/csv; charset=utf-8');
  res.setHeader('Content-Disposition', 'attachment; filename=operation_logs.csv');
  res.send('\uFEFF' + csv);
});

module.exports = router;
