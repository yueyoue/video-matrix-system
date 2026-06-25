<?php
require_once __DIR__ . '/../_helpers.php';
requireAuth();
$today = date('Y-m-d');
$r = [];

// 基础统计
$stmt = $pdo->query("SELECT COUNT(*) FROM " . table('sys_user'));
$r['total_users'] = (int)$stmt->fetchColumn();

$stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('video_task') . " WHERE DATE(created_at) = ?");
$stmt->execute([$today]);
$r['today_videos'] = (int)$stmt->fetchColumn();

$stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('publish_record') . " WHERE DATE(created_at) = ? AND status = 'success'");
$stmt->execute([$today]);
$r['today_publish_success'] = (int)$stmt->fetchColumn();

$stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('publish_record') . " WHERE DATE(created_at) = ? AND status = 'failed'");
$stmt->execute([$today]);
$r['today_publish_failed'] = (int)$stmt->fetchColumn();

$total = $r['today_publish_success'] + $r['today_publish_failed'];
$r['success_rate'] = $total > 0 ? round($r['today_publish_success'] / $total * 100, 1) : 0;

// 管理账号数
$stmt = $pdo->query("SELECT COUNT(*) FROM " . table('platform_account'));
$r['accountCount'] = (int)$stmt->fetchColumn();

// 最近发布记录（最近10条）
$stmt = $pdo->prepare("
    SELECT pr.platform, pr.account_name AS accountName, pr.video_title AS videoTitle,
           pr.published_time AS time, pr.status
    FROM " . table('publish_record') . " pr
    ORDER BY pr.id DESC LIMIT 10
");
$stmt->execute();
$r['recentPublish'] = $stmt->fetchAll();

// 异常预警：检查过期账号
$stmt = $pdo->prepare("
    SELECT nickname, platform
    FROM " . table('platform_account') . "
    WHERE status = 'expired'
    ORDER BY id DESC LIMIT 10
");
$stmt->execute();
$expiredAccounts = $stmt->fetchAll();

$alerts = [];
foreach ($expiredAccounts as $acc) {
    $platformName = match($acc['platform']) {
        'douyin' => '抖音',
        'kuaishou' => '快手',
        'xiaohongshu' => '小红书',
        'weixin' => '视频号',
        default => $acc['platform'],
    };
    $alerts[] = [
        'message' => "{$platformName}账号 {$acc['nickname']} 登录失效",
        'text' => "Cookie已过期，请重新扫码登录",
    ];
}
$r['alerts'] = $alerts;

success($r);
