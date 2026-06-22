<?php
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }
header('Content-Type: application/json; charset=utf-8');
$config = require __DIR__ . '/../../config.php';
$pdo = new PDO(sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4', $config['db_host'], $config['db_port'], $config['db_name']), $config['db_user'], $config['db_pass'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
function _ok_lg($d=null,$m='ok'){echo json_encode(['code'=>0,'data'=>$d,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
function _err_lg($m,$c=400){http_response_code($c);echo json_encode(['code'=>$c,'data'=>null,'message'=>$m],JSON_UNESCAPED_UNICODE);exit;}
if ($_SERVER['REQUEST_METHOD'] === 'GET') { _ok_lg(null, 'API正常'); exit; }
if ($_SERVER['REQUEST_METHOD'] !== 'POST') _err_lg('方法不允许', 405);
$i = json_decode(file_get_contents('php://input'), true) ?: [];
$username = trim($i['username'] ?? ''); $password = $i['password'] ?? '';
if (!$username || !$password) _err_lg('用户名和密码不能为空');
$prefix = $config['db_prefix'];
$st = $pdo->prepare("SELECT * FROM {$prefix}sys_user WHERE username = ?");
$st->execute([$username]); $user = $st->fetch();
if (!$user) _err_lg('用户名或密码错误');
if ($user['status'] === 'disabled') _err_lg('账号已被禁用');
if (!password_verify($password, $user['password'])) _err_lg('用户名或密码错误');
$pdo->prepare("UPDATE {$prefix}sys_user SET last_login = NOW() WHERE id = ?")->execute([$user['id']]);
$hdr = rtrim(strtr(base64_encode(json_encode(['typ'=>'JWT','alg'=>'HS256'])), '+/', '-_'), '=');
$pld = rtrim(strtr(base64_encode(json_encode(['user_id'=>$user['id'],'username'=>$user['username'],'role'=>$user['role'],'iat'=>time(),'exp'=>time()+86400])), '+/', '-_'), '=');
$sig = rtrim(strtr(base64_encode(hash_hmac('sha256', "$hdr.$pld", $config['jwt_secret'], true)), '+/', '-_'), '=');
$token = "$hdr.$pld.$sig";
try { $pdo->prepare("INSERT INTO {$prefix}operation_log (user_id,username,level,module,action,detail) VALUES (?,?,?,?,?,?)")->execute([$user['id'],$user['username'],'INFO','用户登录','登录','登录成功']); } catch(Exception $e) {}
_ok_lg(['token'=>$token,'userInfo'=>['id'=>$user['id'],'username'=>$user['username'],'role'=>$user['role'],'daily_quota'=>$user['daily_quota'],'used_quota'=>$user['used_quota']]], '登录成功');
