<?php
/**
 * 视频任务接口
 * GET    /api/videos           - 任务列表
 * POST   /api/videos           - 创建任务
 * GET    /api/videos/{id}      - 任务详情
 * DELETE /api/videos/{id}      - 删除任务
 * POST   /api/videos/upload    - 上传视频
 */

require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/auth.php';

$currentUser = requireAuth();
$segments    = $GLOBALS['route_segments'];
$method      = $GLOBALS['route_method'];
$action      = $segments[1] ?? '';
$id          = is_numeric($action) ? (int)$action : 0;

// 子路由
if ($action === 'upload') {
    handleUpload();
    exit;
}

if ($id > 0) {
    switch ($method) {
        case 'GET':
            getDetail($id);
            break;
        case 'DELETE':
            remove($id);
            break;
        default:
            error('请求方法不允许', 405);
    }
    exit;
}

switch ($method) {
    case 'GET':
        getList();
        break;
    case 'POST':
        create();
        break;
    default:
        error('请求方法不允许', 405);
}

/**
 * 任务列表
 */
function getList()
{
    global $pdo, $currentUser;

    [$page, $pageSize, $offset] = getPageParams();
    $status   = param('status', '');
    $type     = param('type', '');
    $keyword  = param('keyword', '');
    $userId   = param('user_id', '');

    $where  = "WHERE 1=1";
    $params = [];

    if ($currentUser['role'] !== 'admin') {
        $where .= " AND v.user_id = ?";
        $params[] = $currentUser['user_id'];
    } elseif ($userId) {
        $where .= " AND v.user_id = ?";
        $params[] = $userId;
    }

    if ($status) {
        $where .= " AND v.status = ?";
        $params[] = $status;
    }

    if ($type) {
        $where .= " AND v.type = ?";
        $params[] = $type;
    }

    if ($keyword) {
        $where .= " AND v.file_name LIKE ?";
        $params[] = "%{$keyword}%";
    }

    $stmt = $pdo->prepare("SELECT COUNT(*) FROM " . table('video_task') . " v $where");
    $stmt->execute($params);
    $total = $stmt->fetchColumn();

    $stmt = $pdo->prepare("
        SELECT v.*, u.username
        FROM " . table('video_task') . " v
        LEFT JOIN " . table('sys_user') . " u ON v.user_id = u.id
        $where ORDER BY v.id DESC LIMIT $pageSize OFFSET $offset
    ");
    $stmt->execute($params);
    $list = $stmt->fetchAll();

    // 解码JSON字段
    foreach ($list as &$item) {
        $item['source_ids'] = json_decode($item['source_ids'] ?? '[]', true);
        $item['config']     = json_decode($item['config'] ?? '{}', true);
    }

    paginate($list, $total, $page, $pageSize);
}

/**
 * 任务详情
 */
function getDetail($id)
{
    global $pdo, $currentUser;

    $stmt = $pdo->prepare("
        SELECT v.*, u.username
        FROM " . table('video_task') . " v
        LEFT JOIN " . table('sys_user') . " u ON v.user_id = u.id
        WHERE v.id = ?
    ");
    $stmt->execute([$id]);
    $task = $stmt->fetch();

    if (!$task) {
        error('任务不存在', 404);
    }

    if ($currentUser['role'] !== 'admin' && $task['user_id'] != $currentUser['user_id']) {
        error('无权查看此任务', 403);
    }

    $task['source_ids'] = json_decode($task['source_ids'] ?? '[]', true);
    $task['config']     = json_decode($task['config'] ?? '{}', true);

    success($task);
}

/**
 * 创建任务
 */
function create()
{
    global $pdo, $currentUser;

    $input     = getJsonInput();
    $fileName  = trim($input['file_name'] ?? '');
    $filePath  = $input['file_path'] ?? '';
    $fileSize  = (int)($input['file_size'] ?? 0);
    $duration  = (int)($input['duration'] ?? 0);
    $type      = $input['type'] ?? '';
    $sourceIds = $input['source_ids'] ?? [];
    $config    = $input['config'] ?? [];

    if (empty($fileName)) {
        error('文件名不能为空');
    }

    if (!in_array($type, ['cut', 'mix'])) {
        error('任务类型无效，支持: cut, mix');
    }

    $stmt = $pdo->prepare("INSERT INTO " . table('video_task') . " (user_id, file_name, file_path, file_size, duration, type, source_ids, config) VALUES (?, ?, ?, ?, ?, ?, ?, ?)");
    $stmt->execute([
        $currentUser['user_id'],
        $fileName,
        $filePath,
        $fileSize,
        $duration,
        $type,
        json_encode($sourceIds),
        json_encode($config)
    ]);

    $taskId = $pdo->lastInsertId();
    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '视频处理', '创建任务', "创建{$type}任务: {$fileName}");

    success(['id' => (int)$taskId], '任务创建成功');
}

/**
 * 删除任务
 */
function remove($id)
{
    global $pdo, $currentUser;

    $stmt = $pdo->prepare("SELECT * FROM " . table('video_task') . " WHERE id = ?");
    $stmt->execute([$id]);
    $task = $stmt->fetch();

    if (!$task) {
        error('任务不存在', 404);
    }

    if ($currentUser['role'] !== 'admin' && $task['user_id'] != $currentUser['user_id']) {
        error('无权删除此任务', 403);
    }

    if ($task['status'] === 'processing') {
        error('任务处理中，无法删除');
    }

    // 删除文件
    if ($task['file_path'] && file_exists($task['file_path'])) {
        @unlink($task['file_path']);
    }

    $pdo->prepare("DELETE FROM " . table('video_task') . " WHERE id = ?")->execute([$id]);

    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '视频处理', '删除任务', "删除任务: {$task['file_name']}");

    success(null, '任务删除成功');
}

