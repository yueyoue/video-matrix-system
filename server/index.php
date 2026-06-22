<?php
/**
 * 视频矩阵系统 - API入口文件
 * 统一路由，分发到对应的 api/*.php
 */

// 错误报告（生产环境可关闭）
error_reporting(E_ALL);
ini_set('display_errors', 0);
ini_set('log_errors', 1);

// 加载响应函数（包含CORS头）
require_once __DIR__ . '/includes/response.php';

// 检查是否已安装
if (!file_exists(__DIR__ . '/config.php') && !preg_match('#^/install#', $_SERVER['REQUEST_URI'])) {
    // 未安装且不在安装页面，跳转到安装向导
    header('Location: /install/');
    exit;
}

// 获取请求路径
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);

// 安装向导路由
if (preg_match('#^/install(/.*)?$#', $path)) {
    require __DIR__ . '/install/index.php';
    exit;
}

// API路由
$path = preg_replace('#^/api/#', '', $path);
$path = trim($path, '/');
$segments = $path ? explode('/', $path) : [];

if (empty($segments[0])) {
    success(['version' => '1.0.0', 'status' => 'running'], '视频矩阵系统API运行正常');
}

$file = __DIR__ . '/api/' . $segments[0] . '.php';

if (file_exists($file)) {
    // 将路由段传递给API文件
    $GLOBALS['route_segments'] = $segments;
    $GLOBALS['route_method']   = $_SERVER['REQUEST_METHOD'];
    require $file;
} else {
    error('接口不存在: /api/' . htmlspecialchars($segments[0]), 404);
}
