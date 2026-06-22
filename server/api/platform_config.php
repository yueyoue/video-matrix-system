<?php
/**
 * 平台接口配置
 * GET  /api/platform_config      - 获取所有平台配置
 * GET  /api/platform_config/{p}  - 获取指定平台配置
 * POST /api/platform_config      - 保存平台配置
 */

require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/auth.php';

$currentUser = requireAuth();
$segments    = $GLOBALS['route_segments'];
$method      = $GLOBALS['route_method'];
$platform    = $segments[1] ?? '';

switch ($method) {
    case 'GET':
        if ($platform) {
            getOne($platform);
        } else {
            getAll();
        }
        break;
    case 'POST':
        save();
        break;
    default:
        error('请求方法不允许', 405);
}

/**
 * 获取所有平台配置
 */
function getAll()
{
    global $pdo;

    $stmt = $pdo->prepare("SELECT * FROM " . table('platform_config') . " ORDER BY id ASC");
    $stmt->execute();
    $list = $stmt->fetchAll();

    foreach ($list as &$item) {
        $item['config_json'] = json_decode($item['config_json'] ?? '{}', true);
    }

    success($list);
}

/**
 * 获取指定平台配置
 */
function getOne($platform)
{
    global $pdo;

    $stmt = $pdo->prepare("SELECT * FROM " . table('platform_config') . " WHERE platform = ?");
    $stmt->execute([$platform]);
    $config = $stmt->fetch();

    if (!$config) {
        error('平台配置不存在', 404);
    }

    $config['config_json'] = json_decode($config['config_json'] ?? '{}', true);

    success($config);
}

/**
 * 保存平台配置
 */
function save()
{
    global $pdo, $currentUser;

    adminOnly();

    $input    = getJsonInput();
    $platform = $input['platform'] ?? '';
    $configJson = $input['config_json'] ?? [];

    $validPlatforms = ['douyin', 'kuaishou', 'xiaohongshu', 'weixin'];
    if (!in_array($platform, $validPlatforms)) {
        error('平台类型无效');
    }

    $jsonStr = json_encode($configJson, JSON_UNESCAPED_UNICODE);

    $stmt = $pdo->prepare("SELECT id FROM " . table('platform_config') . " WHERE platform = ?");
    $stmt->execute([$platform]);
    $existing = $stmt->fetch();

    if ($existing) {
        $stmt = $pdo->prepare("UPDATE " . table('platform_config') . " SET config_json = ? WHERE platform = ?");
        $stmt->execute([$jsonStr, $platform]);
    } else {
        $stmt = $pdo->prepare("INSERT INTO " . table('platform_config') . " (platform, config_json) VALUES (?, ?)");
        $stmt->execute([$platform, $jsonStr]);
    }

    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '平台配置', '保存配置', "保存{$platform}平台配置");

    success(null, '配置保存成功');
}
