<?php
/**
 * 用户管理接口（管理员）
 * GET    /api/users           - 用户列表
 * POST   /api/users           - 创建用户
 * PUT    /api/users/{id}      - 更新用户
 * DELETE /api/users/{id}      - 删除用户
 * POST   /api/users/{id}/reset - 重置密码
 */

require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/auth.php';

adminOnly();

$segments = $GLOBALS['route_segments'];
$method   = $GLOBALS['route_method'];
$id       = isset($segments[1]) ? (int)$segments[1] : 0;
$sub      = $segments[2] ?? '';

// 处理子路由
if ($sub === 'reset' && $id > 0) {
    resetPassword($id);
    exit;
}

switch ($method) {
    case 'GET':
        getList();
        break;
    case 'POST':
        create();
        break;
    case 'PUT':
        if ($id > 0) update($id);
        else error('缺少用户ID');
        break;
    case 'DELETE':
        if ($id > 0) remove($id);
        else error('缺少用户ID');
        break;
    default:
        error('请求方法不允许', 405);
}

/**
 * 用户列表
 */
function getList()
{
    global $pdo;

    [$page, $pageSize, $offset] = getPageParams();
    $keyword = param('keyword', '');
    $status  = param('status', '');

    $where  = "WHERE 1=1";
    $params = [];

    if ($keyword) {
        $where .= " AND username LIKE ?";
        $params[] = "%{$keyword}%";
    }

    if ($status) {
        $where .= " AND status = ?";
        $params[] = $status;
    }

    // 总数
    $stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('sys_user') . " $where");
    $stmt->execute($params);
    $total = $stmt->fetchColumn();

    // 列表
    $stmt = $pdo->prepare("SELECT id, username, role, daily_quota, used_quota, status, last_login, created_at FROM " . table('sys_user') . " $where ORDER BY id DESC LIMIT $pageSize OFFSET $offset");
    $stmt->execute($params);
    $list = $stmt->fetchAll();

    paginate($list, $total, $page, $pageSize);
}

/**
 * 创建用户
 */
function create()
{
    global $pdo;

    $input     = getJsonInput();
    $username  = trim($input['username'] ?? '');
    $password  = $input['password'] ?? '';
    $role      = $input['role'] ?? 'operator';
    $dailyQuota = (int)($input['daily_quota'] ?? 50);

    if (empty($username) || empty($password)) {
        error('用户名和密码不能为空');
    }

    if (strlen($password) < 6) {
        error('密码长度不能少于6位');
    }

    if (!in_array($role, ['admin', 'operator'])) {
        error('角色类型无效');
    }

    // 检查用户名是否存在
    $stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('sys_user') . " WHERE username = ?");
    $stmt->execute([$username]);
    if ($stmt->fetchColumn() > 0) {
        error('用户名已存在');
    }

    $hashed = password_hash($password, PASSWORD_DEFAULT);

    $stmt = $pdo->prepare("INSERT INTO " . table('sys_user') . " (username, password, role, daily_quota) VALUES (?, ?, ?, ?)");
    $stmt->execute([$username, $hashed, $role, $dailyQuota]);

    $userId = $pdo->lastInsertId();

    $currentUser = getCurrentUser();
    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '用户管理', '创建用户', "创建用户: {$username}");

    success(['id' => (int)$userId], '用户创建成功');
}

/**
 * 更新用户
 */
function update($id)
{
    global $pdo;

    $input = getJsonInput();

    // 检查用户是否存在
    $stmt = $pdo->prepare("SELECT * FROM " . table('sys_user') . " WHERE id = ?");
    $stmt->execute([$id]);
    $user = $stmt->fetch();

    if (!$user) {
        error('用户不存在', 404);
    }

    $fields = [];
    $params = [];

    if (isset($input['role']) && in_array($input['role'], ['admin', 'operator'])) {
        $fields[] = "role = ?";
        $params[] = $input['role'];
    }

    if (isset($input['daily_quota'])) {
        $fields[] = "daily_quota = ?";
        $params[] = (int)$input['daily_quota'];
    }

    if (isset($input['status']) && in_array($input['status'], ['active', 'disabled'])) {
        $fields[] = "status = ?";
        $params[] = $input['status'];
    }

    if (isset($input['password']) && !empty($input['password'])) {
        if (strlen($input['password']) < 6) {
            error('密码长度不能少于6位');
        }
        $fields[] = "password = ?";
        $params[] = password_hash($input['password'], PASSWORD_DEFAULT);
    }

    if (empty($fields)) {
        error('没有需要更新的字段');
    }

    $params[] = $id;
    $stmt = $pdo->prepare("UPDATE " . table('sys_user') . " SET " . implode(', ', $fields) . " WHERE id = ?");
    $stmt->execute($params);

    $currentUser = getCurrentUser();
    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '用户管理', '更新用户', "更新用户ID: {$id}");

    success(null, '用户更新成功');
}

/**
 * 删除用户
 */
function remove($id)
{
    global $pdo;

    // 不能删除自己
    $currentUser = getCurrentUser();
    if ($currentUser['user_id'] == $id) {
        error('不能删除当前登录用户');
    }

    $stmt = $pdo->prepare("SELECT username FROM " . table('sys_user') . " WHERE id = ?");
    $stmt->execute([$id]);
    $user = $stmt->fetch();

    if (!$user) {
        error('用户不存在', 404);
    }

    // 删除用户及其关联数据
    $pdo->prepare("DELETE FROM " . table('platform_account') . " WHERE user_id = ?")->execute([$id]);
    $pdo->prepare("DELETE FROM " . table('video_task') . " WHERE user_id = ?")->execute([$id]);
    $pdo->prepare("DELETE FROM " . table('publish_record') . " WHERE user_id = ?")->execute([$id]);
    $pdo->prepare("DELETE FROM " . table('publish_rule') . " WHERE user_id = ?")->execute([$id]);
    $pdo->prepare("DELETE FROM " . table('sys_user') . " WHERE id = ?")->execute([$id]);

    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '用户管理', '删除用户', "删除用户: {$user['username']}");

    success(null, '用户删除成功');
}

/**
 * 重置密码
 */
function resetPassword($id)
{
    global $pdo;

    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        error('请求方法不允许', 405);
    }

    $input    = getJsonInput();
    $password = $input['password'] ?? '';

    if (empty($password) || strlen($password) < 6) {
        error('密码不能为空且长度不能少于6位');
    }

    $stmt = $pdo->prepare("SELECT username FROM " . table('sys_user') . " WHERE id = ?");
    $stmt->execute([$id]);
    $user = $stmt->fetch();

    if (!$user) {
        error('用户不存在', 404);
    }

    $hashed = password_hash($password, PASSWORD_DEFAULT);
    $stmt = $pdo->prepare("UPDATE " . table('sys_user') . " SET password = ? WHERE id = ?");
    $stmt->execute([$hashed, $id]);

    $currentUser = getCurrentUser();
    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '用户管理', '重置密码', "重置用户 {$user['username']} 的密码");

    success(null, '密码重置成功');
}
