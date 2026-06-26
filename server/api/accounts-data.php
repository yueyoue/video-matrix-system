<?php
/**
 * 数据统计 - 监控账号管理与视频数据爬取
 * GET    /api/accounts-data          - 监控账号列表
 * POST   /api/accounts-data          - 添加监控账号
 * PUT    /api/accounts-data/{id}     - 更新监控账号
 * DELETE /api/accounts-data/{id}     - 删除监控账号
 * POST   /api/accounts-data/sync     - 同步数据（全部或指定账号）
 * GET    /api/accounts-data/videos   - 视频数据列表（分页+筛选）
 * GET    /api/accounts-data/summary  - 汇总统计
 * GET    /api/accounts-data/export   - 导出Excel
 */

// 兼容直接访问（绕过 index.php 路由）
if (!isset($GLOBALS['route_segments'])) {
    require_once __DIR__ . '/../includes/response.php';
    require_once __DIR__ . '/../includes/db.php';
    require_once __DIR__ . '/../includes/auth.php';
    $apiPath = preg_replace('#^/api/#', '', parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH));
    $apiPath = preg_replace('/\.php$/', '', $apiPath);
    $GLOBALS['route_segments'] = explode('/', trim($apiPath, '/'));
    $GLOBALS['route_method']   = $_SERVER['REQUEST_METHOD'];
}

$currentUser = requireAuth();
$segments    = $GLOBALS['route_segments'];
$method      = $GLOBALS['route_method'];
$action      = $segments[1] ?? '';

switch ($action) {
    case 'sync':
        syncAll();
        break;
    case 'videos':
        getVideos();
        break;
    case 'summary':
        getSummary();
        break;
    case 'export':
        exportExcel();
        break;
    case '':
        if ($method === 'GET') getList();
        elseif ($method === 'POST') create();
        else error('方法不允许', 405);
        break;
    default:
        if (is_numeric($action)) {
            $id = (int)$action;
            if ($method === 'PUT') update($id);
            elseif ($method === 'DELETE') remove($id);
            else error('方法不允许', 405);
        } else {
            error('接口不存在', 404);
        }
}

// ───────────────────────── CRUD ─────────────────────────

function getList()
{
    global $pdo;
    $platform = param('platform', '');
    $keyword  = param('keyword', '');
    $where    = "WHERE 1=1";
    $params   = [];
    if ($platform) { $where .= " AND platform = ?"; $params[] = $platform; }
    if ($keyword)  { $where .= " AND account_name LIKE ?"; $params[] = "%{$keyword}%"; }

    $st = $pdo->prepare("SELECT COUNT(*) FROM " . table('monitored_account') . " $where");
    $st->execute($params);
    $total = (int)$st->fetchColumn();

    $st = $pdo->prepare("SELECT * FROM " . table('monitored_account') . " $where ORDER BY id DESC");
    $st->execute($params);
    $list = $st->fetchAll();

    foreach ($list as &$row) {
        $row['total_videos']   = (int)$row['total_videos'];
        $row['total_plays']    = (int)$row['total_plays'];
        $row['total_likes']    = (int)$row['total_likes'];
        $row['total_comments'] = (int)$row['total_comments'];
        $row['total_shares']   = (int)$row['total_shares'];
    }
    success(['list' => $list, 'total' => $total]);
}

function create()
{
    global $pdo, $currentUser;
    $input       = getJsonInput();
    $platform    = $input['platform'] ?? '';
    $accountName = trim($input['account_name'] ?? '');
    $accountUrl  = trim($input['account_url'] ?? '');

    $platforms = ['douyin', 'kuaishou', 'xiaohongshu', 'weixin'];
    if (!in_array($platform, $platforms)) error('平台类型无效');
    if (empty($accountName)) error('账号名称不能为空');

    $secUid = extractSecUid($platform, $accountUrl);

    $st = $pdo->prepare("INSERT INTO " . table('monitored_account') . " (platform, account_name, account_url, sec_uid) VALUES (?, ?, ?, ?)");
    $st->execute([$platform, $accountName, $accountUrl, $secUid]);

    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '数据统计', '添加监控账号', "添加{$platform}监控账号: {$accountName}");

    success(['id' => (int)$pdo->lastInsertId()], '添加成功');
}

