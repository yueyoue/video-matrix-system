<?php
require_once __DIR__ . '/../_helpers.php';
$method = $_SERVER['REQUEST_METHOD'];
$segments = getPathSegments();
$id = $segments[1] ?? null;

switch ($method) {
    case 'GET':
        adminOnly();
        [$page, $pageSize, $offset] = getPageParams();
        $where = "1=1"; $params = [];
        if ($keyword = param('keyword')) { $where .= " AND username LIKE ?"; $params[] = "%$keyword%"; }
        if ($role = param('role')) { $where .= " AND role = ?"; $params[] = $role; }
        if ($status = param('status')) { $where .= " AND status = ?"; $params[] = $status; }
        $stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('sys_user') . " WHERE $where");
        $stmt->execute($params); $total = $stmt->fetchColumn();
        $stmt = $pdo->prepare("SELECT id, username, role, daily_quota, used_quota, status, last_login, created_at FROM " . table('sys_user') . " WHERE $where ORDER BY id DESC LIMIT $pageSize OFFSET $offset");
        $stmt->execute($params);
        paginate($stmt->fetchAll(), $total, $page, $pageSize);
        break;

    case 'POST':
        adminOnly();
        $input = getJsonInput();
        $username = trim($input['username'] ?? '');
        $password = $input['password'] ?? '';
        $role = $input['role'] ?? 'operator';
        $quota = (int)($input['daily_quota'] ?? 50);
        if (!$username || !$password) error('用户名和密码不能为空');
        if (strlen($password) < 6) error('密码长度不能少于6位');
        $hashed = password_hash($password, PASSWORD_DEFAULT);
        try {
            $pdo->prepare("INSERT INTO " . table('sys_user') . " (username, password, role, daily_quota) VALUES (?, ?, ?, ?)")
                ->execute([$username, $hashed, $role, $quota]);
        } catch (PDOException $e) {
            if ($e->getCode() == 23000) error('用户名已存在');
            throw $e;
        }
        $u = getCurrentUser();
        logOp($u['user_id'], $u['username'], 'INFO', '用户管理', '添加用户', "添加用户: $username");
        success(['id' => $pdo->lastInsertId()], '添加成功');
        break;

    case 'PUT':
        if (!$id) error('缺少用户ID');
        adminOnly();
        $input = getJsonInput();
        $sets = []; $params = [];
        if (isset($input['username'])) { $sets[] = "username = ?"; $params[] = $input['username']; }
        if (isset($input['role'])) { $sets[] = "role = ?"; $params[] = $input['role']; }
        if (isset($input['daily_quota'])) { $sets[] = "daily_quota = ?"; $params[] = (int)$input['daily_quota']; }
        if (isset($input['status'])) { $sets[] = "status = ?"; $params[] = $input['status']; }
        if (isset($input['password']) && $input['password']) { $sets[] = "password = ?"; $params[] = password_hash($input['password'], PASSWORD_DEFAULT); }
        if ($sets) { $params[] = $id; $pdo->prepare("UPDATE " . table('sys_user') . " SET " . implode(',', $sets) . " WHERE id = ?")->execute($params); }
        $u = getCurrentUser();
        logOp($u['user_id'], $u['username'], 'INFO', '用户管理', '更新用户', "更新用户ID: $id");
        success(null, '更新成功');
        break;

    case 'DELETE':
        if (!$id) error('缺少用户ID');
        adminOnly();
        $pdo->prepare("DELETE FROM " . table('sys_user') . " WHERE id = ?")->execute([$id]);
        $u = getCurrentUser();
        logOp($u['user_id'], $u['username'], 'INFO', '用户管理', '删除用户', "删除用户ID: $id");
        success(null, '删除成功');
        break;

    default:
        error('方法不允许', 405);
}
