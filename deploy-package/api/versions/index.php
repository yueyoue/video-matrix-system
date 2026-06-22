<?php
require_once __DIR__ . '/../_helpers.php';
$method = $_SERVER['REQUEST_METHOD'];
$segments = getPathSegments();
$id = $segments[1] ?? null;

switch ($method) {
    case 'GET':
        $stmt = $pdo->query("SELECT * FROM " . table('app_version') . " ORDER BY id DESC");
        success($stmt->fetchAll());
        break;
    case 'POST':
        adminOnly();
        $input = getJsonInput();
        $version = $input['version'] ?? '';
        $changelog = $input['changelog'] ?? '';
        $url = $input['download_url'] ?? '';
        if (!$version) error('版本号不能为空');
        $pdo->prepare("INSERT INTO " . table('app_version') . " (version, changelog, download_url) VALUES (?, ?, ?)")
            ->execute([$version, $changelog, $url]);
        success(['id' => $pdo->lastInsertId()], '发布成功');
        break;
    case 'PUT':
        if (!$id) error('缺少ID');
        adminOnly();
        $input = getJsonInput();
        $sets = []; $params = [];
        foreach (['version', 'changelog', 'download_url', 'status'] as $f) {
            if (isset($input[$f])) { $sets[] = "$f = ?"; $params[] = $input[$f]; }
        }
        if ($sets) { $params[] = $id; $pdo->prepare("UPDATE " . table('app_version') . " SET " . implode(',', $sets) . " WHERE id = ?")->execute($params); }
        success(null, '更新成功');
        break;
    default: error('方法不允许', 405);
}
