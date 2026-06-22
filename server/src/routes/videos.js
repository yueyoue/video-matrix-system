const express = require('express');
const { getDB } = require('../db');
const { authMiddleware } = require('../middleware/auth');
const { logOperation } = require('../middleware/logger');

const router = express.Router();
router.use(authMiddleware);

// GET /api/videos
router.get('/', (req, res) => {
  const { page = 1, pageSize = 20, type, status } = req.query;
  const p = Math.max(1, parseInt(page));
  const ps = Math.max(1, Math.min(100, parseInt(pageSize)));
  const offset = (p - 1) * ps;

  const db = getDB();
  let where = '1=1';
  const params = [];
  if (type) { where += ' AND type = ?'; params.push(type); }
  if (status) { where += ' AND status = ?'; params.push(status); }
  if (req.user.role !== 'admin') { where += ' AND user_id = ?'; params.push(req.user.id); }

  const total = db.prepare(`SELECT COUNT(*) as c FROM video_task WHERE ${where}`).get(...params).c;
  const rows = db.prepare(`SELECT * FROM video_task WHERE ${where} ORDER BY id DESC LIMIT ? OFFSET ?`).all(...params, ps, offset);

  res.json({
    code: 0,
    data: {
      list: rows.map(r => ({
        id: r.id, userId: r.user_id, fileName: r.file_name, filePath: r.file_path,
        fileSize: r.file_size, duration: r.duration, type: r.type, status: r.status,
        sourceIds: JSON.parse(r.source_ids || '[]'), config: JSON.parse(r.config || '{}'),
        createdAt: r.created_at,
      })),
      total, page: p, pageSize: ps,
    },
    message: 'ok',
  });
});

// POST /api/videos/cut
router.post('/cut', (req, res) => {
  const { fileName, filePath, fileSize, duration, config } = req.body;
  if (!fileName || !filePath) return res.json({ code: 400, data: null, message: '文件信息不完整' });

  const db = getDB();
  const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
  const result = db.prepare('INSERT INTO video_task (user_id, file_name, file_path, file_size, duration, type, status, config, created_at) VALUES (?,?,?,?,?,?,?,?,?)')
    .run(req.user.id, fileName, filePath, fileSize || 0, duration || 0, 'cut', 'pending', JSON.stringify(config || {}), now);

  logOperation({ userId: req.user.id, username: req.user.username, module: '视频任务', action: '创建裁切任务', detail: fileName });
  res.json({ code: 0, data: { id: result.lastInsertRowid }, message: 'ok' });
});

// POST /api/videos/mix
router.post('/mix', (req, res) => {
  const { fileName, filePath, fileSize, duration, sourceIds, config } = req.body;
  if (!fileName || !filePath) return res.json({ code: 400, data: null, message: '文件信息不完整' });

  const db = getDB();
  const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
  const result = db.prepare('INSERT INTO video_task (user_id, file_name, file_path, file_size, duration, type, status, source_ids, config, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)')
    .run(req.user.id, fileName, filePath, fileSize || 0, duration || 0, 'mix', 'pending', JSON.stringify(sourceIds || []), JSON.stringify(config || {}), now);

  logOperation({ userId: req.user.id, username: req.user.username, module: '视频任务', action: '创建混剪任务', detail: fileName });
  res.json({ code: 0, data: { id: result.lastInsertRowid }, message: 'ok' });
});

// DELETE /api/videos/:id
router.delete('/:id', (req, res) => {
  const { id } = req.params;
  const db = getDB();
  const task = db.prepare('SELECT * FROM video_task WHERE id = ?').get(id);
  if (!task) return res.json({ code: 404, data: null, message: '任务不存在' });
  if (req.user.role !== 'admin' && task.user_id !== req.user.id) return res.json({ code: 403, data: null, message: '无权操作' });

  db.prepare('DELETE FROM video_task WHERE id = ?').run(id);
  logOperation({ userId: req.user.id, username: req.user.username, module: '视频任务', action: '删除任务', detail: `删除任务 ID=${id}` });
  res.json({ code: 0, data: null, message: 'ok' });
});

module.exports = router;
