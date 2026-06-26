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
$action      = $segments[1] ?? ($_GET['_r'] ?? '');

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
    case 'ping':
        success(['ok' => true, 'user' => $currentUser, 'method' => $method, 'action' => $action, 'segments' => $segments]);
        break;
    case 'log':
        $logFile = dirname(__DIR__) . '/logs/scraper.log';
        $lines = 50;
        if (file_exists($logFile)) {
            $content = file_get_contents($logFile);
            $allLines = explode("\n", trim($content));
            $tail = array_slice($allLines, -$lines);
            success(['log' => implode("\n", $tail), 'total_lines' => count($allLines)]);
        } else {
            success(['log' => '暂无日志', 'total_lines' => 0]);
        }
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

function ensureMonitoredTable()
{
    global $pdo;
    $tableName = table('monitored_account');
    $exists = $pdo->query("SHOW TABLES LIKE '{$tableName}'")->fetch();
    if (!$exists) {
        $pdo->exec("CREATE TABLE IF NOT EXISTS `{$tableName}` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `platform` ENUM('douyin','kuaishou','xiaohongshu','weixin') NOT NULL,
            `account_name` VARCHAR(100) NOT NULL,
            `account_url` VARCHAR(500) DEFAULT '',
            `sec_uid` VARCHAR(200) DEFAULT '',
            `total_videos` INT DEFAULT 0,
            `total_plays` BIGINT DEFAULT 0,
            `total_likes` BIGINT DEFAULT 0,
            `total_comments` BIGINT DEFAULT 0,
            `total_shares` BIGINT DEFAULT 0,
            `last_sync` DATETIME,
            `status` ENUM('active','error') DEFAULT 'active',
            `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX `idx_platform` (`platform`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    }
}

function getList()
{
    global $pdo;
    ensureMonitoredTable();
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
    ensureMonitoredTable();
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
    try {
        ensureMonitoredTable();
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
                $errMsg = '爬取失败';
                $cookie = getStoredCookie($acc['platform']);
                if (empty($cookie)) {
                    $errMsg = '请先在「账号管理」中登录该平台账号后再同步';
                } else {
                    $errMsg = '爬取失败，请确认账号ID是否正确，或该平台Cookie是否有效';
                }
                $results[] = ['id' => $acc['id'], 'account' => $acc['account_name'], 'platform' => $acc['platform'], 'error' => $errMsg];
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
    } catch (Throwable $e) {
        error('同步异常: ' . $e->getMessage(), 500);
    }
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
 * 获取已保存的平台Cookie（从 platform_account 表）
 */
function getStoredCookie(string $platform): string
{
    global $pdo;
    $st = $pdo->prepare("SELECT cookie FROM " . table('platform_account') . " WHERE platform = ? AND status = 'active' AND cookie IS NOT NULL AND cookie != '' ORDER BY id DESC LIMIT 1");
    $st->execute([$platform]);
    $row = $st->fetch();
    return $row ? $row['cookie'] : '';
}

/**
 * 写爬虫日志
 */
function scraperLog(string $msg)
{
    $logDir = dirname(__DIR__) . '/logs';
    if (!is_dir($logDir)) @mkdir($logDir, 0755, true);
    @file_put_contents($logDir . '/scraper.log', date('Y-m-d H:i:s') . " {$msg}\n", FILE_APPEND | LOCK_EX);
}

/**
 * 爬取监控账号的视频数据
 * 优先使用已保存的平台Cookie，没有则尝试公开API
 */
function crawlAccountVideos(string $platform, string $accountUrl, string $secUid): ?array
{
    switch ($platform) {
        case 'douyin':      return crawlDouyin($secUid, $accountUrl);
        case 'kuaishou':    return crawlKuaishou($secUid, $accountUrl);
        case 'xiaohongshu': return crawlXhs($secUid, $accountUrl);
        case 'weixin':      return crawlWeixin($accountUrl);
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
    $err  = curl_error($ch);
    $curlErr = curl_errno($ch);
    curl_close($ch);
    scraperLog("GET {$url} => HTTP {$code} curl={$curlErr} " . ($err ? "err: {$err}" : 'len=' . strlen($resp ?: '')));
    if ($resp === false || $code >= 400) return null;
    return $resp;
}

function httpPost(string $url, array $headers, string $cookie, string $body, int $timeout = 15): ?string
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
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $body,
    ]);
    if ($cookie) curl_setopt($ch, CURLOPT_COOKIE, $cookie);
    $resp = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    scraperLog("POST {$url} => HTTP {$code} resp_len=" . strlen($resp ?: ''));
    if ($resp === false || $code >= 400) return null;
    return $resp;
}

// ══════════════════════════════════════════════════════════════
// 抖音爬虫 - 使用已登录账号Cookie
// ══════════════════════════════════════════════════════════════

/**
 * 获取抖音ttwid（通过注册接口）
 */
function getDouyinTtwid(): string
{
    // 方法1: 从首页 Set-Cookie 获取
    $ch = curl_init('https://www.douyin.com/');
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 15,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_HEADER         => true,
        CURLOPT_USERAGENT      => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    ]);
    $resp = curl_exec($ch);
    curl_close($ch);
    $ttwid = '';
    if ($resp && preg_match_all('/^Set-Cookie:\s*ttwid=([^;\r\n]*)/mi', $resp, $matches)) {
        $ttwid = $matches[1][0] ?? '';
    }
    if ($ttwid) { scraperLog('[抖音] ttwid获取成功(首页)'); return $ttwid; }

    // 方法2: 通过注册接口获取
    $body = json_encode([
        'region'  => 'cn',
        'aid'     => 1768,
        'needFid' => false,
        'service' => 'www.douyin.com',
        'migrate_info' => ['ticket' => '', 'source' => 'node'],
        'cbUrlProtocol' => 'https',
        'union' => true,
    ]);
    $ch = curl_init('https://ttwid.bytedance.com/ttwid/union/register/');
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 10,
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $body,
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_HEADER         => true,
        CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
        CURLOPT_USERAGENT      => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    ]);
    $resp = curl_exec($ch);
    curl_close($ch);
    if ($resp && preg_match('/^Set-Cookie:\s*ttwid=([^;\r\n]*)/mi', $resp, $m)) {
        $ttwid = $m[1];
        scraperLog('[抖音] ttwid获取成功(注册接口)');
    } else {
        scraperLog('[抖音] ttwid获取失败 resp=' . ($resp ? substr($resp, 0, 300) : 'NULL'));
    }
    return $ttwid;
}

function crawlDouyin(string $secUid, string $accountUrl): ?array
{
    if (empty($secUid) && !empty($accountUrl)) {
        $secUid = extractSecUid('douyin', $accountUrl);
    }
    if (empty($secUid)) {
        scraperLog('[抖音] sec_uid 为空，accountUrl=' . $accountUrl);
        return null;
    }

    $videos = [];

    // 方案1: 用已登录Cookie走抖音网页版（查看任意用户）
    $cookie = getStoredCookie('douyin');
    if (!empty($cookie)) {
        scraperLog('[抖音] 使用已登录Cookie, len=' . strlen($cookie));
        $headers = [
            'Accept: application/json, text/plain, */*',
            'Referer: https://www.douyin.com/user/' . $secUid,
        ];
        $cursor = 0;
        for ($page = 0; $page < 10; $page++) {
            $url = "https://www.douyin.com/aweme/v1/web/aweme/post/?sec_user_id={$secUid}&count=20&max_cursor={$cursor}&aid=1128&version_name=23.5.0";
            $resp = httpFetch($url, $headers, $cookie);
            scraperLog('[抖音] 已登录Cookie page=' . $page . ' resp=' . ($resp ? 'len=' . strlen($resp) : 'NULL'));
            if (!$resp) break;
            $data = json_decode($resp, true);
            if (!$data) break;
            $list = $data['aweme_list'] ?? [];
            if (empty($list)) { scraperLog('[抖音] 列表为空, status_code=' . ($data['status_code'] ?? 'null')); break; }
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
            if (!($data['has_more'] ?? 0)) break;
            $cursor = $data['max_cursor'] ?? 0;
            usleep(500000);
        }
    }

    // 方案2: iesdouyin 分享接口
    if (empty($videos)) {
        $headers = ['Accept: application/json'];
        $cursor = 0;
        for ($page = 0; $page < 10; $page++) {
            $url = "https://www.iesdouyin.com/web/api/v2/aweme/post/?sec_uid={$secUid}&count=20&max_cursor={$cursor}";
            $resp = httpFetch($url, $headers);
            scraperLog('[抖音] iesdouyin page=' . $page . ' resp=' . ($resp ? 'len=' . strlen($resp) : 'NULL'));
            if (!$resp) break;
            $data = json_decode($resp, true);
            if (!$data) break;
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
            if (!($data['has_more'] ?? 0)) break;
            $cursor = $data['max_cursor'] ?? 0;
            usleep(500000);
        }
    }

    // 方案3: 解析主页SSR
    if (empty($videos)) {
        scraperLog('[抖音] 前两种方式无数据，尝试SSR解析');
        $videos = crawlDouyinSSR($secUid);
    }

    scraperLog('[抖音] secUid=' . $secUid . ' 共获取 ' . count($videos) . ' 条视频');
    return empty($videos) ? null : $videos;
}

function crawlDouyinSSR(string $secUid): array
{
    $videos = [];

    // 尝试移动端分享页（反爬较弱）
    $ch = curl_init('https://www.iesdouyin.com/share/user/' . $secUid);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 15,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_ENCODING       => 'gzip, deflate',
        CURLOPT_USERAGENT      => 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
    ]);
    $html = curl_exec($ch);
    curl_close($ch);

    if ($html) {
        // 尝试提取 _ROUTER_DATA 或 RENDER_DATA
        foreach (['RENDER_DATA', '__ROUTER_DATA', '_ROUTER_DATA'] as $scriptId) {
            if (preg_match('/<script id="' . $scriptId . '"[^>]*>([^<]+)<\/script>/', $html, $m)) {
                $json = json_decode(urldecode($m[1]), true);
                $awemeList = findKey($json ?? [], 'aweme_list');
                if ($awemeList) {
                    foreach ($awemeList as $item) {
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
                    scraperLog('[抖音SSR] 从' . $scriptId . '提取 ' . count($videos) . ' 条');
                    return $videos;
                }
            }
        }
        scraperLog('[抖音SSR] 未找到嵌入数据, html_len=' . strlen($html) . ' sample=' . substr(strip_tags($html), 0, 200));
    } else {
        scraperLog('[抖音SSR] 请求失败');
    }
    return $videos;
}

function findKey($arr, string $key)
{
    if (!is_array($arr)) return null;
    if (isset($arr[$key])) return $arr[$key];
    foreach ($arr as $v) { $r = findKey($v, $key); if ($r !== null) return $r; }
    return null;
}

// ══════════════════════════════════════════════════════════════
// 快手爬虫 - 使用已登录账号Cookie + GraphQL
// ══════════════════════════════════════════════════════════════

/**
 * 获取快手Cookie
 */
function getKuaishouCookie(): string
{
    $ch = curl_init('https://www.kuaishou.com/');
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 15,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_HEADER         => true,
        CURLOPT_USERAGENT      => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    ]);
    $resp = curl_exec($ch);
    curl_close($ch);
    $cookieStr = '';
    if ($resp && preg_match_all('/^Set-Cookie:\s*([^;\r\n]*)/mi', $resp, $matches)) {
        foreach ($matches[1] as $c) $cookieStr .= $c . '; ';
    }
    return rtrim($cookieStr, '; ');
}

function crawlKuaishou(string $secUid, string $accountUrl): ?array
{
    if (empty($secUid) && !empty($accountUrl)) {
        $secUid = extractSecUid('kuaishou', $accountUrl);
    }
    if (empty($secUid)) {
        scraperLog('[快手] userId 为空，无法爬取');
        return null;
    }

    // 使用公开主页API
    $cookie = getKuaishouCookie();
    scraperLog('[快手] userId=' . $secUid . ' cookie_len=' . strlen($cookie));

    $headers = [
        'Accept: application/json, text/plain, */*',
        'Referer: https://www.kuaishou.com/profile/' . $secUid,
        'Content-Type: application/json',
    ];

    $videos = [];
    $pcursor = '';
    $maxPages = 10;

    for ($page = 0; $page < $maxPages; $page++) {
        $body = json_encode([
            'operationName' => 'visionProfilePhotoList',
            'variables'    => ['userId' => $secUid, 'pcursor' => $pcursor, 'page' => 'profile'],
            'query'        => 'query visionProfilePhotoList($userId: String, $pcursor: String, $page: String) { visionProfilePhotoList(userId: $userId, pcursor: $pcursor, page: $page) { list { id duration coverUrl viewCount likeCount commentCount shareCount caption timestamp } pcursor } }',
        ]);

        $resp = httpPost('https://www.kuaishou.com/graphql', $headers, $cookie, $body);
        scraperLog('[快手] page=' . $page . ' resp=' . ($resp ? substr($resp, 0, 300) : 'NULL'));
        if (!$resp) { if ($page === 0) return null; break; }

        $data = json_decode($resp, true);
        if (!$data) { if ($page === 0) return null; break; }

        $list = $data['data']['visionProfilePhotoList']['list'] ?? $data['data']['photoFeed']['list'] ?? [];
        if (empty($list)) break;

        foreach ($list as $item) {
            $videos[] = [
                'title'        => $item['caption'] ?? $item['title'] ?? '',
                'plays'        => (int)($item['viewCount'] ?? 0),
                'likes'        => (int)($item['likeCount'] ?? 0),
                'comments'     => (int)($item['commentCount'] ?? 0),
                'shares'       => (int)($item['shareCount'] ?? 0),
                'publish_time' => isset($item['timestamp']) ? date('Y-m-d H:i:s', (int)($item['timestamp'] / 1000)) : date('Y-m-d H:i:s'),
            ];
        }

        $pcursor = $data['data']['visionProfilePhotoList']['pcursor'] ?? '';
        if (empty($pcursor) || $pcursor === 'no_more') break;
        usleep(500000);
    }

    scraperLog('[快手] userId=' . $secUid . ' 共获取 ' . count($videos) . ' 条视频');
    return empty($videos) ? null : $videos;
}

// ══════════════════════════════════════════════════════════════
// 小红书爬虫 - 使用已登录账号Cookie
// ══════════════════════════════════════════════════════════════

/**
 * 获取小红书Cookie
 */
function getXhsCookie(): string
{
    $ch = curl_init('https://www.xiaohongshu.com/');
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 15,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_HEADER         => true,
        CURLOPT_USERAGENT      => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    ]);
    $resp = curl_exec($ch);
    curl_close($ch);
    $cookieStr = '';
    if ($resp && preg_match_all('/^Set-Cookie:\s*([^;\r\n]*)/mi', $resp, $matches)) {
        foreach ($matches[1] as $c) $cookieStr .= $c . '; ';
    }
    return rtrim($cookieStr, '; ');
}

function crawlXhs(string $secUid, string $accountUrl): ?array
{
    if (empty($secUid) && !empty($accountUrl)) {
        $secUid = extractSecUid('xiaohongshu', $accountUrl);
    }
    if (empty($secUid)) {
        scraperLog('[小红书] userId 为空，无法爬取');
        return null;
    }

    // 使用公开API
    $cookie = getXhsCookie();
    scraperLog('[小红书] userId=' . $secUid . ' cookie_len=' . strlen($cookie));

    $headers = [
        'Accept: application/json, text/plain, */*',
        'Referer: https://www.xiaohongshu.com/user/profile/' . $secUid,
    ];

    $videos = [];
    $cursor = '';
    $maxPages = 10;

    for ($page = 0; $page < $maxPages; $page++) {
        $url = "https://edith.xiaohongshu.com/api/sns/web/v1/user_posted?num=20&cursor=" . urlencode($cursor) . "&user_id=" . urlencode($secUid) . "&image_formats=jpg,webp,avif";
        $resp = httpFetch($url, $headers, $cookie);
        scraperLog('[小红书] page=' . $page . ' resp=' . ($resp ? substr($resp, 0, 300) : 'NULL'));
        if (!$resp) { if ($page === 0) return null; break; }

        $data = json_decode($resp, true);
        if (!$data) { if ($page === 0) return null; break; }

        $notes = $data['data']['notes'] ?? $data['data']['list'] ?? $data['notes'] ?? [];
        if (empty($notes)) break;

        foreach ($notes as $note) {
            $interact = $note['interactInfo'] ?? $note['interact_info'] ?? [];
            $videos[] = [
                'title'        => $note['title'] ?? $note['displayTitle'] ?? $note['display_title'] ?? '',
                'plays'        => (int)($interact['viewCount'] ?? $interact['view_count'] ?? 0),
                'likes'        => (int)($interact['likedCount'] ?? $interact['liked_count'] ?? 0),
                'comments'     => (int)($interact['commentCount'] ?? $interact['comment_count'] ?? 0),
                'shares'       => (int)($interact['shareCount'] ?? $interact['share_count'] ?? 0),
                'publish_time' => isset($note['time']) ? date('Y-m-d H:i:s', (int)($note['time'] / 1000)) : ($note['createTime'] ?? date('Y-m-d H:i:s')),
            ];
        }

        $cursor = $data['data']['cursor'] ?? $data['cursor'] ?? '';
        $hasMore = $data['data']['has_more'] ?? $data['hasMore'] ?? false;
        if (!$hasMore || empty($cursor)) break;
        usleep(500000);
    }

    scraperLog('[小红书] userId=' . $secUid . ' 共获取 ' . count($videos) . ' 条笔记');
    return empty($videos) ? null : $videos;
}

// ══════════════════════════════════════════════════════════════
// 视频号爬虫
// ══════════════════════════════════════════════════════════════

function crawlWeixin(string $accountUrl): ?array
{
    $cookie = getStoredCookie('weixin');
    if (empty($cookie)) {
        scraperLog('[视频号] 无可用Cookie，请先在「账号管理」中登录至少一个视频号账号');
        return null;
    }

    $headers = [
        'Accept: application/json, text/plain, */*',
        'Referer: https://channels.weixin.qq.com/',
        'Origin: https://channels.weixin.qq.com',
        'Content-Type: application/json',
    ];

    $videos = [];
    $maxPages = 10;
    $lastBuffId = '';

    for ($page = 0; $page < $maxPages; $page++) {
        $body = json_encode(['count' => 20, 'lastBuffId' => $lastBuffId]);
        $resp = httpPost('https://channels.weixin.qq.com/cgi-bin/mmfinderassistant-bin/post/getpostlist', $headers, $cookie, $body);
        if (!$resp) { if ($page === 0) return null; break; }

        $data = json_decode($resp, true);
        if (!$data) { if ($page === 0) return null; break; }

        $list = $data['data']['list'] ?? $data['data']['postList'] ?? [];
        if (empty($list)) break;

        foreach ($list as $item) {
            $videos[] = [
                'title'        => $item['title'] ?? $item['desc'] ?? '',
                'plays'        => (int)($item['readCount'] ?? $item['viewCount'] ?? 0),
                'likes'        => (int)($item['likeCount'] ?? $item['favorCount'] ?? 0),
                'comments'     => (int)($item['commentCount'] ?? 0),
                'shares'       => (int)($item['shareCount'] ?? $item['forwardCount'] ?? 0),
                'publish_time' => isset($item['createTime']) ? date('Y-m-d H:i:s', (int)$item['createTime']) : date('Y-m-d H:i:s'),
            ];
        }

        $lastBuffId = $data['data']['lastBuffId'] ?? '';
        $hasMore = $data['data']['hasMore'] ?? true;
        if (!$hasMore || empty($lastBuffId)) break;
        usleep(500000);
    }

    scraperLog("[视频号] 获取 " . count($videos) . " 条视频");
    return empty($videos) ? null : $videos;
}
