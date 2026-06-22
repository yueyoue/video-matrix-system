<?php
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, PUT, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }
header('Content-Type: application/json; charset=utf-8');
$config = require __DIR__ . '/../../config.php';
$pdo = new PDO(sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4', $config['db_host'], $config['db_port'], $config['db_name']), $config['db_user'], $config['db_pass'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
$prefix=$config['db_prefix'];
function _ok_ac($d=null,$m='ok'){echo json_encode(['code'=>0,'data'=>$d,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
function _err_ac($m,$c=400){http_response_code($c);echo json_encode(['code'=>$c,'data'=>null,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
function _adm_ac(){global $config;$h=$_SERVER['HTTP_AUTHORIZATION']??'';if(!preg_match('/^Bearer\s+(.+)$/i',$h,$m))_err_ac('未认证',401);$p=explode('.',$m[1]);if(count($p)!==3)_err_ac('Token无效',401);$exp=rtrim(strtr(base64_encode(hash_hmac('sha256',$p[0].'.'.$p[1],$config['jwt_secret'],true)),'+/','-_'),'=');$d=json_decode(base64_decode(strtr($p[1],'-_','+/')),true);if(!$d||($d['role']??'')!=='admin')_err_ac('权限不足',403);}
$method=$_SERVER['REQUEST_METHOD'];
if($method==='GET'){$st=$pdo->query("SELECT * FROM {$prefix}ai_config LIMIT 1");_ok_ac($st->fetch()?:[]);}
elseif($method==='PUT'){_adm_ac();$i=json_decode(file_get_contents('php://input'),true)?:[];$s=[];$p=[];
foreach(['provider','app_id','secret_key','daily_limit']as$f){if(isset($i[$f])){$s[]="$f=?";$p[]=$i[$f];}}
if($s)$pdo->prepare("UPDATE {$prefix}ai_config SET ".implode(',',$s))->execute($p);_ok_ac(null,'更新成功');}
else{_err_ac('方法不允许',405);}
