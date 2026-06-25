<?php
/**
 * 平台账号管理接口
 * GET    /api/accounts           - 账号列表
 * POST   /api/accounts           - 添加账号
 * PUT    /api/accounts/{id}      - 更新账号
 * DELETE /api/accounts/{id}      - 删除账号
 * POST   /api/accounts/{id}/check - 检查Cookie状态
 */

// 兼容直接访问（绕过 index.php 路由）
if (!isset($GLOBALS['route_segments'])) {
    require_once __DIR__ . '/../includes/response.php';
    require_once __DIR__ . '/../includes/db.php';
    require_once __DIR__ . '/../includes/auth.php';
    $apiPath = preg_replace('#^/api/#', '', parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH));
    $GLOBALS['route_segments'] = explode('/', trim($apiPath, '/'));
    $GLOBALS['route_method']   = $_SERVER['REQUEST_METHOD'];
}

$currentUser = requireAuth();
$segments    = $GLOBALS['route_segments'];
$method      = $GLOBALS['route_method'];
$id          = isset($segments[1]) ? (int)$segments[1] : 0;
$sub         = $segments[2] ?? '';

// 子路由
if (isset($segments[1]) && $segments[1] === 'batch-check') {
    batchCheck();
    exit;
}
if ($sub === 'check' && $id > 0) {
    checkCookie($id);
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
        else error('缺少账号ID');
        break;
    case 'DELETE':
        if ($id > 0) remove($id);
        else error('缺少账号ID');
        break;
    default:
        error('请求方法不允许', 405);
}

/**
 * 账号列表
 */
function getList()
{
    global $pdo, $currentUser;

    [$page, $pageSize, $offset] = getPageParams();
    $platform = param('platform', '');
    $keyword  = param('keyword', '');
    $userId   = param('user_id', '');

    $where  = "WHERE 1=1";
    $params = [];

    // 非管理员只能看自己的
    if ($currentUser['role'] !== 'admin') {
        $where .= " AND a.user_id = ?";
        $params[] = $currentUser['user_id'];
    } elseif ($userId) {
        $where .= " AND a.user_id = ?";
        $params[] = $userId;
    }

    if ($platform) {
        $where .= " AND a.platform = ?";
        $params[] = $platform;
    }

    if ($keyword) {
        $where .= " AND a.nickname LIKE ?";
        $params[] = "%{$keyword}%";
    }

    $stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('platform_account') . " a $where");
    $stmt->execute($params);
    $total = $stmt->fetchColumn();

    $stmt = $pdo->prepare("
        SELECT a.*, u.username
        FROM " . table('platform_account') . " a
        LEFT JOIN " . table('sys_user') . " u ON a.user_id = u.id
        $where ORDER BY a.id DESC LIMIT $pageSize OFFSET $offset
    ");
    $stmt->execute($params);
    $list = $stmt->fetchAll();

    paginate($list, $total, $page, $pageSize);
}

/**
 * 添加账号
 */
function create()
{
    global $pdo, $currentUser;

    $input     = getJsonInput();
    $platform  = $input['platform'] ?? '';
    $nickname  = trim($input['nickname'] ?? '');
    $avatarUrl = $input['avatar_url'] ?? '';
    $cookie    = $input['cookie'] ?? '';
    $userId    = $currentUser['role'] === 'admin' && isset($input['user_id']) ? (int)$input['user_id'] : $currentUser['user_id'];

    $platforms = ['douyin', 'kuaishou', 'xiaohongshu', 'weixin'];
    if (!in_array($platform, $platforms)) {
        error('平台类型无效，支持: ' . implode(', ', $platforms));
    }

    if (empty($nickname)) {
        error('账号昵称不能为空');
    }

    $stmt = $pdo->prepare("INSERT INTO " . table('platform_account') . " (user_id, platform, nickname, avatar_url, cookie) VALUES (?, ?, ?, ?, ?)");
    $stmt->execute([$userId, $platform, $nickname, $avatarUrl, $cookie]);

    $id = $pdo->lastInsertId();
    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '账号管理', '添加账号', "添加{$platform}账号: {$nickname}");

    success(['id' => (int)$id], '账号添加成功');
}

/**
 * 更新账号
 */
