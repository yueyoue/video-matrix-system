const jwt = require('jsonwebtoken');

const JWT_SECRET = process.env.JWT_SECRET || 'video-matrix-secret-key-2024';
const JWT_EXPIRES = '7d';

function signToken(payload) {
  return jwt.sign(payload, JWT_SECRET, { expiresIn: JWT_EXPIRES });
}

function authMiddleware(req, res, next) {
  const header = req.headers.authorization;
  if (!header || !header.startsWith('Bearer ')) {
    return res.status(401).json({ code: 401, data: null, message: '未登录或token无效' });
  }
  try {
    const token = header.slice(7);
    const decoded = jwt.verify(token, JWT_SECRET);
    req.user = decoded;
    next();
  } catch (err) {
    return res.status(401).json({ code: 401, data: null, message: 'token已过期或无效' });
  }
}

function adminOnly(req, res, next) {
  if (req.user.role !== 'admin') {
    return res.status(403).json({ code: 403, data: null, message: '需要管理员权限' });
  }
  next();
}

module.exports = { signToken, authMiddleware, adminOnly, JWT_SECRET };
