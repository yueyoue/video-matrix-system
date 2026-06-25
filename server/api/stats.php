<?php
// 如果已通过 index.php 路由加载（includes 已定义），跳过自包含初始化
if (function_exists('success')) {
    // 已经通过 index.php 路由加载，使用全局函数
    // 解析路由
    $segments = $GLOBALS['route_segments'] ?? [];
    $action = $segments[1] ?? 'overview';
    $today = date('Y-m-d');
    global $pdo;
    switch ($action) {
        case 'overview':
            $currentUser = requireAuth();
            $r = [];
            $r['total_users'] = (int)$pdo->query('SELECT COUNT(*) FROM ' . table('sys_user'))->fetchColumn();
            $st = $pdo->prepare('SELECT COUNT(*) FROM ' . table('video_task') . ' WHERE DATE(created_at)=?'); $st->execute([$today]); $r['today_videos'] = (int)$st->fetchColumn();
            $st = $pdo->prepare('SELECT COUNT(*) FROM ' . table('publish_record') . ' WHERE DATE(created_at)=? AND status=?'); $st->execute([$today, 'success']); $r['today_publish_success'] = (int)$st->fetchColumn();
            $st = $pdo->prepare('SELECT COUNT(*) FROM ' . table('publish_record') . ' WHERE DATE(created_at)=? AND status=?'); $st->execute([$today, 'failed']); $r['today_publish_failed'] = (int)$st->fetchColumn();
            $tot = $r['today_publish_success'] + $r['today_publish_failed'];
            $r['success_rate'] = $tot > 0 ? round($r['today_publish_success'] / $tot * 100, 1) : 0;

            // 管理账号数
            $r['accountCount'] = (int)$pdo->query('SELECT COUNT(*) FROM ' . table('platform_account'))->fetchColumn();

            // 最近发布记录
            $st = $pdo->prepare('SELECT pr.platform, pr.account_name AS accountName, pr.video_title AS videoTitle, pr.published_time AS time, pr.status FROM ' . table('publish_record') . ' pr ORDER BY pr.id DESC LIMIT 10');
            $st->execute();
            $r['recentPublish'] = $st->fetchAll();

            // 异常预警
            $st = $pdo->prepare("SELECT nickname, platform FROM " . table('platform_account') . " WHERE status = 'expired' ORDER BY id DESC LIMIT 10");
            $st->execute();
            $expiredAccounts = $st->fetchAll();
            $alerts = [];
            foreach ($expiredAccounts as $acc) {
                $platformName = match($acc['platform']) { 'douyin'=>'抖音', 'kuaishou'=>'快手', 'xiaohongshu'=>'小红书', 'weixin'=>'视频号', default=>$acc['platform'] };
                $alerts[] = ['message'=>"{$platformName}账号 {$acc['nickname']} 登录失效", 'text'=>'Cookie已过期，请重新扫码登录'];
            }
            // 视频数据统计
            $r['video_data_count'] = (int)$pdo->query('SELECT COUNT(*) FROM ' . table('video_data'))->fetchColumn();
            $vStats = $pdo->query('SELECT COALESCE(SUM(plays),0) AS tp, COALESCE(SUM(likes),0) AS tl FROM ' . table('video_data'))->fetch();
            $r['total_plays'] = (int)($vStats['tp'] ?? 0);
            $r['total_likes'] = (int)($vStats['tl'] ?? 0);
            $aStats = $pdo->query('SELECT COALESCE(SUM(works_count),0) AS tw, COALESCE(SUM(total_plays),0) AS atp FROM ' . table('platform_account'))->fetch();
            $r['total_works'] = (int)($aStats['tw'] ?? 0);
            if ($r['total_plays'] == 0 && (int)($aStats['atp'] ?? 0) > 0) $r['total_plays'] = (int)($aStats['atp'] ?? 0);
            // 无数据提示
            if ($r['video_data_count'] == 0) {
                $actAcc = (int)$pdo->query('SELECT COUNT(*) FROM ' . table('platform_account') . " WHERE status='active' AND cookie IS NOT NULL AND cookie != ''")->fetchColumn();
                if ($actAcc > 0) $alerts[] = ['message'=>'视频数据为空，请点击「同步平台数据」拉取','text'=>'已登录 '.$actAcc.' 个账号，但尚未同步视频数据'];
                else $alerts[] = ['message'=>'暂无已登录的平台账号','text'=>'请先在「账号管理」中添加并登录平台账号'];
            }
            $r['alerts'] = $alerts;

            success($r);
            break;
        case 'users':
            $currentUser = requireAuth();
            $st = $pdo->query('SELECT u.id,u.username,u.role,(SELECT COUNT(*) FROM ' . table('video_task') . ' v WHERE v.user_id=u.id AND DATE(v.created_at)=\'' . date('Y-m-d') . '\') as today_videos FROM ' . table('sys_user') . ' u ORDER BY u.id DESC');
            success($st->fetchAll());
            break;
        case 'platforms':
            $currentUser = requireAuth();
            $result = [];
            foreach (['douyin','kuaishou','xiaohongshu','weixin'] as $p) {
                $st = $pdo->prepare('SELECT COUNT(*) FROM ' . table('platform_account') . ' WHERE platform=?'); $st->execute([$p]); $acc = (int)$st->fetchColumn();
                $st = $pdo->prepare('SELECT COUNT(*) FROM ' . table('publish_record') . ' WHERE platform=? AND DATE(created_at)=?'); $st->execute([$p, $today]); $pub = (int)$st->fetchColumn();
                $st = $pdo->prepare('SELECT COUNT(*) FROM ' . table('publish_record') . ' WHERE platform=? AND DATE(created_at)=? AND status=?'); $st->execute([$p, $today, 'success']); $suc = (int)$st->fetchColumn();
                $result[] = ['platform'=>$p, 'accounts'=>$acc, 'today_publish'=>$pub, 'success_rate'=>$pub>0?round($suc/$pub*100,1):0];
            }
            success($result);
            break;
        case 'analysis':
            $currentUser = requireAuth();
            $type      = param('type', 'summary');
            $startDate = param('startDate', date('Y-m-d'));
            $endDate   = param('endDate', date('Y-m-d'));
            $platform  = param('platform', '');
            $page      = max(1, (int)param('page', 1));
            $pageSize  = 20;
            $offset    = ($page - 1) * $pageSize;

            $where = 'WHERE 1=1';
            $params = [];
            if ($startDate) { $where .= ' AND DATE(v.publish_time) >= ?'; $params[] = $startDate; }
            if ($endDate)   { $where .= ' AND DATE(v.publish_time) <= ?'; $params[] = $endDate; }
            if ($platform)  { $where .= ' AND v.platform = ?'; $params[] = $platform; }

            switch ($type) {
                case 'summary':
                    $st = $pdo->prepare('SELECT COALESCE(SUM(v.plays),0) AS totalPlays, COALESCE(SUM(v.likes),0) AS totalLikes, COALESCE(SUM(v.comments),0) AS totalComments, COALESCE(SUM(v.shares),0) AS totalShares FROM ' . table('video_data') . " v $where");
                    $st->execute($params);
                    $r = $st->fetch();
                    $r['totalPlays']   = (int)$r['totalPlays'];
                    $r['totalLikes']   = (int)$r['totalLikes'];
                    $r['totalComments'] = (int)$r['totalComments'];
                    $r['totalShares']  = (int)$r['totalShares'];
                    success($r);
                    break;

                case 'platform':
                    $st = $pdo->prepare('SELECT v.platform, COUNT(*) AS accountCount, COALESCE(SUM(v.plays),0) AS playCount, COALESCE(SUM(v.likes),0) AS likeCount, COALESCE(SUM(v.comments),0) AS commentCount, COALESCE(SUM(v.shares),0) AS shareCount, COUNT(*) AS publishCount FROM ' . table('video_data') . " v $where GROUP BY v.platform");
                    $st->execute($params);
                    $rows = $st->fetchAll();
                    foreach ($rows as &$row) {
                        $row['playCount']    = (int)$row['playCount'];
                        $row['likeCount']    = (int)$row['likeCount'];
                        $row['commentCount'] = (int)$row['commentCount'];
                        $row['shareCount']   = (int)$row['shareCount'];
                        $row['publishCount'] = (int)$row['publishCount'];
                    }
                    success(['list' => $rows]);
                    break;

                case 'video':
                    $countSt = $pdo->prepare('SELECT COUNT(*) FROM ' . table('video_data') . " v $where");
                    $countSt->execute($params);
                    $total = (int)$countSt->fetchColumn();
                    $st = $pdo->prepare('SELECT v.* FROM ' . table('video_data') . " v $where ORDER BY v.publish_time DESC LIMIT $pageSize OFFSET $offset");
                    $st->execute($params);
                    $rows = $st->fetchAll();
                    foreach ($rows as &$row) {
                        $row['plays']    = (int)$row['plays'];
                        $row['likes']    = (int)$row['likes'];
                        $row['comments'] = (int)$row['comments'];
                        $row['shares']   = (int)$row['shares'];
                    }
                    success(['list' => $rows, 'total' => $total, 'page' => $page, 'pageSize' => $pageSize]);
                    break;

                default:
                    error('未知的分析类型', 400);
            }
            break;

        default: error('接口不存在', 404);
    }
    exit;
}