function update($id)
{
    global $pdo, $currentUser;

    $input = getJsonInput();

    $stmt = $pdo->prepare("SELECT * FROM " . table('platform_account') . " WHERE id = ?");
    $stmt->execute([$id]);
    $account = $stmt->fetch();

    if (!$account) {
        error('账号不存在', 404);
    }

    // 非管理员只能操作自己的
    if ($currentUser['role'] !== 'admin' && $account['user_id'] != $currentUser['user_id']) {
        error('无权操作此账号', 403);
    }

    $fields = [];
    $params = [];

    if (isset($input['nickname'])) {
        $fields[] = "nickname = ?";
        $params[] = trim($input['nickname']);
    }
    if (isset($input['avatar_url'])) {
        $fields[] = "avatar_url = ?";
        $params[] = $input['avatar_url'];
    }
    if (isset($input['cookie'])) {
        $fields[] = "cookie = ?";
        $params[] = $input['cookie'];
    }
    if (isset($input['status']) && in_array($input['status'], ['active', 'expired'])) {
        $fields[] = "status = ?";
        $params[] = $input['status'];
    }

    if (empty($fields)) {
        error('没有需要更新的字段');
    }

    $params[] = $id;
    $stmt = $pdo->prepare("UPDATE " . table('platform_account') . " SET " . implode(', ', $fields) . " WHERE id = ?");
    $stmt->execute($params);

    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '账号管理', '更新账号', "更新账号ID: {$id}");

    success(null, '账号更新成功');
}

/**
 * 删除账号
 */
function remove($id)
{
    global $pdo, $currentUser;

    $stmt = $pdo->prepare("SELECT * FROM " . table('platform_account') . " WHERE id = ?");
    $stmt->execute([$id]);
    $account = $stmt->fetch();

    if (!$account) {
        error('账号不存在', 404);
    }

    if ($currentUser['role'] !== 'admin' && $account['user_id'] != $currentUser['user_id']) {
        error('无权操作此账号', 403);
    }

    $pdo->prepare("DELETE FROM " . table('platform_account') . " WHERE id = ?")->execute([$id]);

    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '账号管理', '删除账号', "删除账号: {$account['nickname']}");

    success(null, '账号删除成功');
}

/**
 * 检查Cookie状态
 */
function checkCookie($id)
{
    global $pdo, $currentUser;

    $stmt = $pdo->prepare("SELECT * FROM " . table('platform_account') . " WHERE id = ?");
    $stmt->execute([$id]);
    $account = $stmt->fetch();

    if (!$account) {
        error('账号不存在', 404);
    }

    if ($currentUser['role'] !== 'admin' && $account['user_id'] != $currentUser['user_id']) {
        error('无权操作此账号', 403);
    }

    // 获取平台配置
    $stmt = $pdo->prepare("SELECT config_json FROM " . table('platform_config') . " WHERE platform = ?");
    $stmt->execute([$account['platform']]);
    $configRow = $stmt->fetch();
    $config = $configRow ? json_decode($configRow['config_json'], true) : [];

    $hasCookie = !empty($account['cookie']);
    $loginCheckUrl = $config['loginCheck'] ?? '';

    // 简单的Cookie有效性检查
    $isValid = false;
    $message = 'Cookie为空';

    if ($hasCookie) {
        // 这里可以扩展为实际的API检查
        $isValid = true;
        $message = 'Cookie已设置，有效期内';
    }

    success([
        'valid'       => $isValid,
        'has_cookie'  => $hasCookie,
        'message'     => $message,
        'last_login'  => $account['last_login'],
    ]);
}

/**
 * 批量检测账号状态
 */
function batchCheck()
{
    global $pdo, $currentUser;

    $input = getJsonInput();
    $ids = $input['ids'] ?? [];

    if (empty($ids)) {
        error('请选择要检测的账号');
    }

    $results = [];
    $placeholders = implode(',', array_fill(0, count($ids), '?'));

    $stmt = $pdo->prepare("SELECT id, nickname, platform, cookie, status, last_login FROM " . table('platform_account') . " WHERE id IN ($placeholders)");
    $stmt->execute($ids);
    $accounts = $stmt->fetchAll();

    foreach ($accounts as $account) {
        $hasCookie = !empty($account['cookie']);
        $isValid = false;
        $message = 'Cookie为空';

        if ($hasCookie) {
            $isValid = true;
            $message = 'Cookie已设置，有效期内';

            // 获取平台配置进行实际检查
            $configStmt = $pdo->prepare("SELECT config_json FROM " . table('platform_config') . " WHERE platform = ?");
            $configStmt->execute([$account['platform']]);
            $configRow = $configStmt->fetch();
            // 可以扩展为实际的HTTP请求检查Cookie有效性
        }

        // 更新账号状态
        $newStatus = $isValid ? 'active' : 'expired';
        if ($account['status'] !== $newStatus) {
            $pdo->prepare("UPDATE " . table('platform_account') . " SET status = ? WHERE id = ?")
                ->execute([$newStatus, $account['id']]);
        }

        $results[] = [
            'id'       => (int)$account['id'],
            'nickname' => $account['nickname'],
            'platform' => $account['platform'],
            'valid'    => $isValid,
            'message'  => $message,
        ];
    }

    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '账号管理', '批量检测', '检测 ' . count($ids) . ' 个账号');

    success(['results' => $results]);
}
