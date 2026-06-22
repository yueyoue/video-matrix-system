<?php
/**
 * API 公共辅助函数（自包含，不依赖 index.php 路由）
 */

// CORS
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }

header('Content-Type: application/json; charset=utf-8');

// 配置 & 数据库
$config = require __DIR__ . '/../config.php';

try {
    $dsn = sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4', $config['db_host'], $config['db_port'], $config['db_name']);
    $pdo = new PDO($dsn, $config['db_user'], $config['db_pass'], [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]);
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['code' => 500, 'message' => '数据库连接失败', 'data' => null]);
    exit;
}

// ---------- 辅助函数 ----------

function table($t) { global $config; return $config['db_prefix'] . $t; }

function success($data = null, $msg = 'ok') {
    echo json_encode(['code' => 0, 'data' => $data, 'message' => $msg], JSON_UNESCAPED_UNICODE);
    exit;
}

function error($msg, $code = 400) {
    http_response_code($code);
    echo json_encode(['code' => $code, 'data' => null, 'message' => $msg], JSON_UNESCAPED_UNICODE);
    exit;
}

function getJsonInput() {
    $raw = file_get_contents('php://input');
    $d = json_decode($raw, true);
    return is_array($d) ? $d : [];
}

function param($key, $default = null) {
    return isset($_GET[$key]) ? $_GET[$key] : $default;
}

function getPageParams() {
    $page = max(1, (int)param('page', 1));
    $pageSize = min(100, max(1, (int)param('pageSize', 20)));
    return [$page, $pageSize, ($page - 1) * $pageSize];
}

function paginate($list, $total, $page = 1, $pageSize = 20) {
    success(['list' => $list, 'total' => (int)$total, 'page' => (int)$page, 'pageSize' => (int)$pageSize, 'pages' => ceil($total / $pageSize)]);
}

// ---------- JWT ----------

function jwtEncode($payload, $expire = 86400) {
    global $config;
    $header = rtrim(strtr(base64_encode(json_encode(['typ'=>'JWT','alg'=>'HS256'])), '+/', '-_'), '=');
    $payload['iat'] = time();
    $payload['exp'] = time() + $expire;
    $pe = rtrim(strtr(base64_encode(json_encode($payload)), '+/', '-_'), '=');
    $sig = rtrim(strtr(base64_encode(hash_hmac('sha256', "$header.$pe", $config['jwt_secret'], true)), '+/', '-_'), '=');
    return "$header.$pe.$sig";
}

function jwtDecode($token) {
    global $config;
    $parts = explode('.', $token);
    if (count($parts) !== 3) return null;
    [$h, $p, $s] = $parts;
    $expected = rtrim(strtr(base64_encode(hash_hmac('sha256', "$h.$p", $config['jwt_secret'], true)), '+/', '-_'), '=');
    if (!hash_equals($expected, $s)) return null;
    $data = json_decode(base64_decode(strtr($p, '-_', '+/')), true);
    if (!$data || (isset($data['exp']) && $data['exp'] < time())) return null;
    return $data;
}

function getCurrentUser() {
    static $user = null;
    if ($user !== null) return $user;
    $auth = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
    if (!preg_match('/^Bearer\s+(.+)$/i', $auth, $m)) error('未提供认证Token', 401);
    $payload = jwtDecode($m[1]);
    if (!$payload) error('Token无效或已过期', 401);
    $user = ['user_id' => $payload['user_id'], 'username' => $payload['username'], 'role' => $payload['role']];
    return $user;
}

function requireAuth() { return getCurrentUser(); }

function adminOnly() {
    $u = getCurrentUser();
    if ($u['role'] !== 'admin') error('权限不足', 403);
}

function logOp($uid, $uname, $level, $module, $action, $detail = '') {
    global $pdo;
    try {
        $pdo->prepare("INSERT INTO " . table('operation_log') . " (user_id,username,level,module,action,detail) VALUES (?,?,?,?,?,?)")
            ->execute([$uid, $uname, $level, $module, $action, $detail]);
    } catch (Exception $e) { /* 忽略 */ }
}

/**
 * 从 URL 路径提取动态段
 * 例如 /api/users/5 → ['users','5']
 */
function getPathSegments() {
    $path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
    // 去掉 /api/ 前缀
    $path = preg_replace('#^/api/#', '', $path);
    return array_values(array_filter(explode('/', trim($path, '/'))));
}