/**
 * 上传视频
 */
function handleUpload()
{
    global $pdo, $currentUser;

    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        error('请求方法不允许', 405);
    }

    $config = require __DIR__ . '/../config.php';
    $uploadDir = $config['upload_path'];

    // 确保上传目录存在
    if (!is_dir($uploadDir)) {
        @mkdir($uploadDir, 0755, true);
    }

    if (!isset($_FILES['video'])) {
        error('请选择要上传的文件');
    }

    $file = $_FILES['video'];

    // 检查错误
    if ($file['error'] !== UPLOAD_ERR_OK) {
        $errors = [
            UPLOAD_ERR_INI_SIZE   => '文件大小超过服务器限制',
            UPLOAD_ERR_FORM_SIZE  => '文件大小超过表单限制',
            UPLOAD_ERR_PARTIAL    => '文件上传不完整',
            UPLOAD_ERR_NO_FILE    => '没有选择文件',
            UPLOAD_ERR_NO_TMP_DIR => '服务器临时目录缺失',
            UPLOAD_ERR_CANT_WRITE => '文件写入失败',
        ];
        error($errors[$file['error']] ?? '上传失败');
    }

    // 检查文件类型
    $allowedTypes = ['video/mp4', 'video/avi', 'video/mov', 'video/wmv', 'video/flv', 'video/webm'];
    $finfo = finfo_open(FILEINFO_MIME_TYPE);
    $mimeType = finfo_file($finfo, $file['tmp_name']);
    finfo_close($finfo);

    if (!in_array($mimeType, $allowedTypes)) {
        error('不支持的视频格式，支持: mp4, avi, mov, wmv, flv, webm');
    }

    // 文件大小限制 200MB
    if ($file['size'] > 200 * 1024 * 1024) {
        error('文件大小不能超过200MB');
    }

    // 生成文件名
    $ext      = pathinfo($file['name'], PATHINFO_EXTENSION);
    $dateDir  = date('Ymd');
    $saveDir  = $uploadDir . $dateDir . '/';

    if (!is_dir($saveDir)) {
        @mkdir($saveDir, 0755, true);
    }

    $saveName = uniqid('v_') . '.' . $ext;
    $savePath = $saveDir . $saveName;

    if (!move_uploaded_file($file['tmp_name'], $savePath)) {
        error('文件保存失败');
    }

    // 获取视频时长（如果可能）
    $duration = 0;

    // 保存到数据库
    $relativePath = $dateDir . '/' . $saveName;
    $stmt = $pdo->prepare("INSERT INTO " . table('video_task') . " (user_id, file_name, file_path, file_size, duration, type) VALUES (?, ?, ?, ?, ?, 'cut')");
    $stmt->execute([
        $currentUser['user_id'],
        $file['name'],
        $relativePath,
        $file['size'],
        $duration
    ]);

    $taskId = $pdo->lastInsertId();

    logOperation($currentUser['user_id'], $currentUser['username'], 'INFO', '视频处理', '上传视频', "上传视频: {$file['name']}");

    success([
        'id'         => (int)$taskId,
        'file_name'  => $file['name'],
        'file_path'  => $relativePath,
        'file_size'  => $file['size'],
        'url'        => $config['upload_url'] . $relativePath,
    ], '上传成功');
}
