<?php
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
    default: _err_s('接口不存在',404);
}