function update($id)
{
    global $pdo, $currentUser;
    $input = getJsonInput();

    $st = $pdo->prepare("SELECT * FROM " . table('monitored_account') . " WHERE id = ?");
    $st->execute([$id]);
    $account = $st->fetch();
    if (!$account) error('账号不存在', 404);

    $fields = [];
    $params = [];

    if (isset($input['account_name'])) { $fields[] = "account_name = ?"; $params[] = trim($input['account_name']); }
    if (isset($input['account_url'])) {
        $fields[] = "account_url = ?"; $params[] = trim($input['account_url']);
        $fields[] = "sec_uid = ?"; $params[] = extractSecUid($account['platform'], trim($input['account_url']));
    }
    if (isset($input['status'])) { $fields[] = "status = ?"; $params[] = $input['status']; }

    if (empty($fields)) error('没有需要更新的字段');

    $params[] = $id;
    $pdo->prepare("UPDATE " . table('monitored_account') . " SET " . implode(', ', $fields) . " WHERE id = ?")->execute($params);

    success(null, '更新成功');
}

function remove($id)
{
    global $pdo, $currentUser;
    $st = $pdo->prepare("SELECT * FROM " . table('monitored_account') . " WHERE id = ?");
    $st->execute([$id]);
    $account = $st->fetch();
    if (!$account) error('账号不存在', 404);

    // 同时删除该账号的视频数据
    $pdo->prepare("DELETE FROM " . table('video_data') . " WHERE platform = ? AND account_name = ?")->execute([$account['platform'], $account['account_name']]);
    $pdo->prepare("DELETE FROM " . table('monitored_account') . " WHERE id = ?")->execute([$id]);

    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '数据统计', '删除监控账号', "删除: {$account['account_name']}");

    success(null, '删除成功');
}

// ───────────────────────── 数据同步 ─────────────────────────

function syncAll()
{
    global $pdo, $currentUser;
    $input     = getJsonInput();
    $accountId = isset($input['account_id']) ? (int)$input['account_id'] : 0;

    if ($accountId > 0) {
        $st = $pdo->prepare("SELECT * FROM " . table('monitored_account') . " WHERE id = ?");
        $st->execute([$accountId]);
        $accounts = $st->fetchAll();
    } else {
        $st = $pdo->query("SELECT * FROM " . table('monitored_account') . " WHERE status = 'active'");
        $accounts = $st->fetchAll();
    }

    if (empty($accounts)) error('没有可同步的监控账号');

    $results = [];
    $totalNew = 0;

    foreach ($accounts as $acc) {
        try {
            $videos = crawlAccountVideos($acc['platform'], $acc['account_url'], $acc['sec_uid']);

            if ($videos === null) {
                $pdo->prepare("UPDATE " . table('monitored_account') . " SET status = 'error' WHERE id = ?")->execute([$acc['id']]);
                $results[] = ['id' => $acc['id'], 'account' => $acc['account_name'], 'platform' => $acc['platform'], 'error' => '爬取失败，请检查账号URL是否正确'];
                continue;
            }

            $newCount = 0;
            $totalPlays = 0;
            $totalLikes = 0;
            $totalComments = 0;
            $totalShares = 0;

            foreach ($videos as $v) {
                $title = $v['title'] ?? '';
                if (empty($title)) continue;

                $plays    = (int)($v['plays'] ?? 0);
                $likes    = (int)($v['likes'] ?? 0);
                $comments = (int)($v['comments'] ?? 0);
                $shares   = (int)($v['shares'] ?? 0);
                $pubTime  = $v['publish_time'] ?? date('Y-m-d H:i:s');

                $totalPlays    += $plays;
                $totalLikes    += $likes;
                $totalComments += $comments;
                $totalShares   += $shares;

                // 去重：同平台同账号同标题
                $chk = $pdo->prepare("SELECT id FROM " . table('video_data') . " WHERE platform = ? AND account_name = ? AND video_title = ? LIMIT 1");
                $chk->execute([$acc['platform'], $acc['account_name'], $title]);
                $existing = $chk->fetch();

                if ($existing) {
                    $pdo->prepare("UPDATE " . table('video_data') . " SET plays=?, likes=?, comments=?, shares=?, synced_at=NOW() WHERE id=?")
                        ->execute([$plays, $likes, $comments, $shares, $existing['id']]);
                } else {
                    $pdo->prepare("INSERT INTO " . table('video_data') . " (publish_id, platform, account_name, video_title, plays, likes, comments, shares, publish_time, synced_at) VALUES (0,?,?,?,?,?,?,?,?,NOW())")
                        ->execute([$acc['platform'], $acc['account_name'], $title, $plays, $likes, $comments, $shares, $pubTime]);
                    $newCount++;
                    $totalNew++;
                }
            }

            // 更新监控账号统计
            $pdo->prepare("UPDATE " . table('monitored_account') . " SET total_videos=?, total_plays=?, total_likes=?, total_comments=?, total_shares=?, last_sync=NOW(), status='active' WHERE id=?")
                ->execute([count($videos), $totalPlays, $totalLikes, $totalComments, $totalShares, $acc['id']]);

            $results[] = [
                'id'       => $acc['id'],
                'account'  => $acc['account_name'],
                'platform' => $acc['platform'],
                'found'    => count($videos),
                'new'      => $newCount,
                'updated'  => count($videos) - $newCount,
                'plays'    => $totalPlays,
                'likes'    => $totalLikes,
            ];
        } catch (Exception $e) {
            $results[] = ['id' => $acc['id'], 'account' => $acc['account_name'], 'platform' => $acc['platform'], 'error' => $e->getMessage()];
        }
    }

    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '数据统计', '同步数据', "同步了 " . count($results) . " 个账号, 新增 {$totalNew} 条");

    success(['results' => $results, 'total_new' => $totalNew], "同步完成，新增 {$totalNew} 条视频数据");
}

