<?php
/**
 * 视频数据爬取模块
 * 从已登录的平台账号 Cookie 爬取视频列表和数据统计
 * 
 * POST /api/scraper/sync   - 同步视频数据
 * GET  /api/scraper/status  - 同步状态
 */

// 兼容直接访问（绕过 index.php 路由）
if (!isset($GLOBALS['route_segments'])) {
    require_once __DIR__ . '/../includes/response.php';
    require_once __DIR__ . '/../includes/db.php';
    require_once __DIR__ . '/../includes/auth.php';
    $apiPath = preg_replace('#^/api/#', '', parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH));
    $GLOBALS['route_segments'] = explode('/', trim($apiPath, '/'));
    $GLOBALS['route_method']   = $_SERVER['REQUEST_METHOD'];
}

$currentUser = requireAuth();
$segments    = $GLOBALS['route_segments'];
$method      = $GLOBALS['route_method'];
$action      = $segments[1] ?? 'sync';

switch ($action) {
    case 'sync':
        syncVideoData();
        break;
    case 'status':
        getSyncStatus();
        break;
    default:
        error('接口不存在', 404);
}

/**
 * 同步视频数据 - 从已登录平台爬取
 */
function syncVideoData()
{
    global $pdo, $currentUser;

    $input     = getJsonInput();
    $accountId = isset($input['account_id']) ? (int)$input['account_id'] : 0;

    // 获取要同步的账号
    if ($accountId > 0) {
        $stmt = $pdo->prepare("SELECT * FROM " . table('platform_account') . " WHERE id = ? AND status = 'active'");
        $stmt->execute([$accountId]);
        $accounts = $stmt->fetchAll();
    } else {
        // 同步所有活跃账号
        $stmt = $pdo->prepare("SELECT * FROM " . table('platform_account') . " WHERE status = 'active' AND cookie IS NOT NULL AND cookie != ''");
        $stmt->execute();
        $accounts = $stmt->fetchAll();
    }

    if (empty($accounts)) {
        error('没有可同步的活跃账号，请先添加并登录平台账号');
    }

    $results = [];
    $totalSynced = 0;
    $errors = [];

    foreach ($accounts as $account) {
        $accId    = $account['id'];
        $platform = $account['platform'];
        $nickname = $account['nickname'];
        $cookie   = $account['cookie'];

        if (empty($cookie)) {
            $errors[] = ['account' => $nickname, 'platform' => $platform, 'error' => 'Cookie为空'];
            continue;
        }

        try {
            $videos = scrapePlatformVideos($platform, $cookie);

            if ($videos === null || $videos === false) {
                // Cookie可能过期
                $pdo->prepare("UPDATE " . table('platform_account') . " SET status = 'expired' WHERE id = ?")
                    ->execute([$accId]);
                $errors[] = ['account' => $nickname, 'platform' => $platform, 'error' => 'Cookie已过期或API请求失败'];
                continue;
            }

            if (empty($videos)) {
                $results[] = ['account' => $nickname, 'platform' => $platform, 'synced' => 0, 'found' => 0, 'message' => '未获取到视频数据，请检查Cookie是否有效'];
                continue;
            }

            $syncedCount = 0;
            $totalPlays  = 0;

            foreach ($videos as $video) {
                $title        = $video['title'] ?? '';
                $plays        = (int)($video['plays'] ?? 0);
                $likes        = (int)($video['likes'] ?? 0);
                $comments     = (int)($video['comments'] ?? 0);
                $shares       = (int)($video['shares'] ?? 0);
                $publishTime  = $video['publish_time'] ?? date('Y-m-d H:i:s');
                $videoId      = $video['video_id'] ?? '';

                $totalPlays += $plays;

                if (empty($title)) continue;

                // 检查是否已存在（按 platform + account_name + video_title 去重）
                $stmt = $pdo->prepare("SELECT id FROM " . table('video_data') . " WHERE platform = ? AND account_name = ? AND video_title = ? LIMIT 1");
                $stmt->execute([$platform, $nickname, $title]);
                $existing = $stmt->fetch();

                if ($existing) {
                    // 更新已有记录
                    $pdo->prepare("UPDATE " . table('video_data') . " SET plays = ?, likes = ?, comments = ?, shares = ?, synced_at = NOW() WHERE id = ?")
                        ->execute([$plays, $likes, $comments, $shares, $existing['id']]);
                } else {
                    // 插入新记录
                    $pdo->prepare("INSERT INTO " . table('video_data') . " (publish_id, platform, account_name, video_title, plays, likes, comments, shares, publish_time, synced_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())")
                        ->execute([0, $platform, $nickname, $title, $plays, $likes, $comments, $shares, $publishTime]);
                    $syncedCount++;
                }
            }

            // 更新账号统计
            $worksCount = count($videos);
            $todayPublish = $syncedCount . '/3';
            $pdo->prepare("UPDATE " . table('platform_account') . " SET works_count = ?, total_plays = ?, today_publish = ?, status = 'active', last_login = NOW() WHERE id = ?")
                ->execute([$worksCount, $totalPlays, $todayPublish, $accId]);

            $totalSynced += $syncedCount;
            $results[] = [
                'account'  => $nickname,
                'platform' => $platform,
                'synced'   => $syncedCount,
                'updated'  => $worksCount - $syncedCount,
                'found'    => $worksCount,
                'total'    => $worksCount,
                'plays'    => $totalPlays,
            ];

        } catch (Exception $e) {
            $errors[] = ['account' => $nickname, 'platform' => $platform, 'error' => $e->getMessage()];
        }
    }

    // 记录日志
    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '数据同步',
        '同步视频数据', "同步了 " . count($results) . " 个账号, 新增 {$totalSynced} 条记录");

    success([
        'synced_accounts' => count($results),
        'total_new_records' => $totalSynced,
        'results' => $results,
        'errors' => $errors,
    ], "同步完成，新增 {$totalSynced} 条视频数据");
}

