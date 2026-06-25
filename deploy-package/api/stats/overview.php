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

// 视频数据统计（从 video_data 表汇总）
$stmt = $pdo->query("SELECT COUNT(*) FROM " . table('video_data'));
$r['video_data_count'] = (int)$stmt->fetchColumn();

$stmt = $pdo->query("SELECT COALESCE(SUM(plays), 0) AS total_plays, COALESCE(SUM(likes), 0) AS total_likes, COALESCE(SUM(comments), 0) AS total_comments FROM " . table('video_data'));
$videoStats = $stmt->fetch();
$r['total_plays'] = (int)($videoStats['total_plays'] ?? 0);
$r['total_likes'] = (int)($videoStats['total_likes'] ?? 0);
$r['total_comments'] = (int)($videoStats['total_comments'] ?? 0);

// 账号维度汇总（works_count, total_plays）
$stmt = $pdo->query("SELECT COALESCE(SUM(works_count), 0) AS total_works, COALESCE(SUM(total_plays), 0) AS acc_total_plays FROM " . table('platform_account'));
$accStats = $stmt->fetch();
$r['total_works'] = (int)($accStats['total_works'] ?? 0);
// 如果 video_data 没数据但 platform_account 有，用 platform_account 的
if ($r['total_plays'] == 0 && (int)($accStats['acc_total_plays'] ?? 0) > 0) {
    $r['total_plays'] = (int)($accStats['acc_total_plays'] ?? 0);
}

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

// 如果没有任何视频数据，添加提示
if ($r['video_data_count'] == 0) {
    $activeAccounts = 0;
    $stmt = $pdo->query("SELECT COUNT(*) FROM " . table('platform_account') . " WHERE status = 'active' AND cookie IS NOT NULL AND cookie != ''");
    $activeAccounts = (int)$stmt->fetchColumn();
    if ($activeAccounts > 0) {
        $alerts[] = [
            'message' => "视频数据为空，请点击「同步平台数据」拉取",
            'text' => "已登录 {$activeAccounts} 个账号，但尚未同步视频数据",
        ];
    } else {
        $alerts[] = [
            'message' => "暂无已登录的平台账号",
            'text' => "请先在「账号管理」中添加并登录平台账号",
        ];
    }
}

$r['alerts'] = $alerts;

success($r);
