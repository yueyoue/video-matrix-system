<?php
/**
 * 统一响应函数
 */

// 设置CORS头
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');

// 处理OPTIONS预检请求
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

/**
 * 成功响应
 * @param mixed $data 数据
 * @param string $message 消息
 */
function success($data = null, $message = 'ok')
{
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode([
        'code'    => 0,
        'data'    => $data,
        'message' => $message
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

/**
 * 错误响应
 * @param string $message 错误消息
 * @param int $code HTTP状态码
 * @param int $bizCode 业务码（默认等于HTTP状态码）
 */
function error($message, $code = 400, $bizCode = null)
{
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode([
        'code'    => $bizCode ?? $code,
        'data'    => null,
        'message' => $message
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

/**
 * 分页响应
 * @param array $list 数据列表
 * @param int $total 总数
 * @param int $page 当前页
 * @param int $pageSize 每页数量
 */
function paginate($list, $total, $page = 1, $pageSize = 20)
{
    success([
        'list'     => $list,
        'total'    => (int)$total,
        'page'     => (int)$page,
        'pageSize' => (int)$pageSize,
        'pages'    => ceil($total / $pageSize)
    ]);
}
