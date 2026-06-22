<?php
require_once __DIR__ . '/../_helpers.php';
requireAuth();
$today = date('Y-m-d');
$platforms = ['douyin', 'kuaishou', 'xiaohongshu', 'weixin'];
$result = [];
foreach ($platforms as $p) {
    $stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('platform_account') . " WHERE platform = ?"); $stmt->execute([$p]);
    $accounts = (int)$stmt->fetchColumn();
    $stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('publish_record') . " WHERE platform = ? AND DATE(created_at) = ?"); $stmt->execute([$p, $today]);
    $todayPub = (int)$stmt->fetchColumn();
    $stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('publish_record') . " WHERE platform = ? AND DATE(created_at) = ? AND status = 'success'"); $stmt->execute([$p, $today]);
    $success = (int)$stmt->fetchColumn();
    $rate = $todayPub > 0 ? round($success / $todayPub * 100, 1) : 0;
    $result[] = ['platform' => $p, 'accounts' => $accounts, 'today_publish' => $todayPub, 'success_rate' => $rate];
}
success($result);
