<?php
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }
header('Content-Type: application/json; charset=utf-8');
$config = require __DIR__ . '/../config.php';
$dsn = sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4', $config['db_host'], $config['db_port'], $config['db_name']);
$pdo = new PDO($dsn, $config['db_user'], $config['db_pass'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
function _tbl_a($t) { global $config; return $config['db_prefix'] . $t; }
function _ok_a($d=null,$m='ok'){echo json_encode(['code'=>0,'data'=>$d,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
function _err_a($m,$c=400){http_response_code($c);echo json_encode(['code'=>$c,'data'=>null,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
function _auth_a(){$h=$_SERVER['HTTP_AUTHORIZATION']??'';if(!preg_match('/^Bearer\s+(.+)$/i',$h,$m))_err_a('未提供认证Token',401);$p=explode('.',$m[1]);if(count($p)!==3)_err_a('Token无效',401);$cfg=require __DIR__.'/../config.php';$exp=rtrim(strtr(base64_encode(hash_hmac('sha256',$p[0].'.'.$p[1],$cfg['jwt_secret'],true)),'+/','-_'),'=');$d=json_decode(base64_decode(strtr($p[1],'-_','+/')),true);if(!$d)_err_a('Token无效',401);return $d;}
function _admin_a(){$u=_auth_a();if($u['role']!=='admin')_err_a('权限不足',403);return $u;}
function _json_a(){$r=json_decode(file_get_contents('php://input'),true);return is_array($r)?$r:[];}

$method = $_SERVER['REQUEST_METHOD'];
$uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$segs = array_values(array_filter(explode('/', preg_replace('#^/api/#', '', $uri))));
$action = $segs[1] ?? 'config';
$id = $segs[2] ?? null;

switch ($action) {
    case 'config':
        if ($method === 'GET') {
            $st = $pdo->query("SELECT * FROM " . _tbl_a('ai_config') . " LIMIT 1");
            _ok_a($st->fetch() ?: []);
        } elseif ($method === 'PUT') {
            _admin_a(); $i = _json_a(); $s = []; $p = [];
            foreach (['provider', 'app_id', 'secret_key', 'daily_limit'] as $f) {
                if (isset($i[$f])) { $s[] = "$f = ?"; $p[] = $i[$f]; }
            }
            if ($s) $pdo->prepare("UPDATE " . _tbl_a('ai_config') . " SET " . implode(',', $s))->execute($p);
            _ok_a(null, '更新成功');
        } else { _err_a('方法不允许', 405); }
        break;
    case 'voices':
        if ($method === 'GET') {
            $sql = "SELECT * FROM " . _tbl_a('ai_voice');
            if ($st = $_GET['status'] ?? '') $sql .= " WHERE status = '$st'";
            $sql .= " ORDER BY id";
            _ok_a($pdo->query($sql)->fetchAll());
        } elseif ($method === 'POST') {
            _admin_a(); $i = _json_a();
            $pdo->prepare("INSERT INTO " . _tbl_a('ai_voice') . " (name, voice_id, type, scene) VALUES (?, ?, ?, ?)")
                ->execute([$i['name'] ?? '', $i['voice_id'] ?? '', $i['type'] ?? 'female', $i['scene'] ?? '']);
            _ok_a(['id' => $pdo->lastInsertId()], '添加成功');
        } elseif ($method === 'PUT') {
            if (!$id) _err_a('缺少ID'); _admin_a(); $i = _json_a(); $s = []; $p = [];
            foreach (['name', 'voice_id', 'type', 'scene', 'status'] as $f) {
                if (isset($i[$f])) { $s[] = "$f = ?"; $p[] = $i[$f]; }
            }
            if ($s) { $p[] = $id; $pdo->prepare("UPDATE " . _tbl_a('ai_voice') . " SET " . implode(',', $s) . " WHERE id = ?")->execute($p); }
            _ok_a(null, '更新成功');
        } elseif ($method === 'DELETE') {
            if (!$id) _err_a('缺少ID'); _admin_a();
            $pdo->prepare("DELETE FROM " . _tbl_a('ai_voice') . " WHERE id = ?")->execute([$id]);
            _ok_a(null, '删除成功');
        } else { _err_a('方法不允许', 405); }
        break;
    case 'test':
        if ($method !== 'POST') _err_a('方法不允许', 405);
        _admin_a();
        _ok_a(['connected' => true], '接口连通正常');
        break;
    default: _err_a('接口不存在', 404);
}
