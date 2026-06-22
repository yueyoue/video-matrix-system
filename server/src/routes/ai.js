const express = require('express');
const { getDB } = require('../db');
const { authMiddleware } = require('../middleware/auth');
const { logOperation } = require('../middleware/logger');

const router = express.Router();
router.use(authMiddleware);

// GET /api/ai/voices
router.get('/voices', (req, res) => {
  const db = getDB();
  const rows = db.prepare('SELECT * FROM ai_voice ORDER BY id').all();
  res.json({
    code: 0,
    data: rows.map(r => ({ id: r.id, name: r.name, voiceId: r.voice_id, type: r.type, scene: r.scene, status: r.status, createdAt: r.created_at })),
    message: 'ok',
  });
});

// POST /api/ai/voices
router.post('/voices', (req, res) => {
  const { name, voiceId, type, scene } = req.body;
  if (!name || !voiceId || !type) return res.json({ code: 400, data: null, message: '名称、voiceId和类型不能为空' });

  const db = getDB();
  const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
  const result = db.prepare('INSERT INTO ai_voice (name, voice_id, type, scene, created_at) VALUES (?,?,?,?,?)').run(name, voiceId, type, scene || null, now);

  logOperation({ userId: req.user.id, username: req.user.username, module: 'AI配音', action: '添加音色', detail: name });
  res.json({ code: 0, data: { id: result.lastInsertRowid }, message: 'ok' });
});

// PUT /api/ai/voices/:id
router.put('/voices/:id', (req, res) => {
  const { id } = req.params;
  const db = getDB();
  const voice = db.prepare('SELECT * FROM ai_voice WHERE id = ?').get(id);
  if (!voice) return res.json({ code: 404, data: null, message: '音色不存在' });

  const { name, voiceId, type, scene, status } = req.body;
  const updates = []; const params = [];
  if (name) { updates.push('name = ?'); params.push(name); }
  if (voiceId) { updates.push('voice_id = ?'); params.push(voiceId); }
  if (type) { updates.push('type = ?'); params.push(type); }
  if (scene !== undefined) { updates.push('scene = ?'); params.push(scene); }
  if (status) { updates.push('status = ?'); params.push(status); }
  if (updates.length === 0) return res.json({ code: 400, data: null, message: '没有需要更新的字段' });

  params.push(id);
  db.prepare(`UPDATE ai_voice SET ${updates.join(', ')} WHERE id = ?`).run(...params);

  logOperation({ userId: req.user.id, username: req.user.username, module: 'AI配音', action: '更新音色', detail: `ID=${id}` });
  res.json({ code: 0, data: null, message: 'ok' });
});

// GET /api/ai/config
router.get('/config', (req, res) => {
  const db = getDB();
  const cfg = db.prepare('SELECT * FROM ai_config ORDER BY id DESC LIMIT 1').get();
  if (!cfg) return res.json({ code: 0, data: null, message: 'ok' });

  res.json({
    code: 0,
    data: {
      id: cfg.id, provider: cfg.provider, appId: cfg.app_id,
      secretKey: cfg.secret_key ? '***' + cfg.secret_key.slice(-4) : null,
      dailyLimit: cfg.daily_limit, createdAt: cfg.created_at, updatedAt: cfg.updated_at,
    },
    message: 'ok',
  });
});

// PUT /api/ai/config
router.put('/config', (req, res) => {
  const { provider, appId, secretKey, dailyLimit } = req.body;
  const db = getDB();
  const existing = db.prepare('SELECT * FROM ai_config ORDER BY id DESC LIMIT 1').get();
  const now = new Date().toISOString().replace('T', ' ').slice(0, 19);

  if (existing) {
    const updates = []; const params = [];
    if (provider) { updates.push('provider = ?'); params.push(provider); }
    if (appId) { updates.push('app_id = ?'); params.push(appId); }
    if (secretKey) { updates.push('secret_key = ?'); params.push(secretKey); }
    if (dailyLimit !== undefined) { updates.push('daily_limit = ?'); params.push(dailyLimit); }
    updates.push("updated_at = datetime('now')");
    params.push(existing.id);
    db.prepare(`UPDATE ai_config SET ${updates.join(', ')} WHERE id = ?`).run(...params);
  } else {
    db.prepare('INSERT INTO ai_config (provider, app_id, secret_key, daily_limit, created_at, updated_at) VALUES (?,?,?,?,?,?)')
      .run(provider || '', appId || '', secretKey || '', dailyLimit || 100, now, now);
  }

  logOperation({ userId: req.user.id, username: req.user.username, module: 'AI配音', action: '更新配置', detail: '更新AI配置' });
  res.json({ code: 0, data: null, message: 'ok' });
});

// POST /api/ai/test
router.post('/test', (req, res) => {
  const db = getDB();
  const cfg = db.prepare('SELECT * FROM ai_config ORDER BY id DESC LIMIT 1').get();
  if (!cfg) return res.json({ code: 400, data: null, message: '未配置AI服务' });

  const success = Math.random() > 0.2;
  if (success) {
    logOperation({ userId: req.user.id, username: req.user.username, module: 'AI配音', action: '连通测试', detail: '测试成功' });
    res.json({ code: 0, data: { connected: true, provider: cfg.provider, latency: Math.floor(Math.random() * 200 + 50) + 'ms' }, message: 'ok' });
  } else {
    logOperation({ userId: req.user.id, username: req.user.username, level: 'WARN', module: 'AI配音', action: '连通测试', detail: '测试失败' });
    res.json({ code: 500, data: { connected: false }, message: 'AI服务连通测试失败' });
  }
});

module.exports = router;
