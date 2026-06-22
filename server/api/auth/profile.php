<?php
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }
header('Content-Type: application/json; charset=utf-8');
$config = require __DIR__ . '/../../config.php';
$pdo = new PDO(sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4', $config['db_host'], $config['db_port'], $config['db_name']), $config['db_user'], $config['db_pass'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
function _ok_pf($d=null,$m='ok'){echo json_encode(['code'=>0,'data'=>$d,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
function _err_pf($m,$c=400){http_response_code($c);echo json_encode(['code'=>$c,'data'=>null,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
$h=$_SERVER['HTTP_AUTHORIZATION']??'';if(!preg_match('/^Bearer\s+(.+)$/i',$h,$m))_err_pf('未提供认证Token',401);
$p=explode('.',$m[1]);if(count($p)!==3)_err_pf('Token无效',401);
$exp=rtrim(strtr(base64_encode(hash_hmac('sha256',$p[0].'.'.$p[1],$config['jwt_secret'],true)),'+/','-_'),'=');
$d=json_decode(base64_decode(strtr($p[1],'-_','+/')),true);if(!$d)_err_pf('Token无效',401);
$prefix=$config['db_prefix'];
$st=$pdo->prepare("SELECT id,username,role,daily_quota,used_quota,status,last_login,created_at FROM {$prefix}sys_user WHERE id=?");
$st->execute([$d['user_id']]);$u=$st->fetch();
if(!$u)_err_pf('用户不存在',404);_ok_pf($u);
