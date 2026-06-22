<?php
/**
 * 短视频矩阵系统 - 统一入口
 * 自动判断：未安装→安装向导，已安装→前端页面或API
 */

$uri = $_SERVER['REQUEST_URI'];
$path = parse_url($uri, PHP_URL_PATH);

// 未安装 → 跳转安装向导
if (!file_exists(__DIR__ . '/config.php') && strpos($path, '/install') !== 0) {
    header('Location: /install/');
    exit;
}

// API 请求 → 路由到 api/*.php
if (strpos($path, '/api/') === 0) {
    require __DIR__ . '/includes/response.php';
    require __DIR__ . '/includes/db.php';
    require __DIR__ . '/includes/auth.php';

    $apiPath = preg_replace('#^/api/#', '', $path);
    $segments = explode('/', trim($apiPath, '/'));
    // 设置全局路由变量供 API 文件使用
    $GLOBALS['route_segments'] = $segments;
    $GLOBALS['route_method']   = $_SERVER['REQUEST_METHOD'];
    $file = __DIR__ . '/api/' . ($segments[0] ?? '') . '.php';

    if (file_exists($file)) {
        require $file;
    } else {
        error('接口不存在', 404);
    }
    exit;
}

// 安装请求
if (strpos($path, '/install') === 0) {
    require __DIR__ . '/install/index.php';
    exit;
}

// 上传文件直接访问
if (strpos($path, '/uploads/') === 0) {
    $file = __DIR__ . $path;
    if (file_exists($file) && is_file($file)) {
        $mime = mime_content_type($file);
        header("Content-Type: $mime");
        readfile($file);
        exit;
    }
}

// 其他请求 → 返回 Vue 前端
$htmlFile = __DIR__ . '/index.html';
if (file_exists($htmlFile)) {
    // 处理 Vue History 模式路由
    if (!pathinfo($path, PATHINFO_EXTENSION) || pathinfo($path, PATHINFO_EXTENSION) === 'html') {
        readfile($htmlFile);
        exit;
    }
    // 静态资源直接返回
    $staticFile = __DIR__ . $path;
    if (file_exists($staticFile)) {
        $mime = mime_content_type($staticFile);
        header("Content-Type: $mime");
        readfile($staticFile);
        exit;
    }
    readfile($htmlFile);
    exit;
}

// 啥都没有 → 提示安装
echo '<h1>请先上传前端文件</h1><p>将 web-admin.zip 解压到当前目录</p>';
