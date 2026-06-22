<?php
require_once __DIR__ . '/../_helpers.php';
requireAuth();
if (strpos($_SERVER['REQUEST_URI'], '/export') !== false) {
    // 导出 CSV
    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename=logs_' . date('Ymd') . '.csv');
    echo "\xEF\xBB\xBF"; // BOM
    echo "ID,用户,级别,模块,操作,详情,时间\n";
    $stmt = $pdo->query("SELECT * FROM " . table('operation_log') . " ORDER BY id DESC LIMIT 1000");
    while ($row = $stmt->fetch()) {
        echo implode(',', [$row['id'], $row['username'], $row['level'], $row['module'], $row['action'], '"' . str_replace('"', '""', $row['detail']) . '"', $row['created_at']]) . "\n";
    }
    exit;
}
[$page, $pageSize, $offset] = getPageParams();
$where = "1=1"; $params = [];
if ($level = param('level')) { $where .= " AND level = ?"; $params[] = $level; }
if ($keyword = param('keyword')) { $where .= " AND (action LIKE ? OR detail LIKE ?)"; $params[] = "%$keyword%"; $params[] = "%$keyword%"; }
if ($userId = param('user_id')) { $where .= " AND user_id = ?"; $params[] = $userId; }
$stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('operation_log') . " WHERE $where");
$stmt->execute($params); $total = $stmt->fetchColumn();
$stmt = $pdo->prepare("SELECT * FROM " . table('operation_log') . " WHERE $where ORDER BY id DESC LIMIT $pageSize OFFSET $offset");
$stmt->execute($params);
paginate($stmt->fetchAll(), $total, $page, $pageSize);
