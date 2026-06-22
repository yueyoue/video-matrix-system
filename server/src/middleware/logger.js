const dbModule = require('../db');

function logOperation({ userId, username, level = 'INFO', module, action, detail }) {
  try {
    const db = dbModule.getDB();
    if (!db) return;
    db.prepare('INSERT INTO operation_log (user_id, username, level, module, action, detail) VALUES (?,?,?,?,?,?)')
      .run(userId || null, username || null, level, module, action, detail || null);
  } catch (e) {
    console.error('Log write failed:', e.message);
  }
}

module.exports = { logOperation };
