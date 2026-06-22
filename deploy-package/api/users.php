<?php
// CORS & 响应头
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }
header('Content-Type: application/json; charset=utf-8');

// 配置 & 数据库
$config = require __DIR__ . '/../config.php';
$dsn = sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4', $config['db_host'], $config['db_port'], $config['db_name']);
$pdo = new PDO($dsn, $config['db_user'], $config['db_pass'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC, PDO::ATTR_EMULATE_PREPARES => false]);
function _tbl($t) { global $config; return $config['db_prefix'] . $t; }
function _ok($d=null,$m='ok'){echo json_encode(['code'=>0,'data'=>$d,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
function _err($m,$c=400){http_response_code($c);echo json_encode(['code'=>$c,'data'=>null,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
function _json(){$r=json_decode(file_get_contents('php://input'),true);return is_array($r)?$r:[];}
function _jwt_dec($token){
    global $config;$p=explode('.',$token);if(count($p)!==3)return null;
    $exp=rtrim(strtr(base64_encode(hash_hmac('sha256',$p[0].".".$p[1],$config['jwt_secret'],true)),'+/','-_'),'=');
    if(!hash_equals($exp,$p[2]))return null;
    $d=json_decode(base64_decode(strtr($p[1],'-_','+/')),true);
    if(!$d||isset($d['exp'])&&$d['exp']<time())return null;return $d;
}
function _auth(){
    $h=$_SERVER['HTTP_AUTHORIZATION']??'';
    if(!preg_match('/^Bearer\s+(.+)$/i',$h,$m))_err('未提供认证Token',401);
    $d=_jwt_dec($m[1]);if(!$d)_err('Token无效或已过期',401);
    return ['user_id'=>$d['user_id'],'username'=>$d['username'],'role'=>$d['role']];
}
function _admin(){$u=_auth();if($u['role']!=='admin')_err('权限不足',403);return $u;}
function _log($u,$lv,$mod,$act,$det=''){global $pdo;try{$pdo->prepare("INSERT INTO "._tbl('operation_log')." (user_id,username,level,module,action,detail) VALUES (?,?,?,?,?,?)")->execute([$u['user_id'],$u['username'],$lv,$mod,$act,$det]);}catch(Exception $e){}}

$method = $_SERVER['REQUEST_METHOD'];
$uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$segs = array_values(array_filter(explode('/', preg_replace('#^/api/#', '', $uri))));
if (isset($_GET['_r'])) { $rsegs = array_values(array_filter(explode('/', $_GET['_r']))); $id = $rsegs[0] ?? null; }
else { $id = $segs[1] ?? null; }

switch ($method) {
    case 'GET':
        _admin();
        $page=max(1,(int)($_GET['page']??1));$ps=min(100,max(1,(int)($_GET['pageSize']??20)));
        $w="1=1";$p=[];
        if($k=$_GET['keyword']??''){$w.=" AND username LIKE ?";$p[]="%$k%";}
        if($r=$_GET['role']??''){$w.=" AND role = ?";$p[]=$r;}
        if($s=$_GET['status']??''){$w.=" AND status = ?";$p[]=$s;}
        $st=$pdo->prepare("SELECT COUNT(*) FROM "._tbl('sys_user')." WHERE $w");$st->execute($p);$tot=$st->fetchColumn();
        $st=$pdo->prepare("SELECT id,username,role,daily_quota,used_quota,status,last_login,created_at FROM "._tbl('sys_user')." WHERE $w ORDER BY id DESC LIMIT $ps OFFSET ".($page-1)*$ps);
        $st->execute($p);_ok(['list'=>$st->fetchAll(),'total'=>(int)$tot,'page'=>$page,'pageSize'=>$ps,'pages'=>ceil($tot/$ps)]);
        break;
    case 'POST':
        _admin();$i=_json();$un=trim($i['username']??'');$pw=$i['password']??'';
        if(!$un||!$pw)_err('用户名和密码不能为空');if(strlen($pw)<6)_err('密码长度不能少于6位');
        try{$pdo->prepare("INSERT INTO "._tbl('sys_user')." (username,password,role,daily_quota) VALUES (?,?,?,?)")->execute([$un,password_hash($pw,PASSWORD_DEFAULT),$i['role']??'operator',(int)($i['daily_quota']??50)]);}
        catch(PDOException $e){if($e->getCode()==23000)_err('用户名已存在');throw $e;}
        $u=_admin();_log($u,'INFO','用户管理','添加用户',"添加用户: $un");
        _ok(['id'=>$pdo->lastInsertId()],'添加成功');
        break;
    case 'PUT':
        if(!$id)_err('缺少用户ID');_admin();$i=_json();$s=[];$p=[];
        foreach(['username','role','status']as$f){if(isset($i[$f])){$s[]="$f = ?";$p[]=$i[$f];}}
        if(isset($i['daily_quota'])){$s[]="daily_quota = ?";$p[]=(int)$i['daily_quota'];}
        if(isset($i['password'])&&$i['password']){$s[]="password = ?";$p[]=password_hash($i['password'],PASSWORD_DEFAULT);}
        if($s){$p[]=$id;$pdo->prepare("UPDATE "._tbl('sys_user')." SET ".implode(',',$s)." WHERE id = ?")->execute($p);}
        $u=_admin();_log($u,'INFO','用户管理','更新用户',"更新用户ID: $id");_ok(null,'更新成功');
        break;
    case 'DELETE':
        if(!$id)_err('缺少用户ID');_admin();
        $pdo->prepare("DELETE FROM "._tbl('sys_user')." WHERE id = ?")->execute([$id]);
        $u=_admin();_log($u,'INFO','用户管理','删除用户',"删除用户ID: $id");_ok(null,'删除成功');
        break;
    default: _err('方法不允许',405);
}
