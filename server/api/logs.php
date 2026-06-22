<?php
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }
header('Content-Type: application/json; charset=utf-8');
$config = require __DIR__ . '/../config.php';
$dsn = sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4', $config['db_host'], $config['db_port'], $config['db_name']);
$pdo = new PDO($dsn, $config['db_user'], $config['db_pass'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
function _tbl_l($t) { global $config; return $config['db_prefix'] . $t; }
function _ok_l($d=null,$m='ok'){echo json_encode(['code'=>0,'data'=>$d,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
function _err_l($m,$c=400){http_response_code($c);echo json_encode(['code'=>$c,'data'=>null,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
function _auth_l(){$h=$_SERVER['HTTP_AUTHORIZATION']??'';if(!preg_match('/^Bearer\s+(.+)$/i',$h,$m))_err_l('未提供认证Token',401);$p=explode('.',$m[1]);if(count($p)!==3)_err_l('Token无效',401);$cfg=require __DIR__.'/../config.php';$exp=rtrim(strtr(base64_encode(hash_hmac('sha256',$p[0].'.'.$p[1],$cfg['jwt_secret'],true)),'+/','-_'),'=');$d=json_decode(base64_decode(strtr($p[1],'-_','+/')),true);if(!$d)_err_l('Token无效',401);return $d;}

_auth_l();

// 导出
if (strpos($_SERVER['REQUEST_URI'], '/export') !== false) {
    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename=logs_' . date('Ymd') . '.csv');
    echo "\xEF\xBB\xBF";
    echo "ID,用户,级别,模块,操作,详情,时间\n";
    $st = $pdo->query("SELECT * FROM " . _tbl_l('operation_log') . " ORDER BY id DESC LIMIT 1000");
    while ($r = $st->fetch()) {
        echo implode(',', [$r['id'],$r['username'],$r['level'],$r['module'],$r['action'],'"'.str_replace('"','""',$r['detail']).'"',$r['created_at']]) . "\n";
    }
    exit;
}

$page = max(1, (int)($_GET['page'] ?? 1));
$ps = min(100, max(1, (int)($_GET['pageSize'] ?? 20)));
$w = "1=1"; $p = [];
if ($lv = $_GET['level'] ?? '') { $w .= " AND level = ?"; $p[] = $lv; }
if ($kw = $_GET['keyword'] ?? '') { $w .= " AND (action LIKE ? OR detail LIKE ?)"; $p[] = "%$kw%"; $p[] = "%$kw%"; }
$st = $pdo->prepare("SELECT COUNT(*) FROM " . _tbl_l('operation_log') . " WHERE $w");
$st->execute($p); $tot = $st->fetchColumn();
$st = $pdo->prepare("SELECT * FROM " . _tbl_l('operation_log') . " WHERE $w ORDER BY id DESC LIMIT $ps OFFSET " . ($page - 1) * $ps);
$st->execute($p);
_ok_l(['list' => $st->fetchAll(), 'total' => (int)$tot, 'page' => $page, 'pageSize' => $ps, 'pages' => ceil($tot / $ps)]);
