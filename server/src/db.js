const initSqlJs = require('sql.js');
const path = require('path');
const fs = require('fs');
const bcrypt = require('bcryptjs');

const DB_PATH = path.join(__dirname, '..', 'data', 'app.db');
fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });

let db = null;

// Wrapper to match better-sqlite3 style API
class DBWrapper {
  constructor(sqlDb) {
    this._db = sqlDb;
  }

  prepare(sql) {
    const self = this;
    return {
      run(...params) {
        const stmt = self._db.prepare(sql);
        if (params.length > 0) stmt.bind(params);
        stmt.step();
        const changes = self._db.getRowsModified();
        stmt.free();
        return { changes, lastInsertRowid: self._db.exec("SELECT last_insert_rowid()")[0]?.values[0]?.[0] || 0 };
      },
      get(...params) {
        const stmt = self._db.prepare(sql);
        if (params.length > 0) stmt.bind(params);
        const cols = stmt.getColumnNames();
        if (stmt.step()) {
          const vals = stmt.get();
          stmt.free();
          const row = {};
          cols.forEach((c, i) => { row[c] = vals[i]; });
          return row;
        }
        stmt.free();
        return undefined;
      },
      all(...params) {
        const stmt = self._db.prepare(sql);
        if (params.length > 0) stmt.bind(params);
        const cols = stmt.getColumnNames();
        const rows = [];
        while (stmt.step()) {
          const vals = stmt.get();
          const row = {};
          cols.forEach((c, i) => { row[c] = vals[i]; });
          rows.push(row);
        }
        stmt.free();
        return rows;
      },
    };
  }

  exec(sql) {
    return this._db.exec(sql);
  }

  pragma(str) {
    this._db.run(`PRAGMA ${str}`);
  }

  save() {
    const data = this._db.export();
    const buffer = Buffer.from(data);
    fs.writeFileSync(DB_PATH, buffer);
  }
}

async function initDB() {
  const SQL = await initSqlJs();

  let sqlDb;
  if (fs.existsSync(DB_PATH)) {
    const fileBuffer = fs.readFileSync(DB_PATH);
    sqlDb = new SQL.Database(fileBuffer);
  } else {
    sqlDb = new SQL.Database();
  }

  db = new DBWrapper(sqlDb);
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');

  // Schema
  db.exec(`
    CREATE TABLE IF NOT EXISTS sys_user (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'operator' CHECK(role IN ('admin','operator')),
      daily_quota INTEGER NOT NULL DEFAULT 50,
      used_quota INTEGER NOT NULL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','disabled')),
      last_login TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS platform_account (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      platform TEXT NOT NULL CHECK(platform IN ('douyin','kuaishou','xiaohongshu','weixin')),
      nickname TEXT NOT NULL,
      avatar_url TEXT,
      cookie TEXT,
      status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','expired')),
      works_count INTEGER NOT NULL DEFAULT 0,
      total_plays INTEGER NOT NULL DEFAULT 0,
      today_publish INTEGER NOT NULL DEFAULT 0,
      last_login TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS video_task (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      file_name TEXT NOT NULL,
      file_path TEXT NOT NULL,
      file_size INTEGER NOT NULL DEFAULT 0,
      duration REAL DEFAULT 0,
      type TEXT NOT NULL CHECK(type IN ('cut','mix')),
      status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','processing','done','failed')),
      source_ids TEXT DEFAULT '[]',
      config TEXT DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS publish_record (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      account_id INTEGER NOT NULL,
      video_id INTEGER,
      platform TEXT NOT NULL,
      account_name TEXT NOT NULL,
      video_title TEXT,
      scheduled_time TEXT,
      published_time TEXT,
      status TEXT NOT NULL DEFAULT 'waiting' CHECK(status IN ('waiting','publishing','success','failed')),
      error_msg TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS video_data (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      publish_id INTEGER,
      platform TEXT NOT NULL,
      account_name TEXT NOT NULL,
      video_title TEXT,
      plays INTEGER NOT NULL DEFAULT 0,
      likes INTEGER NOT NULL DEFAULT 0,
      comments INTEGER NOT NULL DEFAULT 0,
      shares INTEGER NOT NULL DEFAULT 0,
      publish_time TEXT,
      synced_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS ai_voice (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      voice_id TEXT NOT NULL,
      type TEXT NOT NULL CHECK(type IN ('male','female')),
      scene TEXT,
      status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','disabled')),
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS ai_config (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      provider TEXT NOT NULL,
      app_id TEXT,
      secret_key TEXT,
      daily_limit INTEGER NOT NULL DEFAULT 100,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS platform_config (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      platform TEXT NOT NULL UNIQUE,
      config_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS app_version (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      version TEXT NOT NULL,
      changelog TEXT,
      download_url TEXT,
      status TEXT NOT NULL DEFAULT 'current' CHECK(status IN ('current','archived','delisted')),
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS operation_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      username TEXT,
      level TEXT NOT NULL DEFAULT 'INFO' CHECK(level IN ('INFO','WARN','ERROR')),
      module TEXT,
      action TEXT,
      detail TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
  `);

  seed(db);
  return db;
}

