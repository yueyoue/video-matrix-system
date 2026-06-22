<?php
require_once __DIR__ . '/../_helpers.php';
$method = $_SERVER['REQUEST_METHOD'];
$segments = getPathSegments();
$platform = $segments[1] ?? null;
$sub = $segments[2] ?? null;

if (!$platform) error('缺少平台参数');

if ($sub === 'reset' && $method === 'POST') {
    $defaults = [
        'douyin' => '{"creatorUrl":"https://creator.douyin.com/","loginCheck":"https://creator.douyin.com/api/login/check","videoList":"https://creator.douyin.com/api/videolist","publish":"https://creator.douyin.com/api/publish","publishBtn":".publish-btn","cookieDays":30}',
        'kuaishou' => '{"creatorUrl":"https://cp.kuaishou.com/","loginCheck":"https://cp.kuaishou.com/api/login/check","videoList":"https://cp.kuaishou.com/api/videolist","publish":"https://cp.kuaishou.com/api/publish","publishBtn":".upload-btn","cookieDays":15}',
        'xiaohongshu' => '{"creatorUrl":"https://creator.xiaohongshu.com/","loginCheck":"https://creator.xiaohongshu.com/api/login/check","videoList":"https://creator.xiaohongshu.com/api/videolist","publish":"https://creator.xiaohongshu.com/api/publish","publishBtn":".submit-btn","cookieDays":7}',
        'weixin' => '{"creatorUrl":"https://channels.weixin.qq.com/","loginCheck":"https://channels.weixin.qq.com/api/login/check","videoList":"https://channels.weixin.qq.com/api/videolist","publish":"https://channels.weixin.qq.com/api/publish","publishBtn":".post-btn","cookieDays":30}',
    ];
    if (isset($defaults[$platform])) {
        $pdo->prepare("UPDATE " . table('platform_config') . " SET config_json = ? WHERE platform = ?")->execute([$defaults[$platform], $platform]);
    }
    success(null, '已恢复默认');
    exit;
}

switch ($method) {
    case 'GET':
        $stmt = $pdo->prepare("SELECT * FROM " . table('platform_config') . " WHERE platform = ?");
        $stmt->execute([$platform]);
        $row = $stmt->fetch();
        if (!$row) error('配置不存在', 404);
        if (is_string($row['config_json'])) $row['config_json'] = json_decode($row['config_json'], true);
        success($row);
        break;
    case 'PUT':
        adminOnly();
        $input = getJsonInput();
        $json = json_encode($input['config_json'] ?? $input, JSON_UNESCAPED_UNICODE);
        $stmt = $pdo->prepare("UPDATE " . table('platform_config') . " SET config_json = ? WHERE platform = ?");
        $stmt->execute([$json, $platform]);
        if ($stmt->rowCount() === 0) {
            $pdo->prepare("INSERT INTO " . table('platform_config') . " (platform, config_json) VALUES (?, ?)")->execute([$platform, $json]);
        }
        success(null, '更新成功');
        break;
    default: error('方法不允许', 405);
}
