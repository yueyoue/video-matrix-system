const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const { authMiddleware } = require('../middleware/auth');
const { logOperation } = require('../middleware/logger');

const router = express.Router();

const UPLOAD_DIR = path.join(__dirname, '..', '..', 'uploads');
fs.mkdirSync(UPLOAD_DIR, { recursive: true });

const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, UPLOAD_DIR),
  filename: (req, file, cb) => {
    const ext = path.extname(file.originalname);
    const name = Date.now() + '-' + Math.random().toString(36).slice(2, 8) + ext;
    cb(null, name);
  },
});

const upload = multer({
  storage,
  limits: { fileSize: 500 * 1024 * 1024 }, // 500MB
  fileFilter: (req, file, cb) => {
    const allowed = ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.jpg', '.jpeg', '.png', '.gif', '.webp'];
    const ext = path.extname(file.originalname).toLowerCase();
    if (allowed.includes(ext)) {
      cb(null, true);
    } else {
      cb(new Error('不支持的文件类型'));
    }
  },
});

// POST /api/upload
router.post('/', authMiddleware, upload.single('file'), (req, res) => {
  if (!req.file) {
    return res.json({ code: 400, data: null, message: '没有上传文件' });
  }

  const fileInfo = {
    fileName: req.file.originalname,
    filePath: '/uploads/' + req.file.filename,
    fileSize: req.file.size,
    mimeType: req.file.mimetype,
  };

  logOperation({ userId: req.user.id, username: req.user.username, module: '文件上传', action: '上传文件', detail: `${req.file.originalname} (${(req.file.size / 1024 / 1024).toFixed(2)}MB)` });

  res.json({ code: 0, data: fileInfo, message: 'ok' });
});

module.exports = router;
