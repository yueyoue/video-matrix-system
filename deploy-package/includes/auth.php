<?php
/**
 * JWT认证中间件（纯原生PHP实现，不依赖第三方库）
 */

/**
 * 生成JWT Token
 * @param array $payload 负载数据
 * @param int $expire 过期时间（秒），默认24小时
 * @return string
 */
function jwtEncode($payload, $expire = 86400)
{
    $config = require __DIR__ . '/../config.php';
    $secret = $config['jwt_secret'];

    $header = base64UrlEncode(json_encode(['typ' => 'JWT', 'alg' => 'HS256']));

    $payload['iat'] = time();
    $payload['exp'] = time() + $expire;
    $payloadEncoded = base64UrlEncode(json_encode($payload));

    $signature = base64UrlEncode(
        hash_hmac('sha256', "$header.$payloadEncoded", $secret, true)
    );

    return "$header.$payloadEncoded.$signature";
}

/**
 * 解析JWT Token
 * @param string $token JWT Token
 * @return array|null 解析后的payload，无效返回null
 */
function jwtDecode($token)
{
    $config = require __DIR__ . '/../config.php';
    $secret = $config['jwt_secret'];

    $parts = explode('.', $token);
    if (count($parts) !== 3) {
        return null;
    }

    [$header, $payload, $signature] = $parts;

    // 验证签名
    $expectedSig = base64UrlEncode(
        hash_hmac('sha256', "$header.$payload", $secret, true)
    );

    if (!hash_equals($expectedSig, $signature)) {
        return null;
    }

    $data = json_decode(base64UrlDecode($payload), true);
    if (!$data) {
        return null;
    }

    // 检查过期
    if (isset($data['exp']) && $data['exp'] < time()) {
        return null;
    }

    return $data;
}

/**
 * Base64 URL安全编码
 */
function base64UrlEncode($data)
{
    return rtrim(strtr(base64_encode($data), '+/', '-_'), '=');
}

/**
 * Base64 URL安全解码
 */
function base64UrlDecode($data)
{
    return base64_decode(strtr($data, '-_', '+/'));
}

/**
 * 从请求中获取当前用户信息
 * @return array 用户信息 [user_id, username, role]
 */
function getCurrentUser()
{
    static $user = null;
    if ($user !== null) {
        return $user;
    }

    $authHeader = $_SERVER['HTTP_AUTHORIZATION'] ?? '';

    if (empty($authHeader) || !preg_match('/^Bearer\s+(.+)$/i', $authHeader, $m)) {
        error('未提供认证Token', 401);
    }

    $token = $m[1];
    $payload = jwtDecode($token);

    if (!$payload) {
        error('Token无效或已过期', 401);
    }

    $user = [
        'user_id'  => $payload['user_id'],
        'username' => $payload['username'],
        'role'     => $payload['role'],
    ];

    return $user;
}

/**
 * 要求管理员权限
 */
function adminOnly()
{
    $user = getCurrentUser();
    if ($user['role'] !== 'admin') {
        error('权限不足，需要管理员权限', 403);
    }
}

/**
 * 要求登录（任意角色）
 */
function requireAuth()
{
    return getCurrentUser();
}
