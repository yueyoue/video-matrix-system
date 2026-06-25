<?php
/**
 * 发布调度接口
 * GET    /api/publish          - 发布记录列表
 * POST   /api/publish          - 创建发布任务
 * PUT    /api/publish/{id}     - 更新发布状态
 * DELETE /api/publish/{id}     - 取消发布
 * GET    /api/publish/rules    - 发布规则
 * POST   /api/publish/rules    - 保存发布规则
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
$action      = $segments[1] ?? '';
$id          = is_numeric($action) ? (int)$action : 0;

// 子路由
if ($action === 'rules') {
    handleRules();
    exit;
}

if ($id > 0) {
    switch ($method) {
        case 'PUT':
            updateStatus($id);
            break;
        case 'DELETE':
            cancel($id);
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
 * 发布记录列表
 */
function getList()
{
    global $pdo, $currentUser;

    [$page, $pageSize, $offset] = getPageParams();
    $status   = param('status', '');
    $platform = param('platform', '');
    $userId   = param('user_id', '');

    $where  = "WHERE 1=1";
    $params = [];

    if ($currentUser['role'] !== 'admin') {
        $where .= " AND p.user_id = ?";
        $params[] = $currentUser['user_id'];
    } elseif ($userId) {
        $where .= " AND p.user_id = ?";
        $params[] = $userId;
    }

    if ($status) {
        $where .= " AND p.status = ?";
        $params[] = $status;
    }

    if ($platform) {
        $where .= " AND p.platform = ?";
        $params[] = $platform;
    }

    $stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('publish_record') . " p $where");
    $stmt->execute($params);
    $total = $stmt->fetchColumn();

    $stmt = $pdo->prepare("
        SELECT p.*, u.username
        FROM " . table('publish_record') . " p
        LEFT JOIN " . table('sys_user') . " u ON p.user_id = u.id
        $where ORDER BY p.scheduled_time DESC LIMIT $pageSize OFFSET $offset
    ");
    $stmt->execute($params);
    $list = $stmt->fetchAll();

    paginate($list, $total, $page, $pageSize);
}

/**
 * 创建发布任务
 */
function create()
{
    global $pdo, $currentUser;

    $input = getJsonInput();

    $accountId    = (int)($input['account_id'] ?? 0);
    $videoId      = (int)($input['video_id'] ?? 0);
    $videoTitle   = trim($input['video_title'] ?? '');
    $scheduledTime = $input['scheduled_time'] ?? '';

    if (!$accountId) {
        error('请选择发布账号');
    }

    if (!$videoTitle) {
        error('请输入视频标题');
    }

    // 验证账号存在
    $stmt = $pdo->prepare("SELECT * FROM " . table('platform_account') . " WHERE id = ?");
    $stmt->execute([$accountId]);
    $account = $stmt->fetch();

    if (!$account) {
        error('账号不存在', 404);
    }

    if ($currentUser['role'] !== 'admin' && $account['user_id'] != $currentUser['user_id']) {
        error('无权使用此账号', 403);
    }

    // 验证视频存在
    if ($videoId) {
        $stmt = $pdo->prepare("SELECT * FROM " . table('video_task') . " WHERE id = ?");
        $stmt->execute([$videoId]);
        $video = $stmt->fetch();

        if (!$video) {
            error('视频不存在', 404);
        }
    }

    $stmt = $pdo->prepare("INSERT INTO " . table('publish_record') . " (user_id, account_id, video_id, platform, account_name, video_title, scheduled_time) VALUES (?, ?, ?, ?, ?, ?, ?)");
    $stmt->execute([
        $currentUser['user_id'],
        $accountId,
        $videoId ?: null,
        $account['platform'],
        $account['nickname'],
        $videoTitle,
        $scheduledTime ?: null
    ]);

    $publishId = $pdo->lastInsertId();

    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '发布模块', '创建发布', "创建发布任务: {$videoTitle} -> {$account['nickname']}");

    success(['id' => (int)$publishId], '发布任务创建成功');
}

/**
 * 更新发布状态
 */
