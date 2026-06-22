const express = require('express');
const { getDB } = require('../db');
const { authMiddleware } = require('../middleware/auth');
const { logOperation } = require('../middleware/logger');

const router = express.Router();
router.use(authMiddleware);

const VALID_PLATFORMS = ['douyin', 'kuaishou', 'xiaohongshu', 'weixin'];
const DEFAULT_CONFIGS = {
  douyin: { userAgent: 'Mozilla/5.0', retry: 3, timeout: 30000, publishInterval: 60 },
  kuaishou: { userAgent: 'Mozilla/5.0', retry: 3, timeout: 30000, publishInterval: 90 },
  xiaohongshu: { userAgent: 'Mozilla/5.0', retry: 2, timeout: 25000, publishInterval: 120 },
  weixin: { userAgent: 'Mozilla/5.0', retry: 2, timeout: 25000, publishInterval: 180 },
};

// GET /api/platform-config/:platform
router.get('/:platform', (req, res) => {
  const { platform } = req.params;
  if (!VALID_PLATFORMS.includes(platform)) return res.json({ code: 400, data: null, message: '无效的平台' });

  const db = getDB();
  const row = db.prepare('SELECT * FROM platform_config WHERE platform = ?').get(platform);
  if (!row) return res.json({ code: 0, data: DEFAULT_CONFIGS[platform] || {}, message: 'ok' });

  res.json({ code: 0, data: { ...DEFAULT_CONFIGS[platform], ...JSON.parse(row.config_json) }, message: 'ok' });
});

// PUT /api/platform-config/:platform
router.put('/:platform', (req, res) => {
  const { platform } = req.params;
  if (!VALID_PLATFORMS.includes(platform)) return res.json({ code: 400, data: null, message: '无效的平台' });

  const db = getDB();
  const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
  const configJson = JSON.stringify(req.body);

  const existing = db.prepare('SELECT * FROM platform_config WHERE platform = ?').get(platform);
  if (existing) {
    db.prepare("UPDATE platform_config SET config_json = ?, updated_at = datetime('now') WHERE platform = ?").run(configJson, platform);
  } else {
    db.prepare('INSERT INTO platform_config (platform, config_json, created_at, updated_at) VALUES (?,?,?,?)').run(platform, configJson, now, now);
  }

  logOperation({ userId: req.user.id, username: req.user.username, module: '平台配置', action: '更新配置', detail: `更新 ${platform} 配置` });
  res.json({ code: 0, data: null, message: 'ok' });
});

// POST /api/platform-config/:platform/reset
router.post('/:platform/reset', (req, res) => {
  const { platform } = req.params;
  if (!VALID_PLATFORMS.includes(platform)) return res.json({ code: 400, data: null, message: '无效的平台' });

  const db = getDB();
  const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
  const configJson = JSON.stringify(DEFAULT_CONFIGS[platform] || {});

  const existing = db.prepare('SELECT * FROM platform_config WHERE platform = ?').get(platform);
  if (existing) {
    db.prepare("UPDATE platform_config SET config_json = ?, updated_at = datetime('now') WHERE platform = ?").run(configJson, platform);
  } else {
    db.prepare('INSERT INTO platform_config (platform, config_json, created_at, updated_at) VALUES (?,?,?,?)').run(platform, configJson, now, now);
  }

  logOperation({ userId: req.user.id, username: req.user.username, module: '平台配置', action: '恢复默认', detail: `恢复 ${platform} 默认配置` });
  res.json({ code: 0, data: DEFAULT_CONFIGS[platform] || {}, message: 'ok' });
});

module.exports = router;
