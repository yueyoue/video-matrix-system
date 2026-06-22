<?php
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }
header('Content-Type: application/json; charset=utf-8');
$config = require __DIR__ . '/../../config.php';
$pdo = new PDO(sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4', $config['db_host'], $config['db_port'], $config['db_name']), $config['db_user'], $config['db_pass'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
$prefix=$config['db_prefix'];
function _ok_av($d=null,$m='ok'){echo json_encode(['code'=>0,'data'=>$d,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
function _err_av($m,$c=400){http_response_code($c);echo json_encode(['code'=>$c,'data'=>null,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
function _adm_av(){global $config;$h=$_SERVER['HTTP_AUTHORIZATION']??'';if(!preg_match('/^Bearer\s+(.+)$/i',$h,$m))_err_av('未认证',401);$p=explode('.',$m[1]);if(count($p)!==3)_err_av('Token无效',401);$d=json_decode(base64_decode(strtr($p[1],'-_','+/')),true);if(!$d||($d['role']??'')!=='admin')_err_av('权限不足',403);}
$method=$_SERVER['REQUEST_METHOD'];
$uri=parse_url($_SERVER['REQUEST_URI'],PHP_URL_PATH);
$segs=array_values(array_filter(explode('/',preg_replace('#^/api/#','',$uri))));
$id=$segs[2]??null;
if($method==='GET'){$sql="SELECT * FROM {$prefix}ai_voice";if($s=$_GET['status']??'')$sql.=" WHERE status='$s'";$sql.=" ORDER BY id";_ok_av($pdo->query($sql)->fetchAll());}
elseif($method==='POST'){_adm_av();$i=json_decode(file_get_contents('php://input'),true)?:[];$pdo->prepare("INSERT INTO {$prefix}ai_voice (name,voice_id,type,scene) VALUES (?,?,?,?)")->execute([$i['name']??'',$i['voice_id']??'',$i['type']??'female',$i['scene']??'']);_ok_av(['id'=>$pdo->lastInsertId()],'添加成功');}
elseif($method==='PUT'){if(!$id)_err_av('缺少ID');_adm_av();$i=json_decode(file_get_contents('php://input'),true)?:[];$s=[];$p=[];
foreach(['name','voice_id','type','scene','status']as$f){if(isset($i[$f])){$s[]="$f=?";$p[]=$i[$f];}}
if($s){$p[]=$id;$pdo->prepare("UPDATE {$prefix}ai_voice SET ".implode(',',$s)." WHERE id=?")->execute($p);}_ok_av(null,'更新成功');}
elseif($method==='DELETE'){if(!$id)_err_av('缺少ID');_adm_av();$pdo->prepare("DELETE FROM {$prefix}ai_voice WHERE id=?")->execute([$id]);_ok_av(null,'删除成功');}
else{_err_av('方法不允许',405);}