// 自包含模式（直接访问 .php 文件）
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }
header('Content-Type: application/json; charset=utf-8');
$config = require __DIR__ . '/../config.php';
$dsn = sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4', $config['db_host'], $config['db_port'], $config['db_name']);
$pdo = new PDO($dsn, $config['db_user'], $config['db_pass'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
function _tbl_s($t) { global $config; return $config['db_prefix'] . $t; }
function _ok_s($d=null,$m='ok'){echo json_encode(['code'=>0,'data'=>$d,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
function _err_s($m,$c=400){http_response_code($c);echo json_encode(['code'=>$c,'data'=>null,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
function _auth_s(){$h=$_SERVER['HTTP_AUTHORIZATION']??'';if(!preg_match('/^Bearer\s+(.+)$/i',$h,$m))_err_s('未提供认证Token',401);$p=explode('.',$m[1]);if(count($p)!==3)_err_s('Token无效',401);$cfg=require __DIR__.'/../config.php';$exp=rtrim(strtr(base64_encode(hash_hmac('sha256',$p[0].'.'.$p[1],$cfg['jwt_secret'],true)),'+/','-_'),'=');$d=json_decode(base64_decode(strtr($p[1],'-_','+/')),true);if(!$d)_err_s('Token无效',401);return $d;}

$uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$segs = array_values(array_filter(explode('/', preg_replace('#^/api/#', '', $uri))));
$action = $segs[1] ?? 'overview';
$today = date('Y-m-d');

switch ($action) {
    case 'overview':
        _auth_s();
        $r = [];
        $r['total_users'] = (int)$pdo->query("SELECT COUNT(*) FROM "._tbl_s('sys_user'))->fetchColumn();
        $r['today_videos'] = (int)$pdo->prepare("SELECT COUNT(*) FROM "._tbl_s('video_task')." WHERE DATE(created_at)=?")->execute([$today])??0;
        $st=$pdo->prepare("SELECT COUNT(*) FROM "._tbl_s('video_task')." WHERE DATE(created_at)=?");$st->execute([$today]);$r['today_videos']=(int)$st->fetchColumn();
        $st=$pdo->prepare("SELECT COUNT(*) FROM "._tbl_s('publish_record')." WHERE DATE(created_at)=? AND status='success'");$st->execute([$today]);$r['today_publish_success']=(int)$st->fetchColumn();
        $st=$pdo->prepare("SELECT COUNT(*) FROM "._tbl_s('publish_record')." WHERE DATE(created_at)=? AND status='failed'");$st->execute([$today]);$r['today_publish_failed']=(int)$st->fetchColumn();
        $tot=$r['today_publish_success']+$r['today_publish_failed'];
        $r['success_rate']=$tot>0?round($r['today_publish_success']/$tot*100,1):0;

        // 管理账号数
        $r['accountCount']=(int)$pdo->query('SELECT COUNT(*) FROM '._tbl_s('platform_account'))->fetchColumn();

        // 最近发布记录
        $st=$pdo->prepare('SELECT pr.platform, pr.account_name AS accountName, pr.video_title AS videoTitle, pr.published_time AS time, pr.status FROM '._tbl_s('publish_record').' pr ORDER BY pr.id DESC LIMIT 10');
        $st->execute();
        $r['recentPublish']=$st->fetchAll();

        // 异常预警
        $st=$pdo->prepare('SELECT nickname, platform FROM '._tbl_s('platform_account')." WHERE status='expired' ORDER BY id DESC LIMIT 10");
        $st->execute();
        $expiredAccounts=$st->fetchAll();
        $alerts=[];
        foreach($expiredAccounts as $acc){
            $pn=match($acc['platform']){'douyin'=>'抖音','kuaishou'=>'快手','xiaohongshu'=>'小红书','weixin'=>'视频号',default=>$acc['platform']};
            $alerts[]=['message'=>"{$pn}账号 {$acc['nickname']} 登录失效",'text'=>'Cookie已过期，请重新扫码登录'];
        }
        $r['alerts']=$alerts;

        // 视频数据统计
        $r['video_data_count']=(int)$pdo->query('SELECT COUNT(*) FROM '._tbl_s('video_data'))->fetchColumn();
        $vSt=$pdo->query('SELECT COALESCE(SUM(plays),0) AS tp, COALESCE(SUM(likes),0) AS tl FROM '._tbl_s('video_data'))->fetch();
        $r['total_plays']=(int)($vSt['tp']??0);
        $r['total_likes']=(int)($vSt['tl']??0);
        $aSt=$pdo->query('SELECT COALESCE(SUM(works_count),0) AS tw, COALESCE(SUM(total_plays),0) AS atp FROM '._tbl_s('platform_account'))->fetch();
        $r['total_works']=(int)($aSt['tw']??0);
        if($r['total_plays']==0&&(int)($aSt['atp']??0)>0)$r['total_plays']=(int)($aSt['atp']??0);
        if($r['video_data_count']==0){
            $actA=(int)$pdo->query('SELECT COUNT(*) FROM '._tbl_s('platform_account')." WHERE status='active' AND cookie IS NOT NULL AND cookie != ''")->fetchColumn();
            if($actA>0)$alerts[]=['message'=>'视频数据为空，请点击「同步平台数据」拉取','text'=>'已登录 '.$actA.' 个账号，但尚未同步视频数据'];
            else $alerts[]=['message'=>'暂无已登录的平台账号','text'=>'请先在「账号管理」中添加并登录平台账号'];
            $r['alerts']=$alerts;
        }

        _ok_s($r);
        break;
    case 'users':
        _auth_s();
        $st=$pdo->query("SELECT u.id,u.username,u.role,(SELECT COUNT(*) FROM "._tbl_s('video_task')." v WHERE v.user_id=u.id AND DATE(v.created_at)='".date('Y-m-d')."') as today_videos FROM "._tbl_s('sys_user')." u ORDER BY u.id DESC");
        _ok_s($st->fetchAll());
        break;
    case 'platforms':
        _auth_s();
        $result=[];
        foreach(['douyin','kuaishou','xiaohongshu','weixin']as$p){
            $st=$pdo->prepare("SELECT COUNT(*) FROM "._tbl_s('platform_account')." WHERE platform=?");$st->execute([$p]);$acc=(int)$st->fetchColumn();
            $st=$pdo->prepare("SELECT COUNT(*) FROM "._tbl_s('publish_record')." WHERE platform=? AND DATE(created_at)=?");$st->execute([$p,$today]);$pub=(int)$st->fetchColumn();
            $st=$pdo->prepare("SELECT COUNT(*) FROM "._tbl_s('publish_record')." WHERE platform=? AND DATE(created_at)=? AND status='success'");$st->execute([$p,$today]);$suc=(int)$st->fetchColumn();
            $result[]=['platform'=>$p,'accounts'=>$acc,'today_publish'=>$pub,'success_rate'=>$pub>0?round($suc/$pub*100,1):0];
        }
        _ok_s($result);
        break;
    case 'analysis':
        _auth_s();
        $type      = $segs[2] ?? ($_GET['type'] ?? 'summary');
        $startDate = $_GET['startDate'] ?? date('Y-m-d');
        $endDate   = $_GET['endDate'] ?? date('Y-m-d');
        $platform  = $_GET['platform'] ?? '';
        $page      = max(1, (int)($_GET['page'] ?? 1));
        $pageSize  = 20;
        $offset    = ($page - 1) * $pageSize;

        $where = 'WHERE 1=1';
        $params = [];
        if ($startDate) { $where .= ' AND DATE(v.publish_time) >= ?'; $params[] = $startDate; }
        if ($endDate)   { $where .= ' AND DATE(v.publish_time) <= ?'; $params[] = $endDate; }
        if ($platform)  { $where .= ' AND v.platform = ?'; $params[] = $platform; }

        switch ($type) {
            case 'summary':
                $st = $pdo->prepare('SELECT COALESCE(SUM(v.plays),0) AS totalPlays, COALESCE(SUM(v.likes),0) AS totalLikes, COALESCE(SUM(v.comments),0) AS totalComments, COALESCE(SUM(v.shares),0) AS totalShares FROM '._tbl_s('video_data')." v $where");
                $st->execute($params);
                $r = $st->fetch();
                $r['totalPlays']=(int)$r['totalPlays']; $r['totalLikes']=(int)$r['totalLikes']; $r['totalComments']=(int)$r['totalComments']; $r['totalShares']=(int)$r['totalShares'];
                _ok_s($r);
                break;
            case 'platform':
                $st = $pdo->prepare('SELECT v.platform, COUNT(*) AS accountCount, COALESCE(SUM(v.plays),0) AS playCount, COALESCE(SUM(v.likes),0) AS likeCount, COALESCE(SUM(v.comments),0) AS commentCount, COALESCE(SUM(v.shares),0) AS shareCount, COUNT(*) AS publishCount FROM '._tbl_s('video_data')." v $where GROUP BY v.platform");
                $st->execute($params);
                $rows = $st->fetchAll();
                foreach($rows as &$row){$row['playCount']=(int)$row['playCount'];$row['likeCount']=(int)$row['likeCount'];$row['commentCount']=(int)$row['commentCount'];$row['shareCount']=(int)$row['shareCount'];$row['publishCount']=(int)$row['publishCount'];}
                _ok_s(['list'=>$rows]);
                break;
            case 'video':
                $countSt=$pdo->prepare('SELECT COUNT(*) FROM '._tbl_s('video_data')." v $where"); $countSt->execute($params); $total=(int)$countSt->fetchColumn();
                $st=$pdo->prepare('SELECT v.* FROM '._tbl_s('video_data')." v $where ORDER BY v.publish_time DESC LIMIT $pageSize OFFSET $offset"); $st->execute($params); $rows=$st->fetchAll();
                foreach($rows as &$row){$row['plays']=(int)$row['plays'];$row['likes']=(int)$row['likes'];$row['comments']=(int)$row['comments'];$row['shares']=(int)$row['shares'];}
                _ok_s(['list'=>$rows,'total'=>$total,'page'=>$page,'pageSize'=>$pageSize]);
                break;
            default: _err_s('未知的分析类型',400);
        }
        break;

    default: _err_s('接口不存在',404);
}
