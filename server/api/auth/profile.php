<?php
require_once __DIR__ . '/../_helpers.php';
if ($_SERVER['REQUEST_METHOD'] !== 'GET') error('方法不允许', 405);
$u = requireAuth();
$stmt = $pdo->prepare("SELECT id, username, role, daily_quota, used_quota, status, last_login, created_at FROM " . table('sys_user') . " WHERE id = ?");
$stmt->execute([$u['user_id']]);
$user = $stmt->fetch();
if (!$user) error('用户不存在', 404);
success($user);
