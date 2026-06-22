<?php
require_once __DIR__ . '/../_helpers.php';
if ($_SERVER['REQUEST_METHOD'] !== 'POST') error('方法不允许', 405);
adminOnly();
// 测试 AI 接口连通性（简单返回成功，实际可对接第三方API测试）
success(['connected' => true], '接口连通正常');
