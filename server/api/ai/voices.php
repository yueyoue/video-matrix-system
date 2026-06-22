<?php
require_once __DIR__ . '/../_helpers.php';
$method = $_SERVER['REQUEST_METHOD'];
$segments = getPathSegments();
$id = $segments[2] ?? null;

switch ($method) {
    case 'GET':
        $status = param('status');
        $sql = "SELECT * FROM " . table('ai_voice');
        if ($status) { $sql .= " WHERE status = '$status'"; }
        $sql .= " ORDER BY id";
        success($pdo->query($sql)->fetchAll());
        break;
    case 'POST':
        adminOnly();
        $input = getJsonInput();
        $pdo->prepare("INSERT INTO " . table('ai_voice') . " (name, voice_id, type, scene) VALUES (?, ?, ?, ?)")
            ->execute([$input['name'] ?? '', $input['voice_id'] ?? '', $input['type'] ?? 'female', $input['scene'] ?? '']);
        success(['id' => $pdo->lastInsertId()], '添加成功');
        break;
    case 'PUT':
        if (!$id) error('缺少ID');
        adminOnly();
        $input = getJsonInput();
        $sets = []; $params = [];
        foreach (['name', 'voice_id', 'type', 'scene', 'status'] as $f) {
            if (isset($input[$f])) { $sets[] = "$f = ?"; $params[] = $input[$f]; }
        }
        if ($sets) { $params[] = $id; $pdo->prepare("UPDATE " . table('ai_voice') . " SET " . implode(',', $sets) . " WHERE id = ?")->execute($params); }
        success(null, '更新成功');
        break;
    case 'DELETE':
        if (!$id) error('缺少ID');
        adminOnly();
        $pdo->prepare("DELETE FROM " . table('ai_voice') . " WHERE id = ?")->execute([$id]);
        success(null, '删除成功');
        break;
    default: error('方法不允许', 405);
}
