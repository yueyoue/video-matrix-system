<?php
require_once __DIR__ . '/../_helpers.php';
requireAuth();
$today = date('Y-m-d');
$r = [];
$stmt = $pdo->query("SELECT COUNT(*) FROM " . table('sys_user')); $r['total_users'] = (int)$stmt->fetchColumn();
$stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('video_task') . " WHERE DATE(created_at) = ?"); $stmt->execute([$today]); $r['today_videos'] = (int)$stmt->fetchColumn();
$stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('publish_record') . " WHERE DATE(created_at) = ? AND status = 'success'"); $stmt->execute([$today]); $r['today_publish_success'] = (int)$stmt->fetchColumn();
$stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('publish_record') . " WHERE DATE(created_at) = ? AND status = 'failed'"); $stmt->execute([$today]); $r['today_publish_failed'] = (int)$stmt->fetchColumn();
$total = $r['today_publish_success'] + $r['today_publish_failed'];
$r['success_rate'] = $total > 0 ? round($r['today_publish_success'] / $total * 100, 1) : 0;
success($r);
