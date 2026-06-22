<?php
require_once __DIR__ . '/../_helpers.php';
$method = $_SERVER['REQUEST_METHOD'];
if ($method === 'GET') {
    $stmt = $pdo->query("SELECT * FROM " . table('ai_config') . " LIMIT 1");
    success($stmt->fetch() ?: []);
} elseif ($method === 'PUT') {
    adminOnly();
    $input = getJsonInput();
    $sets = []; $params = [];
    foreach (['provider', 'app_id', 'secret_key', 'daily_limit'] as $f) {
        if (isset($input[$f])) { $sets[] = "$f = ?"; $params[] = $input[$f]; }
    }
    if ($sets) $pdo->prepare("UPDATE " . table('ai_config') . " SET " . implode(',', $sets))->execute($params);
    success(null, '更新成功');
} else { error('方法不允许', 405); }
