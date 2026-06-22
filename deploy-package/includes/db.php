<?php
/**
 * 数据库连接（PDO）
 */

// 检查配置文件
if (!file_exists(__DIR__ . '/../config.php')) {
    header('Location: /install/');
    exit;
}

$config = require __DIR__ . '/../config.php';

try {
    $dsn = sprintf(
        'mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4',
        $config['db_host'],
        $config['db_port'],
        $config['db_name']
    );

    $pdo = new PDO($dsn, $config['db_user'], $config['db_pass'], [
        PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES   => false,
    ]);
} catch (PDOException $e) {
    error('数据库连接失败: ' . $e->getMessage(), 500);
}

/**
 * 获取带表前缀的表名
 * @param string $table 表名（不含前缀）
 * @return string
 */
function table($table)
{
    global $config;
    return $config['db_prefix'] . $table;
}

/**
 * 记录操作日志
 * @param int $user_id 用户ID
 * @param string $username 用户名
 * @param string $level 日志级别
 * @param string $module 模块
 * @param string $action 操作
 * @param string $detail 详情
 */
function logOperation($user_id, $username, $level, $module, $action, $detail = '')
{
    global $pdo;
    try {
        $stmt = $pdo->prepare("INSERT INTO " . table('operation_log') . " (user_id, username, level, module, action, detail) VALUES (?, ?, ?, ?, ?, ?)");
        $stmt->execute([$user_id, $username, $level, $module, $action, $detail]);
    } catch (Exception $e) {
        // 日志记录失败不影响主流程
        error_log('日志记录失败: ' . $e->getMessage());
    }
}

/**
 * 获取请求体JSON
 * @return array
 */
function getJsonInput()
{
    $input = file_get_contents('php://input');
    $data = json_decode($input, true);
    return is_array($data) ? $data : [];
}

/**
 * 获取查询参数
 * @param string $key 参数名
 * @param mixed $default 默认值
 * @return mixed
 */
function param($key, $default = null)
{
    return isset($_GET[$key]) ? $_GET[$key] : $default;
}

/**
 * 获取分页参数
 * @return array [$page, $pageSize, $offset]
 */
function getPageParams()
{
    $page     = max(1, (int)param('page', 1));
    $pageSize = min(100, max(1, (int)param('pageSize', 20)));
    $offset   = ($page - 1) * $pageSize;
    return [$page, $pageSize, $offset];
}
