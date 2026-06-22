const express = require('express');
const { getDB } = require('../db');
const { authMiddleware } = require('../middleware/auth');

const router = express.Router();
router.use(authMiddleware);

// GET /api/stats/overview
router.get('/overview', (req, res) => {
  const db = getDB();
  const totalAccounts = db.prepare('SELECT COUNT(*) as c FROM platform_account').get().c;
  const activeAccounts = db.prepare("SELECT COUNT(*) as c FROM platform_account WHERE status = 'active'").get().c;
  const todayPublish = db.prepare('SELECT COALESCE(SUM(today_publish),0) as c FROM platform_account').get().c;
  const totalPlays = db.prepare('SELECT COALESCE(SUM(plays),0) as c FROM video_data').get().c;
  const totalLikes = db.prepare('SELECT COALESCE(SUM(likes),0) as c FROM video_data').get().c;
  const totalComments = db.prepare('SELECT COALESCE(SUM(comments),0) as c FROM video_data').get().c;
  const totalShares = db.prepare('SELECT COALESCE(SUM(shares),0) as c FROM video_data').get().c;
  const pendingPublish = db.prepare("SELECT COUNT(*) as c FROM publish_record WHERE status = 'waiting'").get().c;
  const successPublish = db.prepare("SELECT COUNT(*) as c FROM publish_record WHERE status = 'success'").get().c;
  const failedPublish = db.prepare("SELECT COUNT(*) as c FROM publish_record WHERE status = 'failed'").get().c;
  const totalVideos = db.prepare('SELECT COUNT(*) as c FROM video_task').get().c;
  const totalUsers = db.prepare('SELECT COUNT(*) as c FROM sys_user').get().c;

  res.json({
    code: 0,
    data: { totalAccounts, activeAccounts, todayPublish, totalPlays, totalLikes, totalComments, totalShares, pendingPublish, successPublish, failedPublish, totalVideos, totalUsers },
    message: 'ok',
  });
});

// GET /api/stats/users
router.get('/users', (req, res) => {
  const db = getDB();
  const rows = db.prepare(`
    SELECT u.id, u.username, u.role,
      COUNT(DISTINCT pa.id) as account_count,
      COALESCE(SUM(pa.works_count),0) as total_works,
      COALESCE(SUM(pa.total_plays),0) as total_plays,
      COUNT(DISTINCT pr.id) as publish_count
    FROM sys_user u
    LEFT JOIN platform_account pa ON pa.user_id = u.id
    LEFT JOIN publish_record pr ON pr.user_id = u.id
    GROUP BY u.id ORDER BY total_plays DESC
  `).all();

  res.json({
    code: 0,
    data: rows.map(r => ({
      id: r.id, username: r.username, role: r.role,
      accountCount: r.account_count, totalWorks: r.total_works,
      totalPlays: r.total_plays, publishCount: r.publish_count,
    })),
    message: 'ok',
  });
});

// GET /api/stats/platforms
router.get('/platforms', (req, res) => {
  const db = getDB();
  const rows = db.prepare(`
    SELECT platform, COUNT(*) as account_count,
      COALESCE(SUM(works_count),0) as total_works,
      COALESCE(SUM(total_plays),0) as total_plays,
      COALESCE(SUM(today_publish),0) as today_publish
    FROM platform_account GROUP BY platform
  `).all();

  res.json({
    code: 0,
    data: rows.map(r => ({
      platform: r.platform, accountCount: r.account_count,
      totalWorks: r.total_works, totalPlays: r.total_plays, todayPublish: r.today_publish,
    })),
    message: 'ok',
  });
});

// GET /api/stats/analysis
router.get('/analysis', (req, res) => {
  const { startDate, endDate, platform, page = 1, pageSize = 20 } = req.query;
  const p = Math.max(1, parseInt(page));
  const ps = Math.max(1, Math.min(100, parseInt(pageSize)));
  const offset = (p - 1) * ps;

  const db = getDB();
  let where = '1=1';
  const params = [];
  if (startDate) { where += ' AND publish_time >= ?'; params.push(startDate); }
  if (endDate) { where += ' AND publish_time <= ?'; params.push(endDate + ' 23:59:59'); }
  if (platform) { where += ' AND platform = ?'; params.push(platform); }

  const total = db.prepare(`SELECT COUNT(*) as c FROM video_data WHERE ${where}`).get(...params).c;
  const rows = db.prepare(`SELECT * FROM video_data WHERE ${where} ORDER BY id DESC LIMIT ? OFFSET ?`).all(...params, ps, offset);

  res.json({
    code: 0,
    data: {
      list: rows.map(r => ({
        id: r.id, publishId: r.publish_id, platform: r.platform,
        accountName: r.account_name, videoTitle: r.video_title,
        plays: r.plays, likes: r.likes, comments: r.comments, shares: r.shares,
        publishTime: r.publish_time, syncedAt: r.synced_at,
      })),
      total, page: p, pageSize: ps,
    },
    message: 'ok',
  });
});

module.exports = router;