// ───────────────────────── 视频数据查询 ─────────────────────────

function getVideos()
{
    global $pdo;
    [$page, $pageSize, $offset] = getPageParams();
    $platform  = param('platform', '');
    $accountName = param('account_name', '');
    $startDate = param('startDate', '');
    $endDate   = param('endDate', '');

    $where  = "WHERE 1=1";
    $params = [];
    if ($platform)    { $where .= " AND platform = ?"; $params[] = $platform; }
    if ($accountName) { $where .= " AND account_name = ?"; $params[] = $accountName; }
    if ($startDate)   { $where .= " AND DATE(publish_time) >= ?"; $params[] = $startDate; }
    if ($endDate)     { $where .= " AND DATE(publish_time) <= ?"; $params[] = $endDate; }

    $st = $pdo->prepare("SELECT COUNT(*) FROM " . table('video_data') . " $where");
    $st->execute($params);
    $total = (int)$st->fetchColumn();

    $st = $pdo->prepare("SELECT * FROM " . table('video_data') . " $where ORDER BY publish_time DESC LIMIT $pageSize OFFSET $offset");
    $st->execute($params);
    $list = $st->fetchAll();

    foreach ($list as &$row) {
        $row['plays']    = (int)$row['plays'];
        $row['likes']    = (int)$row['likes'];
        $row['comments'] = (int)$row['comments'];
        $row['shares']   = (int)$row['shares'];
    }

    success(['list' => $list, 'total' => $total, 'page' => $page, 'pageSize' => $pageSize]);
}

// ───────────────────────── 汇总统计 ─────────────────────────