function updateStatus($id)
{
    global $pdo, $currentUser;

    $input = getJsonInput();
    $status = $input['status'] ?? '';
    $errorMsg = $input['error_msg'] ?? '';

    $validStatuses = ['waiting', 'publishing', 'success', 'failed'];
    if (!in_array($status, $validStatuses)) {
        error('状态值无效');
    }

    $stmt = $pdo->prepare("SELECT * FROM " . table('publish_record') . " WHERE id = ?");
    $stmt->execute([$id]);
    $record = $stmt->fetch();

    if (!$record) {
        error('发布记录不存在', 404);
    }

    $fields = ["status = ?"];
    $params = [$status];

    if ($status === 'success') {
        $fields[] = "published_time = NOW()";
    }

    if ($status === 'failed' && $errorMsg) {
        $fields[] = "error_msg = ?";
        $params[] = $errorMsg;
    }

    $params[] = $id;
    $stmt = $pdo->prepare("UPDATE " . table('publish_record') . " SET " . implode(', ', $fields) . " WHERE id = ?");
    $stmt->execute($params);

    success(null, '状态更新成功');
}

/**
 * 取消发布
 */
function cancel($id)
{
    global $pdo, $currentUser;

    $stmt = $pdo->prepare("SELECT * FROM " . table('publish_record') . " WHERE id = ?");
    $stmt->execute([$id]);
    $record = $stmt->fetch();

    if (!$record) {
        error('发布记录不存在', 404);
    }

    if ($currentUser['role'] !== 'admin' && $record['user_id'] != $currentUser['user_id']) {
        error('无权操作此记录', 403);
    }

    if ($record['status'] !== 'waiting') {
        error('只能取消等待中的发布任务');
    }

    $pdo->prepare("DELETE FROM " . table('publish_record') . " WHERE id = ?")->execute([$id]);

    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '发布模块', '取消发布', "取消发布ID: {$id}");

    success(null, '发布已取消');
}

/**
 * 发布规则
 */
function handleRules()
{
    global $pdo, $currentUser;

    if ($_SERVER['REQUEST_METHOD'] === 'GET') {
        $stmt = $pdo->prepare("SELECT * FROM " . table('publish_rule') . " WHERE user_id = ?");
        $stmt->execute([$currentUser['user_id']]);
        $rules = $stmt->fetchAll();

        foreach ($rules as &$rule) {
            $rule['platforms']     = json_decode($rule['platforms'] ?? '[]', true);
            $rule['publish_times'] = json_decode($rule['publish_times'] ?? '[]', true);
        }

        success($rules);
    }

    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        $input = getJsonInput();

        $platforms    = $input['platforms'] ?? [];
        $dailyLimit   = (int)($input['daily_limit'] ?? 3);
        $publishTimes = $input['publish_times'] ?? [];
        $orderMode    = $input['order_mode'] ?? 'sequence';
        $autoRemove   = (int)($input['auto_remove'] ?? 1);

        // 检查是否已有规则
        $stmt = $pdo->prepare("SELECT id FROM " . table('publish_rule') . " WHERE user_id = ?");
        $stmt->execute([$currentUser['user_id']]);
        $existing = $stmt->fetch();

        if ($existing) {
            $stmt = $pdo->prepare("UPDATE " . table('publish_rule') . " SET platforms = ?, daily_limit = ?, publish_times = ?, order_mode = ?, auto_remove = ? WHERE user_id = ?");
            $stmt->execute([json_encode($platforms), $dailyLimit, json_encode($publishTimes), $orderMode, $autoRemove, $currentUser['user_id']]);
        } else {
            $stmt = $pdo->prepare("INSERT INTO " . table('publish_rule') . " (user_id, platforms, daily_limit, publish_times, order_mode, auto_remove) VALUES (?, ?, ?, ?, ?, ?)");
            $stmt->execute([$currentUser['user_id'], json_encode($platforms), $dailyLimit, json_encode($publishTimes), $orderMode, $autoRemove]);
        }

        logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '发布模块', '保存规则', '更新发布规则');

        success(null, '规则保存成功');
    }

    error('请求方法不允许', 405);
}
