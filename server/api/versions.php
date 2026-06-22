<?php
/**
 * 版本管理接口
 * GET    /api/versions       - 版本列表
 * GET    /api/versions/current - 当前版本
 * POST   /api/versions       - 添加版本（管理员）
 * PUT    /api/versions/{id}  - 更新版本（管理员）
 * DELETE /api/versions/{id}  - 删除版本（管理员）
 */

require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/auth.php';

$currentUser = requireAuth();
$segments    = $GLOBALS['route_segments'];
$method      = $GLOBALS['route_method'];
$action      = $segments[1] ?? '';
$id          = is_numeric($action) ? (int)$action : 0;

if ($action === 'current') {
    getCurrent();
    exit;
}

if ($id > 0) {
    switch ($method) {
        case 'PUT':
            update($id);
            break;
        case 'DELETE':
            remove($id);
            break;
        default:
            error('请求方法不允许', 405);
    }
    exit;
}

switch ($method) {
    case 'GET':
        getList();
        break;
    case 'POST':
        create();
        break;
    default:
        error('请求方法不允许', 405);
}

/**
 * 版本列表
 */
function getList()
{
    global $pdo;

    [$page, $pageSize, $offset] = getPageParams();
    $status = param('status', '');

    $where  = "WHERE 1=1";
    $params = [];

    if ($status) {
        $where .= " AND status = ?";
        $params[] = $status;
    }

    $stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('app_version') . " $where");
    $stmt->execute($params);
    $total = $stmt->fetchColumn();

    $stmt = $pdo->prepare("SELECT * FROM " . table('app_version') . " $where ORDER BY id DESC LIMIT $pageSize OFFSET $offset");
    $stmt->execute($params);
    $list = $stmt->fetchAll();

    paginate($list, $total, $page, $pageSize);
}

/**
 * 获取当前版本
 */
function getCurrent()
{
    global $pdo;

    $stmt = $pdo->prepare("SELECT * FROM " . table('app_version') . " WHERE status = 'current' ORDER BY id DESC LIMIT 1");
    $stmt->execute();
    $version = $stmt->fetch();

    if (!$version) {
        success(null, '暂无版本信息');
    }

    success($version);
}

/**
 * 添加版本
 */
function create()
{
    global $pdo, $currentUser;

    adminOnly();

    $input      = getJsonInput();
    $version    = trim($input['version'] ?? '');
    $changelog  = $input['changelog'] ?? '';
    $downloadUrl = $input['download_url'] ?? '';

    if (empty($version)) {
        error('版本号不能为空');
    }

    // 检查版本号是否重复
    $stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('app_version') . " WHERE version = ?");
    $stmt->execute([$version]);
    if ($stmt->fetchColumn() > 0) {
        error('版本号已存在');
    }

    $stmt = $pdo->prepare("INSERT INTO " . table('app_version') . " (version, changelog, download_url) VALUES (?, ?, ?)");
    $stmt->execute([$version, $changelog, $downloadUrl]);

    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '版本管理', '添加版本', "添加版本: {$version}");

    success(['id' => (int)$pdo->lastInsertId()], '版本添加成功');
}

/**
 * 更新版本
 */
function update($id)
{
    global $pdo, $currentUser;

    adminOnly();

    $input = getJsonInput();

    $fields = [];
    $params = [];

    if (isset($input['version'])) {
        $fields[] = "version = ?";
        $params[] = trim($input['version']);
    }
    if (isset($input['changelog'])) {
        $fields[] = "changelog = ?";
        $params[] = $input['changelog'];
    }
    if (isset($input['download_url'])) {
        $fields[] = "download_url = ?";
        $params[] = $input['download_url'];
    }
    if (isset($input['status']) && in_array($input['status'], ['current', 'archived', 'delisted'])) {
        // 如果设置为current，先把其他的改为archived
        if ($input['status'] === 'current') {
            $pdo->prepare("UPDATE " . table('app_version') . " SET status = 'archived' WHERE status = 'current'")->execute();
        }
        $fields[] = "status = ?";
        $params[] = $input['status'];
    }

    if (empty($fields)) {
        error('没有需要更新的字段');
    }

    $params[] = $id;
    $stmt = $pdo->prepare("UPDATE " . table('app_version') . " SET " . implode(', ', $fields) . " WHERE id = ?");
    $stmt->execute($params);

    success(null, '版本更新成功');
}

/**
 * 删除版本
 */
function remove($id)
{
    global $pdo, $currentUser;

    adminOnly();

    $stmt = $pdo->prepare("SELECT version FROM " . table('app_version') . " WHERE id = ?");
    $stmt->execute([$id]);
    $version = $stmt->fetch();

    if (!$version) {
        error('版本不存在', 404);
    }

    $pdo->prepare("DELETE FROM " . table('app_version') . " WHERE id = ?")->execute([$id]);

    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '版本管理', '删除版本', "删除版本: {$version['version']}");

    success(null, '版本删除成功');
}