/**
 * 获取同步状态
 */
function getSyncStatus()
{
    global $pdo;

    $stmt = $pdo->query("SELECT COUNT(*) FROM " . table('video_data'));
    $totalVideos = (int)$stmt->fetchColumn();

    $stmt = $pdo->query("SELECT MAX(synced_at) FROM " . table('video_data'));
    $lastSync = $stmt->fetchColumn();

    $stmt = $pdo->query("SELECT COUNT(*) FROM " . table('platform_account') . " WHERE status = 'active' AND cookie IS NOT NULL AND cookie != ''");
    $activeAccounts = (int)$stmt->fetchColumn();

    success([
        'total_videos'    => $totalVideos,
        'last_sync'       => $lastSync,
        'active_accounts' => $activeAccounts,
    ]);
}

/**
 * 从指定平台爬取视频列表
 * @param string $platform 平台标识
 * @param string $cookie Cookie字符串
 * @return array|null 视频列表，失败返回null
 */
function scrapePlatformVideos(string $platform, string $cookie): ?array
{
    switch ($platform) {
        case 'douyin':
            return scrapeDouyin($cookie);
        case 'kuaishou':
            return scrapeKuaishou($cookie);
        case 'xiaohongshu':
            return scrapeXiaohongshu($cookie);
        case 'weixin':
            return scrapeWeixin($cookie);
        default:
            return null;
    }
}

/**
 * 通用 cURL 请求封装
 */
function httpGet(string $url, array $headers, string $cookie, int $timeout = 15): ?array
{
    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL            => $url,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => $timeout,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_ENCODING       => 'gzip, deflate',
        CURLOPT_HTTPHEADER     => $headers,
        CURLOPT_COOKIE         => $cookie,
        CURLOPT_USERAGENT      => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    ]);

    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error    = curl_error($ch);
    $curlErr  = curl_errno($ch);
    curl_close($ch);

    // 记录请求日志
    $logDir = dirname(__DIR__) . '/logs';
    if (!is_dir($logDir)) @mkdir($logDir, 0755, true);
    $logFile = $logDir . '/scraper.log';
    $logMsg = date('Y-m-d H:i:s') . " GET {$url} => HTTP {$httpCode} (curl_err={$curlErr})\n";
    if ($error) $logMsg .= "  curl_error: {$error}\n";
    if ($response) $logMsg .= "  response: " . substr($response, 0, 500) . "\n";
    @file_put_contents($logFile, $logMsg, FILE_APPEND | LOCK_EX);

    if ($curlErr !== 0 || $httpCode >= 400) {
        return null;
    }

    $data = json_decode($response, true);
    return is_array($data) ? $data : null;
}

function httpPost(string $url, array $headers, string $cookie, string $body, int $timeout = 15): ?array
{
    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL            => $url,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => $timeout,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_ENCODING       => 'gzip, deflate',
        CURLOPT_HTTPHEADER     => $headers,
        CURLOPT_COOKIE         => $cookie,
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $body,
        CURLOPT_USERAGENT      => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    ]);

    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    if ($response === false || $httpCode >= 400) {
        return null;
    }

    $data = json_decode($response, true);
    return is_array($data) ? $data : null;
}