function seed(db) {
  const userCount = db.prepare('SELECT COUNT(*) as c FROM sys_user').get().c;
  if (userCount > 0) return;

  const now = new Date().toISOString().replace('T', ' ').slice(0, 19);

  const adminHash = bcrypt.hashSync('admin123', 10);
  const opHash = bcrypt.hashSync('123456', 10);

  const insertUser = db.prepare('INSERT INTO sys_user (username, password_hash, role, daily_quota, used_quota, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)');
  insertUser.run('admin', adminHash, 'admin', 999, 0, 'active', now, now);
  insertUser.run('operator1', opHash, 'operator', 50, 12, 'active', now, now);

  const insertAcct = db.prepare('INSERT INTO platform_account (user_id, platform, nickname, avatar_url, cookie, status, works_count, total_plays, today_publish, last_login, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)');
  insertAcct.run(1, 'douyin', '抖音小助手', 'https://example.com/avatar1.png', 'cookie_douyin_xxx', 'active', 128, 580000, 3, now, now);
  insertAcct.run(1, 'kuaishou', '快手达人', 'https://example.com/avatar2.png', 'cookie_kuaishou_xxx', 'active', 86, 320000, 2, now, now);
  insertAcct.run(2, 'xiaohongshu', '小红薯博主', 'https://example.com/avatar3.png', 'cookie_xhs_xxx', 'active', 65, 210000, 1, now, now);
  insertAcct.run(2, 'weixin', '微信视频号', 'https://example.com/avatar4.png', 'cookie_weixin_xxx', 'expired', 42, 95000, 0, now, now);
  insertAcct.run(1, 'douyin', '美食探店', 'https://example.com/avatar5.png', 'cookie_douyin_yyy', 'active', 200, 1200000, 5, now, now);

  const insertVideo = db.prepare('INSERT INTO video_task (user_id, file_name, file_path, file_size, duration, type, status, source_ids, config, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)');
  insertVideo.run(1, '原始素材01.mp4', '/uploads/raw01.mp4', 52428800, 120.5, 'cut', 'done', '[]', '{"trim":[0,60]}', now);
  insertVideo.run(1, '混剪合集.mp4', '/uploads/mix01.mp4', 104857600, 180.0, 'mix', 'done', '[1,2]', '{"transition":"fade"}', now);
  insertVideo.run(2, '产品展示.mp4', '/uploads/product.mp4', 31457280, 45.0, 'cut', 'processing', '[]', '{"trim":[5,40]}', now);
  insertVideo.run(1, '探店vlog.mp4', '/uploads/vlog.mp4', 73400320, 300.0, 'mix', 'pending', '[1,3]', '{"speed":1.5}', now);

  const insertPub = db.prepare('INSERT INTO publish_record (user_id, account_id, video_id, platform, account_name, video_title, scheduled_time, published_time, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)');
  insertPub.run(1, 1, 1, 'douyin', '抖音小助手', '今日美食推荐', now, now, 'success', now);
  insertPub.run(1, 2, 2, 'kuaishou', '快手达人', '快手好物分享', now, now, 'success', now);
  insertPub.run(2, 3, 3, 'xiaohongshu', '小红薯博主', '种草笔记视频', now, null, 'waiting', now);
  insertPub.run(1, 5, 1, 'douyin', '美食探店', '探店合集', now, now, 'success', now);
  insertPub.run(1, 1, 2, 'douyin', '抖音小助手', '混剪测试', now, null, 'failed', now);

  const insertData = db.prepare('INSERT INTO video_data (publish_id, platform, account_name, video_title, plays, likes, comments, shares, publish_time, synced_at) VALUES (?,?,?,?,?,?,?,?,?,?)');
  insertData.run(1, 'douyin', '抖音小助手', '今日美食推荐', 125000, 8200, 430, 1200, now, now);
  insertData.run(2, 'kuaishou', '快手达人', '快手好物分享', 68000, 3500, 210, 580, now, now);
  insertData.run(4, 'douyin', '美食探店', '探店合集', 310000, 21000, 1500, 4200, now, now);

  const insertVoice = db.prepare('INSERT INTO ai_voice (name, voice_id, type, scene, status, created_at) VALUES (?,?,?,?,?,?)');
  insertVoice.run('标准女声', 'voice_female_01', 'female', '通用', 'active', now);
  insertVoice.run('标准男声', 'voice_male_01', 'male', '通用', 'active', now);
  insertVoice.run('活力女声', 'voice_female_02', 'female', '带货', 'active', now);
  insertVoice.run('磁性男声', 'voice_male_02', 'male', '解说', 'active', now);
  insertVoice.run('甜美少女', 'voice_female_03', 'female', '种草', 'disabled', now);

  db.prepare('INSERT INTO ai_config (provider, app_id, secret_key, daily_limit, created_at, updated_at) VALUES (?,?,?,?,?,?)')
    .run('volcengine', 'app_test_001', 'sk_test_xxxxx', 200, now, now);

  const defaultConfigs = {
    douyin: { userAgent: 'Mozilla/5.0', retry: 3, timeout: 30000, publishInterval: 60 },
    kuaishou: { userAgent: 'Mozilla/5.0', retry: 3, timeout: 30000, publishInterval: 90 },
    xiaohongshu: { userAgent: 'Mozilla/5.0', retry: 2, timeout: 25000, publishInterval: 120 },
    weixin: { userAgent: 'Mozilla/5.0', retry: 2, timeout: 25000, publishInterval: 180 },
  };
  const insertPlatCfg = db.prepare('INSERT INTO platform_config (platform, config_json, created_at, updated_at) VALUES (?,?,?,?)');
  for (const [p, cfg] of Object.entries(defaultConfigs)) {
    insertPlatCfg.run(p, JSON.stringify(cfg), now, now);
  }

  const insertVer = db.prepare('INSERT INTO app_version (version, changelog, download_url, status, created_at) VALUES (?,?,?,?,?)');
  insertVer.run('1.0.0', '首次发布', 'https://example.com/download/v1.0.0.zip', 'archived', now);
  insertVer.run('1.1.0', '新增混剪功能\n优化发布流程', 'https://example.com/download/v1.1.0.zip', 'archived', now);
  insertVer.run('1.2.0', '新增AI配音\n数据统计增强\n修复已知bug', 'https://example.com/download/v1.2.0.zip', 'current', now);

  const insertLog = db.prepare('INSERT INTO operation_log (user_id, username, level, module, action, detail, created_at) VALUES (?,?,?,?,?,?,?)');
  insertLog.run(1, 'admin', 'INFO', '系统', '初始化', '系统初始化完成', now);
  insertLog.run(1, 'admin', 'INFO', '用户管理', '创建用户', '创建运营账号 operator1', now);
  insertLog.run(2, 'operator1', 'INFO', '平台账号', '添加账号', '添加抖音账号: 抖音小助手', now);
  insertLog.run(2, 'operator1', 'WARN', '发布', '发布失败', '账号cookie已过期，发布失败', now);
  insertLog.run(1, 'admin', 'ERROR', '系统', '同步异常', '数据同步超时', now);

  console.log('✅ Seed data inserted');
}

// Save DB to disk periodically and on exit
function saveDB() {
  if (db) db.save();
}

process.on('exit', saveDB);
process.on('SIGINT', () => { saveDB(); process.exit(); });
process.on('SIGTERM', () => { saveDB(); process.exit(); });

// Auto-save every 30 seconds
setInterval(saveDB, 30000);

module.exports = { initDB, getDB: () => db };