function getSummary()
{
    global $pdo;
    $platform  = param('platform', '');
    $accountName = param('account_name', '');
    $startDate = param('startDate', '');
    $endDate   = param('endDate', '');

    $where  = "WHERE 1=1";
    $params = [];
    if ($platform)    { $where .= " AND platform = ?"; $params[] = $platform; }
    if ($accountName) { $where .= " AND account_name = ?"; $params[] = $accountName; }
    if ($startDate)   { $where .= " AND DATE(publish_time) >= ?"; $params[] = $startDate; }
    if ($endDate)     { $where .= " AND DATE(publish_time) <= ?"; $params[] = $endDate; }

    // 总计
    $st = $pdo->prepare("SELECT COUNT(*) AS video_count, COALESCE(SUM(plays),0) AS plays, COALESCE(SUM(likes),0) AS likes, COALESCE(SUM(comments),0) AS comments, COALESCE(SUM(shares),0) AS shares FROM " . table('video_data') . " $where");
    $st->execute($params);
    $summary = $st->fetch();
    $summary['video_count'] = (int)$summary['video_count'];
    $summary['plays']       = (int)$summary['plays'];
    $summary['likes']       = (int)$summary['likes'];
    $summary['comments']    = (int)$summary['comments'];
    $summary['shares']      = (int)$summary['shares'];

    // 按平台分组
    $st = $pdo->prepare("SELECT platform, COUNT(*) AS video_count, COALESCE(SUM(plays),0) AS plays, COALESCE(SUM(likes),0) AS likes, COALESCE(SUM(comments),0) AS comments, COALESCE(SUM(shares),0) AS shares FROM " . table('video_data') . " $where GROUP BY platform");
    $st->execute($params);
    $platforms = $st->fetchAll();
    foreach ($platforms as &$p) {
        $p['video_count'] = (int)$p['video_count'];
        $p['plays']       = (int)$p['plays'];
        $p['likes']       = (int)$p['likes'];
        $p['comments']    = (int)$p['comments'];
        $p['shares']      = (int)$p['shares'];
    }

    // 按账号分组
    $st = $pdo->prepare("SELECT platform, account_name, COUNT(*) AS video_count, COALESCE(SUM(plays),0) AS plays, COALESCE(SUM(likes),0) AS likes, COALESCE(SUM(comments),0) AS comments, COALESCE(SUM(shares),0) AS shares FROM " . table('video_data') . " $where GROUP BY platform, account_name ORDER BY plays DESC");
    $st->execute($params);
    $accounts = $st->fetchAll();
    foreach ($accounts as &$a) {
        $a['video_count'] = (int)$a['video_count'];
        $a['plays']       = (int)$a['plays'];
        $a['likes']       = (int)$a['likes'];
        $a['comments']    = (int)$a['comments'];
        $a['shares']      = (int)$a['shares'];
    }

    success(['summary' => $summary, 'platforms' => $platforms, 'accounts' => $accounts]);
}

// ───────────────────────── Excel导出 ─────────────────────────

function exportExcel()
{
    global $pdo;
    $platform    = param('platform', '');
    $accountName = param('account_name', '');
    $startDate   = param('startDate', '');
    $endDate     = param('endDate', '');

    $where  = "WHERE 1=1";
    $params = [];
    if ($platform)    { $where .= " AND platform = ?"; $params[] = $platform; }
    if ($accountName) { $where .= " AND account_name = ?"; $params[] = $accountName; }
    if ($startDate)   { $where .= " AND DATE(publish_time) >= ?"; $params[] = $startDate; }
    if ($endDate)     { $where .= " AND DATE(publish_time) <= ?"; $params[] = $endDate; }

    $st = $pdo->prepare("SELECT platform, account_name, video_title, plays, likes, comments, shares, publish_time FROM " . table('video_data') . " $where ORDER BY publish_time DESC");
    $st->execute($params);
    $rows = $st->fetchAll();

    $platformNames = ['douyin'=>'抖音','kuaishou'=>'快手','xiaohongshu'=>'小红书','weixin'=>'视频号'];

    // 生成CSV（兼容Excel）
    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename=video_data_' . date('YmdHis') . '.csv');
    echo "\xEF\xBB\xBF"; // UTF-8 BOM
    echo "平台,账号,视频标题,播放量,点赞量,评论量,分享量,发布时间\n";
    foreach ($rows as $row) {
        $pn = $platformNames[$row['platform']] ?? $row['platform'];
        $title = str_replace(['"', "\n", "\r"], ['""', '', ''], $row['video_title']);
        echo "\"{$pn}\",\"{$row['account_name']}\",\"{$title}\",{$row['plays']},{$row['likes']},{$row['comments']},{$row['shares']},\"{$row['publish_time']}\"\n";
    }
    exit;
}

// ───────────────────────── 爬虫实现 ─────────────────────────

/**
 * 从账号URL中提取sec_uid
 */