// ══════════════════════════════════════════════════════════════
// 抖音爬虫
// ══════════════════════════════════════════════════════════════

function scrapeDouyin(string $cookie): ?array
{
    $headers = [
        'Accept: application/json, text/plain, */*',
        'Referer: https://creator.douyin.com/',
        'Origin: https://creator.douyin.com',
    ];

    $videos = [];
    $cursor = 0;
    $maxPages = 3; // 最多爬3页，避免被封

    for ($page = 0; $page < $maxPages; $page++) {
        $url = "https://creator.douyin.com/web/api/media/aweme/post/?limit=20&cursor={$cursor}";
        $data = httpGet($url, $headers, $cookie);

        if (!$data) {
            if ($page === 0) return null; // 第一页就失败，Cookie可能过期
            break;
        }

        $list = $data['aweme_list'] ?? $data['data']['aweme_list'] ?? [];
        if (empty($list)) break;

        foreach ($list as $item) {
            $stats = $item['statistics'] ?? $item['stats'] ?? [];
            $videos[] = [
                'video_id'     => $item['aweme_id'] ?? $item['id'] ?? '',
                'title'        => $item['desc'] ?? $item['title'] ?? '',
                'plays'        => (int)($stats['play_count'] ?? $stats['playCount'] ?? 0),
                'likes'        => (int)($stats['digg_count'] ?? $stats['likeCount'] ?? $stats['like_count'] ?? 0),
                'comments'     => (int)($stats['comment_count'] ?? $stats['commentCount'] ?? 0),
                'shares'       => (int)($stats['share_count'] ?? $stats['shareCount'] ?? 0),
                'publish_time' => isset($item['create_time']) ? date('Y-m-d H:i:s', $item['create_time']) : ($item['createTime'] ?? date('Y-m-d H:i:s')),
            ];
        }

        $hasMore = $data['has_more'] ?? $data['data']['has_more'] ?? false;
        if (!$hasMore) break;

        $cursor = $data['cursor'] ?? $data['data']['cursor'] ?? ($cursor + 20);
        usleep(500000); // 0.5秒延迟，防止请求过快
    }

    return $videos;
}

// ══════════════════════════════════════════════════════════════
// 快手爬虫
// ══════════════════════════════════════════════════════════════

function scrapeKuaishou(string $cookie): ?array
{
    $headers = [
        'Accept: application/json, text/plain, */*',
        'Referer: https://cp.kuaishou.com/',
        'Origin: https://cp.kuaishou.com',
        'Content-Type: application/json',
    ];

    $videos = [];
    $pcursor = '';
    $maxPages = 3;

    for ($page = 0; $page < $maxPages; $page++) {
        $url = "https://cp.kuaishou.com/rest/wd/knowledge/feed/profile?count=20&pcursor=" . urlencode($pcursor);
        $data = httpGet($url, $headers, $cookie);

        if (!$data) {
            if ($page === 0) return null;
            break;
        }

        $list = $data['data']['list'] ?? $data['list'] ?? [];
        if (empty($list)) break;

        foreach ($list as $item) {
            $videos[] = [
                'video_id'     => $item['id'] ?? $item['photoId'] ?? '',
                'title'        => $item['caption'] ?? $item['title'] ?? $item['description'] ?? '',
                'plays'        => (int)($item['viewCount'] ?? $item['play_count'] ?? $item['view'] ?? 0),
                'likes'        => (int)($item['likeCount'] ?? $item['like_count'] ?? $item['like'] ?? 0),
                'comments'     => (int)($item['commentCount'] ?? $item['comment_count'] ?? $item['comment'] ?? 0),
                'shares'       => (int)($item['shareCount'] ?? $item['share_count'] ?? $item['share'] ?? 0),
                'publish_time' => isset($item['timestamp']) ? date('Y-m-d H:i:s', (int)($item['timestamp'] / 1000)) : ($item['createTime'] ?? date('Y-m-d H:i:s')),
            ];
        }

        $pcursor = $data['data']['pcursor'] ?? $data['pcursor'] ?? '';
        if (empty($pcursor) || $pcursor === 'no_more') break;

        usleep(500000);
    }

    return $videos;
}

// ══════════════════════════════════════════════════════════════
// 小红书爬虫
// ══════════════════════════════════════════════════════════════

