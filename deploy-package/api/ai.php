<?php
/**
 * AI配音配置接口
 * GET  /api/ai/config     - 获取AI配置
 * POST /api/ai/config     - 保存AI配置
 * GET  /api/ai/voices     - 音色列表
 * POST /api/ai/voices     - 添加音色
 * PUT  /api/ai/voices/{id} - 更新音色
 * DELETE /api/ai/voices/{id} - 删除音色
 */

require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/auth.php';

$currentUser = requireAuth();
$segments    = $GLOBALS['route_segments'];
$method      = $GLOBALS['route_method'];
$action      = $segments[1] ?? 'config';

switch ($action) {
    case 'config':
        handleConfig();
        break;
    case 'voices':
        handleVoices();
        break;
    default:
        error('接口不存在', 404);
}

/**
 * AI配置
 */
function handleConfig()
{
    global $pdo, $currentUser;

    if ($_SERVER['REQUEST_METHOD'] === 'GET') {
        $stmt = $pdo->prepare("SELECT * FROM " . table('ai_config') . " ORDER BY id LIMIT 1");
        $stmt->execute();
        $config = $stmt->fetch();

        if (!$config) {
            success([
                'provider'   => 'aliyun',
                'app_id'     => '',
                'secret_key' => '',
                'daily_limit' => 100,
            ]);
        }

        // 隐藏密钥
        if (!empty($config['secret_key'])) {
            $config['secret_key'] = substr($config['secret_key'], 0, 6) . '******';
        }

        success($config);
    }

    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        adminOnly();

        $input = getJsonInput();
        $provider   = $input['provider'] ?? 'aliyun';
        $appId      = $input['app_id'] ?? '';
        $secretKey  = $input['secret_key'] ?? '';
        $dailyLimit = (int)($input['daily_limit'] ?? 100);

        // 如果密钥是掩码格式，不更新
        if (preg_match('/^\*{6}$/', $secretKey) || empty($secretKey)) {
            // 只更新非密钥字段
            $stmt = $pdo->prepare("SELECT id FROM " . table('ai_config') . " ORDER BY id LIMIT 1");
            $stmt->execute();
            $existing = $stmt->fetch();

            if ($existing) {
                $stmt = $pdo->prepare("UPDATE " . table('ai_config') . " SET provider = ?, app_id = ?, daily_limit = ? WHERE id = ?");
                $stmt->execute([$provider, $appId, $dailyLimit, $existing['id']]);
            } else {
                $stmt = $pdo->prepare("INSERT INTO " . table('ai_config') . " (provider, app_id, daily_limit) VALUES (?, ?, ?)");
                $stmt->execute([$provider, $appId, $dailyLimit]);
            }
        } else {
            $stmt = $pdo->prepare("SELECT id FROM " . table('ai_config') . " ORDER BY id LIMIT 1");
            $stmt->execute();
            $existing = $stmt->fetch();

            if ($existing) {
                $stmt = $pdo->prepare("UPDATE " . table('ai_config') . " SET provider = ?, app_id = ?, secret_key = ?, daily_limit = ? WHERE id = ?");
                $stmt->execute([$provider, $appId, $secretKey, $dailyLimit, $existing['id']]);
            } else {
                $stmt = $pdo->prepare("INSERT INTO " . table('ai_config') . " (provider, app_id, secret_key, daily_limit) VALUES (?, ?, ?, ?)");
                $stmt->execute([$provider, $appId, $secretKey, $dailyLimit]);
            }
        }

        logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', 'AI配置', '保存配置', 'AI配音配置已更新');

        success(null, '配置保存成功');
    }

    error('请求方法不允许', 405);
}

/**
 * 音色管理
 */
function handleVoices()
{
    global $pdo, $currentUser;

    $method = $GLOBALS['route_method'];
    $segments = $GLOBALS['route_segments'];
    $id = isset($segments[2]) ? (int)$segments[2] : 0;

    switch ($method) {
        case 'GET':
            $status = param('status', '');
            $where = "WHERE 1=1";
            $params = [];

            if ($status) {
                $where .= " AND status = ?";
                $params[] = $status;
            }

            $stmt = $pdo->prepare("SELECT * FROM " . table('ai_voice') . " $where ORDER BY id ASC");
            $stmt->execute($params);
            success($stmt->fetchAll());

        case 'POST':
            adminOnly();
            $input = getJsonInput();
            $name   = trim($input['name'] ?? '');
            $voiceId = trim($input['voice_id'] ?? '');
            $type   = $input['type'] ?? 'female';
            $scene  = $input['scene'] ?? '';

            if (empty($name) || empty($voiceId)) {
                error('音色名称和ID不能为空');
            }

            $stmt = $pdo->prepare("INSERT INTO " . table('ai_voice') . " (name, voice_id, type, scene) VALUES (?, ?, ?, ?)");
            $stmt->execute([$name, $voiceId, $type, $scene]);

            logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', 'AI配置', '添加音色', "添加音色: {$name}");

            success(['id' => (int)$pdo->lastInsertId()], '音色添加成功');

        case 'PUT':
            if (!$id) error('缺少音色ID');
            adminOnly();

            $input = getJsonInput();
            $fields = [];
            $params = [];

            if (isset($input['name']))      { $fields[] = "name = ?";      $params[] = trim($input['name']); }
            if (isset($input['voice_id']))   { $fields[] = "voice_id = ?";  $params[] = trim($input['voice_id']); }
            if (isset($input['type']))       { $fields[] = "type = ?";      $params[] = $input['type']; }
            if (isset($input['scene']))      { $fields[] = "scene = ?";     $params[] = $input['scene']; }
            if (isset($input['status']))     { $fields[] = "status = ?";    $params[] = $input['status']; }

            if (empty($fields)) error('没有需要更新的字段');

            $params[] = $id;
            $stmt = $pdo->prepare("UPDATE " . table('ai_voice') . " SET " . implode(', ', $fields) . " WHERE id = ?");
            $stmt->execute($params);

            success(null, '音色更新成功');

        case 'DELETE':
            if (!$id) error('缺少音色ID');
            adminOnly();

            $pdo->prepare("DELETE FROM " . table('ai_voice') . " WHERE id = ?")->execute([$id]);
            success(null, '音色删除成功');

        default:
            error('请求方法不允许', 405);
    }
}