function extractSecUid(string $platform, string $url): string
{
    if (empty($url)) return '';

    switch ($platform) {
        case 'douyin':
            // https://www.douyin.com/user/MS4wLjABAAAAxxxxxx
            if (preg_match('#/user/([A-Za-z0-9_-]+)#', $url, $m)) return $m[1];
            // https://v.douyin.com/xxxxxx 需要跟踪重定向
            if (preg_match('#v\.douyin\.com#', $url)) {
                $ch = curl_init($url);
                curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER=>true, CURLOPT_FOLLOWLOCATION=>false, CURLOPT_NOBODY=>true, CURLOPT_TIMEOUT=>5]);
                curl_exec($ch);
                $redirect = curl_getinfo($ch, CURLINFO_EFFECTIVE_URL);
                curl_close($ch);
                if (preg_match('#/user/([A-Za-z0-9_-]+)#', $redirect, $m)) return $m[1];
            }
            break;
        case 'kuaishou':
            if (preg_match('#/profile/([A-Za-z0-9_-]+)#', $url, $m)) return $m[1];
            break;
        case 'xiaohongshu':
            if (preg_match('#/user/profile/([a-f0-9]+)#', $url, $m)) return $m[1];
            break;
    }
    return '';
}

/**
 * 爬取监控账号的公开视频数据
 */
function crawlAccountVideos(string $platform, string $accountUrl, string $secUid): ?array
{
    switch ($platform) {
        case 'douyin':  return crawlDouyinPublic($secUid, $accountUrl);
        case 'kuaishou': return crawlKuaishouPublic($secUid, $accountUrl);
        case 'xiaohongshu': return crawlXhsPublic($secUid, $accountUrl);
        case 'weixin':  return crawlWeixinPublic($accountUrl);
        default: return null;
    }
}

function httpFetch(string $url, array $headers = [], string $cookie = '', int $timeout = 15): ?string
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
        CURLOPT_USERAGENT      => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    ]);
    if ($cookie) curl_setopt($ch, CURLOPT_COOKIE, $cookie);
    $resp = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($resp === false || $code >= 400) return null;
    return $resp;
}

function crawlDouyinPublic(string $secUid, string $accountUrl): ?array
{
    // 如果没有secUid，尝试从URL获取
    if (empty($secUid) && !empty($accountUrl)) {
        $secUid = extractSecUid('douyin', $accountUrl);
    }
    if (empty($secUid)) return null;

    $headers = [
        'Accept: application/json, text/plain, */*',
        'Referer: https://www.douyin.com/',
    ];

    $videos = [];
    $cursor = 0;
    $maxPages = 5;

    for ($page = 0; $page < $maxPages; $page++) {
        $url = "https://www.douyin.com/aweme/v1/web/aweme/post/?sec_user_id={$secUid}&count=20&max_cursor={$cursor}&aid=6383&cookie_enabled=true";
        $resp = httpFetch($url, $headers);
        if (!$resp) { if ($page === 0) return null; break; }

        $data = json_decode($resp, true);
        if (!$data) { if ($page === 0) return null; break; }

        $list = $data['aweme_list'] ?? [];
        if (empty($list)) break;

        foreach ($list as $item) {
            $stats = $item['statistics'] ?? [];
            $videos[] = [
                'title'        => $item['desc'] ?? '',
                'plays'        => (int)($stats['play_count'] ?? 0),
                'likes'        => (int)($stats['digg_count'] ?? 0),
                'comments'     => (int)($stats['comment_count'] ?? 0),
                'shares'       => (int)($stats['share_count'] ?? 0),
                'publish_time' => isset($item['create_time']) ? date('Y-m-d H:i:s', $item['create_time']) : date('Y-m-d H:i:s'),
            ];
        }

        $hasMore = $data['has_more'] ?? 0;
        if (!$hasMore) break;
        $cursor = $data['max_cursor'] ?? 0;
        usleep(800000);
    }

    return $videos;
}

