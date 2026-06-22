<?php
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }
header('Content-Type: application/json; charset=utf-8');
$config = require __DIR__ . '/../config.php';
$dsn = sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4', $config['db_host'], $config['db_port'], $config['db_name']);
$pdo = new PDO($dsn, $config['db_user'], $config['db_pass'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
function _tbl_v($t) { global $config; return $config['db_prefix'] . $t; }
function _ok_v($d=null,$m='ok'){echo json_encode(['code'=>0,'data'=>$d,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
function _err_v($m,$c=400){http_response_code($c);echo json_encode(['code'=>$c,'data'=>null,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
function _auth_v(){$h=$_SERVER['HTTP_AUTHORIZATION']??'';if(!preg_match('/^Bearer\s+(.+)$/i',$h,$m))_err_v('未提供认证Token',401);$p=explode('.',$m[1]);if(count($p)!==3)_err_v('Token无效',401);$cfg=require __DIR__.'/../config.php';$exp=rtrim(strtr(base64_encode(hash_hmac('sha256',$p[0].'.'.$p[1],$cfg['jwt_secret'],true)),'+/','-_'),'=');$d=json_decode(base64_decode(strtr($p[1],'-_','+/')),true);if(!$d)_err_v('Token无效',401);return $d;}
function _admin_v(){$u=_auth_v();if($u['role']!=='admin')_err_v('权限不足',403);return $u;}
function _json_v(){$r=json_decode(file_get_contents('php://input'),true);return is_array($r)?$r:[];}

$method = $_SERVER['REQUEST_METHOD'];
$uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$segs = array_values(array_filter(explode('/', preg_replace('#^/api/#', '', $uri))));
$id = $segs[1] ?? null;

switch ($method) {
    case 'GET':
        _auth_v();
        $st = $pdo->query("SELECT * FROM " . _tbl_v('app_version') . " ORDER BY id DESC");
        _ok_v($st->fetchAll());
        break;
    case 'POST':
        _admin_v(); $i = _json_v();
        $v = $i['version'] ?? ''; if (!$v) _err_v('版本号不能为空');
        $pdo->prepare("INSERT INTO " . _tbl_v('app_version') . " (version, changelog, download_url) VALUES (?, ?, ?)")
            ->execute([$v, $i['changelog'] ?? '', $i['download_url'] ?? '']);
        _ok_v(['id' => $pdo->lastInsertId()], '发布成功');
        break;
    case 'PUT':
        if (!$id) _err_v('缺少ID'); _admin_v(); $i = _json_v();
        $s = []; $p = [];
        foreach (['version', 'changelog', 'download_url', 'status'] as $f) {
            if (isset($i[$f])) { $s[] = "$f = ?"; $p[] = $i[$f]; }
        }
        if ($s) { $p[] = $id; $pdo->prepare("UPDATE " . _tbl_v('app_version') . " SET " . implode(',', $s) . " WHERE id = ?")->execute($p); }
        _ok_v(null, '更新成功');
        break;
    case 'DELETE':
        if (!$id) _err_v('缺少ID'); _admin_v();
        $pdo->prepare("DELETE FROM " . _tbl_v('app_version') . " WHERE id = ?")->execute([$id]);
        _ok_v(null, '删除成功');
        break;
    default: _err_v('方法不允许', 405);
}
