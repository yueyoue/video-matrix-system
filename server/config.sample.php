<?php
/**
 * 视频矩阵系统 - 配置文件模板
 * 复制此文件为 config.php 并修改配置
 */
return [
    // 数据库配置
    'db_host'    => 'localhost',
    'db_port'    => 3306,
    'db_name'    => 'video_matrix',
    'db_user'    => 'root',
    'db_pass'    => '',
    'db_prefix'  => 'vm_',

    // JWT密钥（安装时自动生成）
    'jwt_secret' => 'CHANGE_ME_TO_RANDOM_STRING',

    // 上传配置
    'upload_path' => __DIR__ . '/uploads/',
    'upload_url'  => '/uploads/',
];