function crawlKuaishouPublic(string $secUid, string $accountUrl): ?array
{
    if (empty($secUid) && !empty($accountUrl)) {
        $secUid = extractSecUid('kuaishou', $accountUrl);
    }
    if (empty($secUid)) return null;

    $headers = [
        'Accept: application/json, text/plain, */*',
        'Referer: https://www.kuaishou.com/',
        'Content-Type: application/json',
    ];

    $videos = [];
    $pcursor = '';
    $maxPages = 5;

    for ($page = 0; $page < $maxPages; $page++) {
        $body = json_encode([
            'operationName' => 'visionProfilePhotoList',
            'variables' => ['userId' => $secUid, 'pcursor' => $pcursor, 'page' => 'profile'],
            'query' => 'query visionProfilePhotoList($userId: String, $pcursor: String, $page: String) { visionProfilePhotoList(userId: $userId, pcursor: $pcursor, page: $page) { list { id duration coverUrl viewCount likeCount commentCount shareCount caption timestamp } pcursor } }',
        ]);

        $ch = curl_init('https://www.kuaishou.com/graphql');
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $body,
            CURLOPT_HTTPHEADER => $headers,
            CURLOPT_TIMEOUT => 15,
            CURLOPT_SSL_VERIFYPEER => false,
            CURLOPT_USERAGENT => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        ]);
        $resp = curl_exec($ch);
        curl_close($ch);

        if (!$resp) { if ($page === 0) return null; break; }
        $data = json_decode($resp, true);
        if (!$data) { if ($page === 0) return null; break; }

        $list = $data['data']['visionProfilePhotoList']['list'] ?? [];
        if (empty($list)) break;

        foreach ($list as $item) {
            $videos[] = [
                'title'        => $item['caption'] ?? '',
                'plays'        => (int)($item['viewCount'] ?? 0),
                'likes'        => (int)($item['likeCount'] ?? 0),
                'comments'     => (int)($item['commentCount'] ?? 0),
                'shares'       => (int)($item['shareCount'] ?? 0),
                'publish_time' => isset($item['timestamp']) ? date('Y-m-d H:i:s', (int)($item['timestamp'] / 1000)) : date('Y-m-d H:i:s'),
            ];
        }

        $pcursor = $data['data']['visionProfilePhotoList']['pcursor'] ?? '';
        if (empty($pcursor) || $pcursor === 'no_more') break;
        usleep(800000);
    }

    return $videos;
}

function crawlXhsPublic(string $secUid, string $accountUrl): ?array
{
    if (empty($secUid) && !empty($accountUrl)) {
        $secUid = extractSecUid('xiaohongshu', $accountUrl);
    }
    if (empty($secUid)) return null;

    $headers = [
        'Accept: application/json, text/plain, */*',
        'Referer: https://www.xiaohongshu.com/',
    ];

    $videos = [];
    $cursor = '';
    $maxPages = 5;

    for ($page = 0; $page < $maxPages; $page++) {
        $url = "https://edith.xiaohongshu.com/api/sns/web/v1/user_posted?num=20&cursor={$cursor}&user_id={$secUid}";
        $resp = httpFetch($url, $headers);
        if (!$resp) { if ($page === 0) return null; break; }

        $data = json_decode($resp, true);
        if (!$data || ($data['code'] ?? -1) !== 0) { if ($page === 0) return null; break; }

        $notes = $data['data']['notes'] ?? [];
        if (empty($notes)) break;

        foreach ($notes as $note) {
            $interact = $note['interact_info'] ?? [];
            $videos[] = [
                'title'        => $note['display_title'] ?? $note['title'] ?? '',
                'plays'        => (int)($interact['view_count'] ?? 0),
                'likes'        => (int)($interact['liked_count'] ?? 0),
                'comments'     => (int)($interact['comment_count'] ?? 0),
                'shares'       => (int)($interact['share_count'] ?? 0),
                'publish_time' => isset($note['time']) ? date('Y-m-d H:i:s', (int)($note['time'] / 1000)) : date('Y-m-d H:i:s'),
            ];
        }

        $cursor = $data['data']['cursor'] ?? '';
        $hasMore = $data['data']['has_more'] ?? false;
        if (!$hasMore || empty($cursor)) break;
        usleep(800000);
    }

    return $videos;
}

function crawlWeixinPublic(string $accountUrl): ?array
{
    // 微信视频号需要认证才能获取数据，暂不支持公开爬取
    // 可以后续通过客户端Cookie方式实现
    return null;
}
