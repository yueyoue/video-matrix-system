<?php
/**
 * 认证接口
 * POST /api/auth/login     - 登录
 * GET  /api/auth/info      - 获取当前用户信息
 * POST /api/auth/password  - 修改密码
 */

require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/auth.php';

$segments = $GLOBALS['route_segments'];
$method   = $GLOBALS['route_method'];
$action   = $segments[1] ?? 'login';

switch ($action) {
    case 'login':
        handleLogin();
        break;
    case 'info':
        handleInfo();
        break;
    case 'password':
        handlePassword();
        break;
    default:
        error('接口不存在', 404);
}

/**
 * 登录
 */
function handleLogin()
{
    global $pdo;

    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        error('请求方法不允许', 405);
    }

    $input    = getJsonInput();
    $username = trim($input['username'] ?? '');
    $password = $input['password'] ?? '';

    if (empty($username) || empty($password)) {
        error('用户名和密码不能为空');
    }

    $stmt = $pdo->prepare("SELECT * FROM " . table('sys_user') . " WHERE username = ?");
    $stmt->execute([$username]);
    $user = $stmt->fetch();

    if (!$user) {
        error('用户名或密码错误');
    }

    if ($user['status'] === 'disabled') {
        error('账号已被禁用');
    }

    if (!password_verify($password, $user['password'])) {
        error('用户名或密码错误');
    }

    // 更新最后登录时间
    $stmt = $pdo->prepare("UPDATE " . table('sys_user') . " SET last_login = NOW() WHERE id = ?");
    $stmt->execute([$user['id']]);

    // 生成Token
    $token = jwtEncode([
        'user_id'  => $user['id'],
        'username' => $user['username'],
        'role'     => $user['role'],
    ]);

    // 记录日志
    logOperation($user['id'], $user['username'], 'INFO', '用户登录', '登录', '登录成功');

    success([
        'token'    => $token,
        'userInfo' => [
            'id'          => $user['id'],
            'username'    => $user['username'],
            'role'        => $user['role'],
            'daily_quota' => $user['daily_quota'],
            'used_quota'  => $user['used_quota'],
        ]
    ], '登录成功');
}

/**
 * 获取当前用户信息
 */
function handleInfo()
{
    global $pdo;

    $currentUser = requireAuth();

    $stmt = $pdo->prepare("SELECT id, username, role, daily_quota, used_quota, status, last_login, created_at FROM " . table('sys_user') . " WHERE id = ?");
    $stmt->execute([$currentUser['user_id']]);
    $user = $stmt->fetch();

    if (!$user) {
        error('用户不存在', 404);
    }

    success($user);
}

/**
 * 修改密码
 */
function handlePassword()
{
    global $pdo;

    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        error('请求方法不允许', 405);
    }

    $currentUser = requireAuth();
    $input       = getJsonInput();
    $oldPassword = $input['old_password'] ?? '';
    $newPassword = $input['new_password'] ?? '';

    if (empty($oldPassword) || empty($newPassword)) {
        error('旧密码和新密码不能为空');
    }

    if (strlen($newPassword) < 6) {
        error('新密码长度不能少于6位');
    }

    $stmt = $pdo->prepare("SELECT password FROM " . table('sys_user') . " WHERE id = ?");
    $stmt->execute([$currentUser['user_id']]);
    $user = $stmt->fetch();

    if (!password_verify($oldPassword, $user['password'])) {
        error('旧密码不正确');
    }

    $hashed = password_hash($newPassword, PASSWORD_DEFAULT);
    $stmt = $pdo->prepare("UPDATE " . table('sys_user') . " SET password = ? WHERE id = ?");
    $stmt->execute([$hashed, $currentUser['user_id']]);

    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '用户管理', '修改密码', '密码修改成功');

    success(null, '密码修改成功');
}
