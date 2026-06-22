<?php
/**
 * 数据统计接口
 * GET /api/stats/dashboard   - 仪表盘概览
 * GET /api/stats/trends      - 趋势数据
 * GET /api/stats/platform    - 平台统计
 * GET /api/stats/accounts    - 账号统计排行
 */

require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/auth.php';

$currentUser = requireAuth();
$segments    = $GLOBALS['route_segments'];
$action      = $segments[1] ?? 'dashboard';

switch ($action) {
    case 'dashboard':
        getDashboard();
        break;
    case 'trends':
        getTrends();
        break;
    case 'platform':
        getPlatformStats();
        break;
    case 'accounts':
        getAccountRanking();
        break;
    default:
        error('接口不存在', 404);
}

/**
 * 仪表盘概览
 */
function getDashboard()
{
    global $pdo, $currentUser;

    $userId = $currentUser['user_id'];
    $isAdmin = $currentUser['role'] === 'admin';

    // 今日日期
    $today = date('Y-m-d');

    // 账号总数
    $sql = "SELECT COUNT(*) FROM " . table('platform_account');
    $params = [];
    if (!$isAdmin) {
        $sql .= " WHERE user_id = ?";
        $params[] = $userId;
    }
    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $totalAccounts = $stmt->fetchColumn();

    // 活跃账号数
    $sql = "SELECT COUNT(*) FROM " . table('platform_account') . " WHERE status = 'active'";
    $params = [];
    if (!$isAdmin) {
        $sql .= " AND user_id = ?";
        $params[] = $userId;
    }
    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $activeAccounts = $stmt->fetchColumn();

    // 今日发布数
    $sql = "SELECT COUNT(*) FROM " . table('publish_record') . " WHERE DATE(published_time) = ?";
    $params = [$today];
    if (!$isAdmin) {
        $sql .= " AND user_id = ?";
        $params[] = $userId;
    }
    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $todayPublished = $stmt->fetchColumn();

    // 待发布数
    $sql = "SELECT COUNT(*) FROM " . table('publish_record') . " WHERE status = 'waiting'";
    $params = [];
    if (!$isAdmin) {
        $sql .= " AND user_id = ?";
        $params[] = $userId;
    }
    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $waitingPublish = $stmt->fetchColumn();

    // 总播放量
    $sql = "SELECT SUM(plays) FROM " . table('video_data');
    $params = [];
    // video_data 没有 user_id，按平台账号关联查询
    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $totalPlays = $stmt->fetchColumn() ?: 0;

    // 总点赞
    $stmt = $pdo->prepare("SELECT SUM(likes) FROM " . table('video_data'));
    $stmt->execute();
    $totalLikes = $stmt->fetchColumn() ?: 0;

    // 总评论
    $stmt = $pdo->prepare("SELECT SUM(comments) FROM " . table('video_data'));
    $stmt->execute();
    $totalComments = $stmt->fetchColumn() ?: 0;

    // 总转发
    $stmt = $pdo->prepare("SELECT SUM(shares) FROM " . table('video_data'));
    $stmt->execute();
    $totalShares = $stmt->fetchColumn() ?: 0;

    // 今日发布详情（按平台）
    $sql = "SELECT platform, COUNT(*) as count FROM " . table('publish_record') . " WHERE DATE(published_time) = ? AND status = 'success'";
    $params = [$today];
    if (!$isAdmin) {
        $sql .= " AND user_id = ?";
        $params[] = $userId;
    }
    $sql .= " GROUP BY platform";
    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $todayByPlatform = $stmt->fetchAll();

    success([
        'total_accounts'    => (int)$totalAccounts,
        'active_accounts'   => (int)$activeAccounts,
        'today_published'   => (int)$todayPublished,
        'waiting_publish'   => (int)$waitingPublish,
        'total_plays'       => (int)$totalPlays,
        'total_likes'       => (int)$totalLikes,
        'total_comments'    => (int)$totalComments,
        'total_shares'      => (int)$totalShares,
        'today_by_platform' => $todayByPlatform,
    ]);
}

/**
 * 趋势数据（最近7天/30天）
 */
function getTrends()
{
    global $pdo;

    $days = (int)param('days', 7);
    $days = min(90, max(1, $days));
    $startDate = date('Y-m-d', strtotime("-{$days} days"));

    // 每日播放量趋势
    $stmt = $pdo->prepare("
        SELECT DATE(publish_time) as date, SUM(plays) as plays, SUM(likes) as likes, SUM(comments) as comments, SUM(shares) as shares
        FROM " . table('video_data') . "
        WHERE publish_time >= ?
        GROUP BY DATE(publish_time)
        ORDER BY date ASC
    ");
    $stmt->execute([$startDate]);
    $trends = $stmt->fetchAll();

    // 填充缺失日期
    $result = [];
    $current = new DateTime($startDate);
    $end = new DateTime();
    $trendMap = [];
    foreach ($trends as $t) {
        $trendMap[$t['date']] = $t;
    }

    while ($current <= $end) {
        $dateStr = $current->format('Y-m-d');
        $result[] = $trendMap[$dateStr] ?? [
            'date'     => $dateStr,
            'plays'    => 0,
            'likes'    => 0,
            'comments' => 0,
            'shares'   => 0,
        ];
        $current->modify('+1 day');
    }

    success($result);
}

/**
 * 平台统计
 */
function getPlatformStats()
{
    global $pdo;

    $stmt = $pdo->prepare("
        SELECT platform,
               COUNT(*) as video_count,
               SUM(plays) as total_plays,
               SUM(likes) as total_likes,
               SUM(comments) as total_comments,
               SUM(shares) as total_shares
        FROM " . table('video_data') . "
        GROUP BY platform
        ORDER BY total_plays DESC
    ");
    $stmt->execute();
    $stats = $stmt->fetchAll();

    success($stats);
}

/**
 * 账号统计排行
 */
function getAccountRanking()
{
    global $pdo, $currentUser;

    $limit = min(50, max(1, (int)param('limit', 10)));
    $sortBy = param('sort', 'plays');

    $orderBy = 'total_plays';
    if (in_array($sortBy, ['plays', 'likes', 'comments', 'shares'])) {
        $orderBy = "total_{$sortBy}";
    }

    $stmt = $pdo->prepare("
        SELECT account_name, platform,
               SUM(plays) as total_plays,
               SUM(likes) as total_likes,
               SUM(comments) as total_comments,
               SUM(shares) as total_shares,
               COUNT(*) as video_count
        FROM " . table('video_data') . "
        GROUP BY account_name, platform
        ORDER BY $orderBy DESC
        LIMIT ?
    ");
    $stmt->execute([$limit]);
    $ranking = $stmt->fetchAll();

    success($ranking);
}
