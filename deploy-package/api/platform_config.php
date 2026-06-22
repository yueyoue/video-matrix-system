<?php
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, PUT, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }
header('Content-Type: application/json; charset=utf-8');
$config = require __DIR__ . '/../config.php';
$dsn = sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4', $config['db_host'], $config['db_port'], $config['db_name']);
$pdo = new PDO($dsn, $config['db_user'], $config['db_pass'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
function _tbl_pc($t) { global $config; return $config['db_prefix'] . $t; }
function _ok_pc($d=null,$m='ok'){echo json_encode(['code'=>0,'data'=>$d,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
function _err_pc($m,$c=400){http_response_code($c);echo json_encode(['code'=>$c,'data'=>null,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
function _auth_pc(){$h=$_SERVER['HTTP_AUTHORIZATION']??'';if(!preg_match('/^Bearer\s+(.+)$/i',$h,$m))_err_pc('未提供认证Token',401);$p=explode('.',$m[1]);if(count($p)!==3)_err_pc('Token无效',401);$cfg=require __DIR__.'/../config.php';$exp=rtrim(strtr(base64_encode(hash_hmac('sha256',$p[0].'.'.$p[1],$cfg['jwt_secret'],true)),'+/','-_'),'=');$d=json_decode(base64_decode(strtr($p[1],'-_','+/')),true);if(!$d)_err_pc('Token无效',401);return $d;}
function _admin_pc(){$u=_auth_pc();if($u['role']!=='admin')_err_pc('权限不足',403);return $u;}
function _json_pc(){$r=json_decode(file_get_contents('php://input'),true);return is_array($r)?$r:[];}

$method = $_SERVER['REQUEST_METHOD'];
$uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$segs = array_values(array_filter(explode('/', preg_replace('#^/api/#', '', $uri))));
// 支持 _r 查询参数传递子路由（前端 .php 拦截器生成）
if (isset($_GET['_r'])) {
    $rsegs = array_values(array_filter(explode('/', $_GET['_r'])));
    $platform = $rsegs[0] ?? null;
    $sub = $rsegs[1] ?? null;
} else {
    $platform = $segs[1] ?? null;
    $sub = $segs[2] ?? null;
}

if (!$platform) _err_pc('缺少平台参数');

if ($sub === 'reset' && $method === 'POST') {
    _admin_pc();
    $defaults = [
        'douyin' => '{"creatorUrl":"https://creator.douyin.com/","cookieDays":30}',
        'kuaishou' => '{"creatorUrl":"https://cp.kuaishou.com/","cookieDays":15}',
        'xiaohongshu' => '{"creatorUrl":"https://creator.xiaohongshu.com/","cookieDays":7}',
        'weixin' => '{"creatorUrl":"https://channels.weixin.qq.com/","cookieDays":30}',
    ];
    if (isset($defaults[$platform])) {
        $pdo->prepare("UPDATE " . _tbl_pc('platform_config') . " SET config_json = ? WHERE platform = ?")->execute([$defaults[$platform], $platform]);
    }
    _ok_pc(null, '已恢复默认');
    exit;
}

switch ($method) {
    case 'GET':
        $st = $pdo->prepare("SELECT * FROM " . _tbl_pc('platform_config') . " WHERE platform = ?");
        $st->execute([$platform]);
        $row = $st->fetch();
        if (!$row) _err_pc('配置不存在', 404);
        if (is_string($row['config_json'])) $row['config_json'] = json_decode($row['config_json'], true);
        _ok_pc($row);
        break;
    case 'PUT':
        _admin_pc(); $i = _json_pc();
        $json = json_encode($i['config_json'] ?? $i, JSON_UNESCAPED_UNICODE);
        $st = $pdo->prepare("UPDATE " . _tbl_pc('platform_config') . " SET config_json = ? WHERE platform = ?");
        $st->execute([$json, $platform]);
        if ($st->rowCount() === 0) {
            $pdo->prepare("INSERT INTO " . _tbl_pc('platform_config') . " (platform, config_json) VALUES (?, ?)")->execute([$platform, $json]);
        }
        _ok_pc(null, '更新成功');
        break;
    default: _err_pc('方法不允许', 405);
}
