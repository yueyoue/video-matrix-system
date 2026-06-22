<?php
/**
 * 系统日志接口
 * GET    /api/logs           - 日志列表
 * DELETE /api/logs           - 清空日志（管理员）
 * GET    /api/logs/export    - 导出日志（管理员）
 */

require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/auth.php';

$currentUser = requireAuth();
$segments    = $GLOBALS['route_segments'];
$method      = $GLOBALS['route_method'];
$action      = $segments[1] ?? '';

if ($action === 'export') {
    exportLogs();
    exit;
}

switch ($method) {
    case 'GET':
        getList();
        break;
    case 'DELETE':
        clearLogs();
        break;
    default:
        error('请求方法不允许', 405);
}

/**
 * 日志列表
 */
function getList()
{
    global $pdo, $currentUser;

    [$page, $pageSize, $offset] = getPageParams();
    $level   = param('level', '');
    $module  = param('module', '');
    $keyword = param('keyword', '');
    $dateStart = param('date_start', '');
    $dateEnd   = param('date_end', '');

    $where  = "WHERE 1=1";
    $params = [];

    // 非管理员只能看自己的日志
    if ($currentUser['role'] !== 'admin') {
        $where .= " AND user_id = ?";
        $params[] = $currentUser['user_id'];
    }

    if ($level) {
        $where .= " AND level = ?";
        $params[] = $level;
    }

    if ($module) {
        $where .= " AND module = ?";
        $params[] = $module;
    }

    if ($keyword) {
        $where .= " AND (action LIKE ? OR detail LIKE ?)";
        $params[] = "%{$keyword}%";
        $params[] = "%{$keyword}%";
    }

    if ($dateStart) {
        $where .= " AND created_at >= ?";
        $params[] = $dateStart . ' 00:00:00';
    }

    if ($dateEnd) {
        $where .= " AND created_at <= ?";
        $params[] = $dateEnd . ' 23:59:59';
    }

    $stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('operation_log') . " $where");
    $stmt->execute($params);
    $total = $stmt->fetchColumn();

    $stmt = $pdo->prepare("SELECT * FROM " . table('operation_log') . " $where ORDER BY id DESC LIMIT $pageSize OFFSET $offset");
    $stmt->execute($params);
    $list = $stmt->fetchAll();

    // 获取模块列表（用于筛选）
    $stmt = $pdo->prepare("SELECT DISTINCT module FROM " . table('operation_log') . " ORDER BY module");
    $stmt->execute();
    $modules = $stmt->fetchAll(PDO::FETCH_COLUMN);

    paginate([
        'list'    => $list,
        'modules' => $modules,
    ], $total, $page, $pageSize);
}

/**
 * 清空日志
 */
function clearLogs()
{
    global $pdo, $currentUser;

    adminOnly();

    $input = getJsonInput();
    $beforeDate = $input['before_date'] ?? '';

    if ($beforeDate) {
        $stmt = $pdo->prepare("DELETE FROM " . table('operation_log') . " WHERE created_at < ?");
        $stmt->execute([$beforeDate . ' 00:00:00']);
        $count = $stmt->rowCount();
    } else {
        $stmt = $pdo->prepare("TRUNCATE TABLE " . table('operation_log'));
        $stmt->execute();
        $count = 'all';
    }

    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '系统日志', '清空日志', "清空日志，条件: {$beforeDate ?: '全部'}");

    success(['cleared' => $count], '日志清空成功');
}

/**
 * 导出日志
 */
function exportLogs()
{
    global $pdo, $currentUser;

    adminOnly();

    $level = param('level', '');
    $dateStart = param('date_start', '');
    $dateEnd   = param('date_end', '');

    $where  = "WHERE 1=1";
    $params = [];

    if ($level) {
        $where .= " AND level = ?";
        $params[] = $level;
    }

    if ($dateStart) {
        $where .= " AND created_at >= ?";
        $params[] = $dateStart . ' 00:00:00';
    }

    if ($dateEnd) {
        $where .= " AND created_at <= ?";
        $params[] = $dateEnd . ' 23:59:59';
    }

    $stmt = $pdo->prepare("SELECT * FROM " . table('operation_log') . " $where ORDER BY id DESC");
    $stmt->execute($params);
    $logs = $stmt->fetchAll();

    // 生成CSV
    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename="logs_' . date('YmdHis') . '.csv"');

    $output = fopen('php://output', 'w');
    // UTF-8 BOM
    fprintf($output, chr(0xEF) . chr(0xBB) . chr(0xBF));

    fputcsv($output, ['ID', '用户ID', '用户名', '级别', '模块', '操作', '详情', '时间']);
    foreach ($logs as $log) {
        fputcsv($output, [
            $log['id'],
            $log['user_id'],
            $log['username'],
            $log['level'],
            $log['module'],
            $log['action'],
            $log['detail'],
            $log['created_at'],
        ]);
    }

    fclose($output);
    exit;
}
