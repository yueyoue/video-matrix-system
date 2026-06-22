const express = require('express');
const { getDB } = require('../db');
const { authMiddleware } = require('../middleware/auth');
const { logOperation } = require('../middleware/logger');

const router = express.Router();
router.use(authMiddleware);

// GET /api/versions
router.get('/', (req, res) => {
  const db = getDB();
  const rows = db.prepare('SELECT * FROM app_version ORDER BY id DESC').all();
  res.json({
    code: 0,
    data: rows.map(r => ({ id: r.id, version: r.version, changelog: r.changelog, downloadUrl: r.download_url, status: r.status, createdAt: r.created_at })),
    message: 'ok',
  });
});

// POST /api/versions
router.post('/', (req, res) => {
  const { version, changelog, downloadUrl } = req.body;
  if (!version) return res.json({ code: 400, data: null, message: '版本号不能为空' });

  const db = getDB();
  const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
  db.prepare("UPDATE app_version SET status = 'archived' WHERE status = 'current'").run();
  const result = db.prepare('INSERT INTO app_version (version, changelog, download_url, status, created_at) VALUES (?,?,?,?,?)')
    .run(version, changelog || '', downloadUrl || '', 'current', now);

  logOperation({ userId: req.user.id, username: req.user.username, module: '版本管理', action: '发布版本', detail: `发布 v${version}` });
  res.json({ code: 0, data: { id: result.lastInsertRowid }, message: 'ok' });
});

// PUT /api/versions/:id
router.put('/:id', (req, res) => {
  const { id } = req.params;
  const { status, changelog, downloadUrl } = req.body;

  const db = getDB();
  const ver = db.prepare('SELECT * FROM app_version WHERE id = ?').get(id);
  if (!ver) return res.json({ code: 404, data: null, message: '版本不存在' });

  const updates = []; const params = [];
  if (status) { updates.push('status = ?'); params.push(status); }
  if (changelog !== undefined) { updates.push('changelog = ?'); params.push(changelog); }
  if (downloadUrl !== undefined) { updates.push('download_url = ?'); params.push(downloadUrl); }
  if (updates.length === 0) return res.json({ code: 400, data: null, message: '没有需要更新的字段' });

  if (status === 'current') {
    db.prepare("UPDATE app_version SET status = 'archived' WHERE status = 'current' AND id != ?").run(id);
  }

  params.push(id);
  db.prepare(`UPDATE app_version SET ${updates.join(', ')} WHERE id = ?`).run(...params);

  logOperation({ userId: req.user.id, username: req.user.username, module: '版本管理', action: '更新版本', detail: `更新版本 ID=${id}` });
  res.json({ code: 0, data: null, message: 'ok' });
});

// GET /api/versions/latest — must be before /:id would catch it, but since GET / already handles list, this is fine
router.get('/latest', (req, res) => {
  const db = getDB();
  const row = db.prepare("SELECT * FROM app_version WHERE status = 'current' ORDER BY id DESC LIMIT 1").get();
  if (!row) return res.json({ code: 404, data: null, message: '没有当前版本' });

  res.json({
    code: 0,
    data: { id: row.id, version: row.version, changelog: row.changelog, downloadUrl: row.download_url, status: row.status, createdAt: row.created_at },
    message: 'ok',
  });
});

module.exports = router;
