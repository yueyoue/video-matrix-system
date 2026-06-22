<?php
require_once __DIR__ . '/../_helpers.php';
if ($_SERVER['REQUEST_METHOD'] !== 'POST') error('方法不允许', 405);
$input = getJsonInput();
$username = trim($input['username'] ?? '');
$password = $input['password'] ?? '';
if (!$username || !$password) error('用户名和密码不能为空');
$stmt = $pdo->prepare("SELECT * FROM " . table('sys_user') . " WHERE username = ?");
$stmt->execute([$username]);
$user = $stmt->fetch();
if (!$user) error('用户名或密码错误');
if ($user['status'] === 'disabled') error('账号已被禁用');
if (!password_verify($password, $user['password'])) error('用户名或密码错误');
$stmt = $pdo->prepare("UPDATE " . table('sys_user') . " SET last_login = NOW() WHERE id = ?");
$stmt->execute([$user['id']]);
$token = jwtEncode(['user_id' => $user['id'], 'username' => $user['username'], 'role' => $user['role']]);
logOp($user['id'], $user['username'], 'INFO', '用户登录', '登录', '登录成功');
success(['token' => $token, 'userInfo' => ['id' => $user['id'], 'username' => $user['username'], 'role' => $user['role'], 'daily_quota' => $user['daily_quota'], 'used_quota' => $user['used_quota']]], '登录成功');
