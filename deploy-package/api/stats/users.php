<?php
require_once __DIR__ . '/../_helpers.php';
requireAuth();
adminOnly();
[$page, $pageSize, $offset] = getPageParams();
$today = date('Y-m-d');
$stmt = $pdo->query("SELECT u.id, u.username, u.role,
    (SELECT COUNT(*) FROM " . table('video_task') . " v WHERE v.user_id = u.id AND DATE(v.created_at) = '$today') as today_videos,
    (SELECT COUNT(*) FROM " . table('publish_record') . " p WHERE p.user_id = u.id AND DATE(p.created_at) = '$today' AND p.status = 'success') as publish_success,
    (SELECT COUNT(*) FROM " . table('publish_record') . " p WHERE p.user_id = u.id AND DATE(p.created_at) = '$today' AND p.status = 'failed') as publish_failed
    FROM " . table('sys_user') . " u ORDER BY u.id DESC LIMIT $pageSize OFFSET $offset");
$count = $pdo->query("SELECT COUNT(*) FROM " . table('sys_user'));
paginate($stmt->fetchAll(), $count->fetchColumn(), $page, $pageSize);