function scrapeXiaohongshu(string $cookie): ?array
{
    $headers = [
        'Accept: application/json, text/plain, */*',
        'Referer: https://creator.xiaohongshu.com/',
        'Origin: https://creator.xiaohongshu.com',
    ];

    $videos = [];
    $cursor = '';
    $maxPages = 3;

    for ($page = 0; $page < $maxPages; $page++) {
        $url = "https://creator.xiaohongshu.com/api/galaxy/creator/note/user/posted?num=20&cursor=" . urlencode($cursor) . "&image_formats=jpg,webp,avif";
        $data = httpGet($url, $headers, $cookie);

        if (!$data) {
            if ($page === 0) return null;
            break;
        }

        $notes = $data['data']['notes'] ?? $data['data']['list'] ?? $data['notes'] ?? [];
        if (empty($notes)) break;

        foreach ($notes as $note) {
            $interactInfo = $note['interactInfo'] ?? $note['interact_info'] ?? [];
            $videos[] = [
                'video_id'     => $note['id'] ?? $note['noteId'] ?? $note['note_id'] ?? '',
                'title'        => $note['title'] ?? $note['displayTitle'] ?? $note['desc'] ?? '',
                'plays'        => (int)($interactInfo['viewCount'] ?? $interactInfo['view_count'] ?? $note['views'] ?? 0),
                'likes'        => (int)($interactInfo['likedCount'] ?? $interactInfo['liked_count'] ?? $note['likes'] ?? 0),
                'comments'     => (int)($interactInfo['commentCount'] ?? $interactInfo['comment_count'] ?? $note['comments'] ?? 0),
                'shares'       => (int)($interactInfo['shareCount'] ?? $interactInfo['share_count'] ?? $note['shares'] ?? 0),
                'publish_time' => isset($note['time']) ? date('Y-m-d H:i:s', (int)($note['time'] / 1000)) : ($note['createTime'] ?? date('Y-m-d H:i:s')),
            ];
        }

        $cursor = $data['data']['cursor'] ?? $data['cursor'] ?? '';
        $hasMore = $data['data']['has_more'] ?? $data['hasMore'] ?? false;
        if (!$hasMore || empty($cursor)) break;

        usleep(500000);
    }

    return $videos;
}

// ══════════════════════════════════════════════════════════════
// 视频号爬虫
// ══════════════════════════════════════════════════════════════

function scrapeWeixin(string $cookie): ?array
{
    $headers = [
        'Accept: application/json, text/plain, */*',
        'Referer: https://channels.weixin.qq.com/',
        'Origin: https://channels.weixin.qq.com',
        'Content-Type: application/json',
    ];

    $videos = [];
    $maxPages = 3;
    $lastBuffId = '';

    for ($page = 0; $page < $maxPages; $page++) {
        $body = json_encode([
            'count'      => 20,
            'lastBuffId' => $lastBuffId,
        ]);

        $data = httpPost(
            'https://channels.weixin.qq.com/cgi-bin/mmfinderassistant-bin/post/getpostlist',
            $headers, $cookie, $body
        );

        if (!$data) {
            if ($page === 0) return null;
            break;
        }

        $list = $data['data']['list'] ?? $data['list'] ?? $data['data']['postList'] ?? [];
        if (empty($list)) break;

        foreach ($list as $item) {
            $videos[] = [
                'video_id'     => $item['id'] ?? $item['objectId'] ?? $item['feedId'] ?? '',
                'title'        => $item['title'] ?? $item['desc'] ?? $item['description'] ?? '',
                'plays'        => (int)($item['readCount'] ?? $item['viewCount'] ?? $item['playCount'] ?? 0),
                'likes'        => (int)($item['likeCount'] ?? $item['like_count'] ?? $item['favorCount'] ?? 0),
                'comments'     => (int)($item['commentCount'] ?? $item['comment_count'] ?? 0),
                'shares'       => (int)($item['shareCount'] ?? $item['share_count'] ?? $item['forwardCount'] ?? 0),
                'publish_time' => isset($item['createTime']) ? date('Y-m-d H:i:s', (int)$item['createTime']) : ($item['publishTime'] ?? date('Y-m-d H:i:s')),
            ];
        }

        $lastBuffId = $data['data']['lastBuffId'] ?? $data['lastBuffId'] ?? '';
        $hasMore = $data['data']['hasMore'] ?? $data['hasMore'] ?? true;
        if (!$hasMore || empty($lastBuffId)) break;

        usleep(500000);
    }

    return $videos;
}
