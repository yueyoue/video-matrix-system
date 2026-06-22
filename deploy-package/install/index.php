<?php
/**
 * 视频矩阵系统 - 安装向导
 * 三步安装：环境检测 → 数据库配置 → 管理员账号
 */

// 已安装则跳转
if (file_exists(__DIR__ . '/../config.php')) {
    // 检查是否请求卸载重装
    if (isset($_GET['reinstall'])) {
        // 允许重装
    } else {
        echo '<!DOCTYPE html><html><head><meta charset="utf-8"><title>已安装</title></head><body style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;background:#f5f7fa"><div style="text-align:center"><h2 style="color:#165DFF">✅ 系统已安装</h2><p>如需重新安装，请删除 config.php 后刷新页面</p><p style="margin-top:20px"><a href="/" style="color:#165DFF;text-decoration:none">← 返回首页</a></p></div></body></html>';
        exit;
    }
}

// 处理AJAX请求
if (isset($_POST['ajax'])) {
    // 抑制 PHP 错误输出，确保返回纯 JSON
    error_reporting(0);
    ini_set('display_errors', '0');
    header('Content-Type: application/json; charset=utf-8');
    ob_start();
    $action = $_POST['ajax'];

    try {
        switch ($action) {
            case 'check_db':
                handleCheckDb();
                break;
            case 'install':
                handleInstall();
                break;
            default:
                echo json_encode(['ok' => false, 'msg' => '未知操作']);
        }
    } catch (Throwable $e) {
        // 清空缓冲区中的错误输出
        ob_end_clean();
        ob_start();
        echo json_encode(['ok' => false, 'msg' => '安装异常: ' . $e->getMessage()]);
    }

    // 只输出 JSON 部分
    $output = ob_get_clean();
    // 提取最后一个完整的 JSON 对象
    if (preg_match('/(\{[^{}]*\})\s*$/', $output, $m)) {
        echo $m[1];
    } else {
        echo json_encode(['ok' => false, 'msg' => '服务器返回异常']);
    }
    exit;
}

/**
 * 测试数据库连接
 */
function handleCheckDb()
{
    $host     = $_POST['db_host'] ?? 'localhost';
    $port     = (int)($_POST['db_port'] ?? 3306);
    $dbName   = $_POST['db_name'] ?? '';
    $user     = $_POST['db_user'] ?? '';
    $pass     = $_POST['db_pass'] ?? '';
    $createDb = isset($_POST['create_db']);

    try {
        // 先连接MySQL服务器（不指定数据库）
        $dsn = "mysql:host={$host};port={$port};charset=utf8mb4";
        $pdo = new PDO($dsn, $user, $pass, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_TIMEOUT => 5,
        ]);

        // 如果需要自动创建数据库
        if ($createDb && $dbName) {
            $pdo->exec("CREATE DATABASE IF NOT EXISTS `{$dbName}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci");
        }

        // 尝试选择数据库
        $pdo->exec("USE `{$dbName}`");

        echo json_encode(['ok' => true, 'msg' => '数据库连接成功！']);
    } catch (PDOException $e) {
        echo json_encode(['ok' => false, 'msg' => '连接失败: ' . $e->getMessage()]);
    }
}

/**
 * 执行安装
 */
function handleInstall()
{
    $host     = $_POST['db_host'] ?? 'localhost';
    $port     = (int)($_POST['db_port'] ?? 3306);
    $dbName   = $_POST['db_name'] ?? '';
    $user     = $_POST['db_user'] ?? '';
    $pass     = $_POST['db_pass'] ?? '';
    $prefix   = $_POST['db_prefix'] ?? 'vm_';
    $adminUser = trim($_POST['admin_user'] ?? '');
    $adminPass = $_POST['admin_pass'] ?? '';
    $adminPass2 = $_POST['admin_pass2'] ?? '';

    // 验证
    if (empty($dbName) || empty($user)) {
        echo json_encode(['ok' => false, 'msg' => '请填写完整的数据库信息']);
        return;
    }

    if (empty($adminUser) || empty($adminPass)) {
        echo json_encode(['ok' => false, 'msg' => '请填写管理员账号信息']);
        return;
    }

    if (strlen($adminPass) < 6) {
        echo json_encode(['ok' => false, 'msg' => '管理员密码长度不能少于6位']);
        return;
    }

    if ($adminPass !== $adminPass2) {
        echo json_encode(['ok' => false, 'msg' => '两次密码输入不一致']);
        return;
    }

    try {
        // 连接数据库
        $dsn = "mysql:host={$host};port={$port};dbname={$dbName};charset=utf8mb4";
        $pdo = new PDO($dsn, $user, $pass, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        ]);

        // 读取SQL文件
        $sqlFile = __DIR__ . '/install.sql';
        if (!file_exists($sqlFile)) {
            echo json_encode(['ok' => false, 'msg' => 'install.sql 文件不存在']);
            return;
        }

        $sql = file_get_contents($sqlFile);

        // 替换表前缀
        $sql = str_replace('{prefix}', $prefix, $sql);

        // 拆分并执行SQL
        $statements = array_filter(
            array_map('trim', explode(';', $sql)),
            function ($s) { return !empty($s) && $s !== '--'; }
        );

        foreach ($statements as $statement) {
            if (!empty(trim($statement))) {
                $pdo->exec($statement);
            }
        }

        // 创建管理员账号
        $hashedPassword = password_hash($adminPass, PASSWORD_DEFAULT);

        // 检查admin是否已存在（被模拟数据插入）
        $stmt = $pdo->prepare("SELECT COUNT(*) FROM `{$prefix}sys_user` WHERE username = ?");
        $stmt->execute([$adminUser]);

        if ($stmt->fetchColumn() > 0) {
            // 更新现有用户
            $stmt = $pdo->prepare("UPDATE `{$prefix}sys_user` SET password = ?, role = 'admin', status = 'active' WHERE username = ?");
            $stmt->execute([$hashedPassword, $adminUser]);
        } else {
            // 插入新管理员
            $stmt = $pdo->prepare("INSERT INTO `{$prefix}sys_user` (username, password, role, status) VALUES (?, ?, 'admin', 'active')");
            $stmt->execute([$adminUser, $hashedPassword]);
        }

        // 生成配置文件
        $jwtSecret = bin2hex(random_bytes(32));
        $configContent = "<?php\nreturn [\n";
        $configContent .= "    'db_host'    => " . var_export($host, true) . ",\n";
        $configContent .= "    'db_port'    => {$port},\n";
        $configContent .= "    'db_name'    => " . var_export($dbName, true) . ",\n";
        $configContent .= "    'db_user'    => " . var_export($user, true) . ",\n";
        $configContent .= "    'db_pass'    => " . var_export($pass, true) . ",\n";
        $configContent .= "    'db_prefix'  => " . var_export($prefix, true) . ",\n";
        $configContent .= "    'jwt_secret' => '{$jwtSecret}',\n";
        $configContent .= "    'upload_path' => __DIR__ . '/uploads/',\n";
        $configContent .= "    'upload_url'  => '/uploads/',\n";
        $configContent .= "];\n";

        $configPath = __DIR__ . '/../config.php';
        if (file_put_contents($configPath, $configContent) === false) {
            echo json_encode(['ok' => false, 'msg' => '无法写入 config.php，请检查目录权限']);
            return;
        }

        // 记录安装日志
        try {
            $stmt = $pdo->prepare("INSERT INTO `{$prefix}operation_log` (user_id, username, level, module, action, detail) VALUES (1, ?, 'INFO', '系统', '系统安装', '系统初始化完成')");
            $stmt->execute([$adminUser]);
        } catch (Exception $e) {
            // 忽略日志错误
        }

        echo json_encode(['ok' => true, 'msg' => '安装成功！']);
    } catch (PDOException $e) {
        echo json_encode(['ok' => false, 'msg' => '安装失败: ' . $e->getMessage()]);
    } catch (Exception $e) {
        echo json_encode(['ok' => false, 'msg' => '安装失败: ' . $e->getMessage()]);
    }
}
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>视频矩阵系统 - 安装向导</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .installer {
            width: 100%;
            max-width: 600px;
            background: #fff;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.15);
            overflow: hidden;
        }
        .installer-header {
            background: linear-gradient(135deg, #165DFF 0%, #0FC6FF 100%);
            padding: 32px;
            text-align: center;
            color: #fff;
        }
        .installer-logo {
            width: 64px;
            height: 64px;
            background: rgba(255,255,255,0.2);
            border-radius: 16px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 32px;
            margin-bottom: 12px;
        }
        .installer-title {
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 4px;
        }
        .installer-subtitle {
            font-size: 14px;
            opacity: 0.85;
        }

        /* 步骤进度条 */
        .steps {
            display: flex;
            justify-content: center;
            padding: 28px 40px;
            background: #fafbfc;
            border-bottom: 1px solid #f0f0f0;
        }
        .step-item {
            display: flex;
            align-items: center;
            flex: 1;
            max-width: 160px;
        }
        .step-item:last-child { flex: 0; }
        .step-item:last-child .step-line { display: none; }
        .step-num {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 700;
            background: #e5e6eb;
            color: #86909c;
            flex-shrink: 0;
            transition: all 0.3s;
        }
        .step-num.active {
            background: #165DFF;
            color: #fff;
            box-shadow: 0 4px 12px rgba(22,93,255,0.4);
        }
        .step-num.done {
            background: #00b42a;
            color: #fff;
        }
        .step-label {
            margin-left: 10px;
            font-size: 13px;
            color: #86909c;
            white-space: nowrap;
        }
        .step-label.active { color: #165DFF; font-weight: 600; }
        .step-label.done { color: #00b42a; }
        .step-line {
            flex: 1;
            height: 2px;
            background: #e5e6eb;
            margin: 0 12px;
        }
        .step-line.done { background: #00b42a; }

        /* 内容区域 */
        .installer-body {
            padding: 32px 40px;
            min-height: 320px;
        }
        .panel { display: none; }
        .panel.active { display: block; }
        .panel-title {
            font-size: 18px;
            font-weight: 700;
            color: #1d2129;
            margin-bottom: 8px;
        }
        .panel-desc {
            font-size: 14px;
            color: #86909c;
            margin-bottom: 24px;
        }

        /* 环境检测 */
        .check-list { list-style: none; }
        .check-item {
            display: flex;
            align-items: center;
            padding: 14px 16px;
            border: 1px solid #f0f0f0;
            border-radius: 10px;
            margin-bottom: 10px;
            transition: all 0.3s;
        }
        .check-item.pass {
            border-color: #e8ffea;
            background: #f6fff8;
        }
        .check-item.fail {
            border-color: #ffece8;
            background: #fff7f6;
        }
        .check-icon {
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            margin-right: 12px;
            background: #f2f3f5;
            color: #c9cdd4;
            flex-shrink: 0;
        }
        .check-item.pass .check-icon { background: #e8ffea; color: #00b42a; }
        .check-item.fail .check-icon { background: #ffece8; color: #f53f3f; }
        .check-name { flex: 1; font-size: 14px; color: #1d2129; }
        .check-status {
            font-size: 12px;
            padding: 2px 10px;
            border-radius: 20px;
            background: #f2f3f5;
            color: #86909c;
        }
        .check-item.pass .check-status { background: #e8ffea; color: #00b42a; }
        .check-item.fail .check-status { background: #ffece8; color: #f53f3f; }

        /* 表单 */
        .form-group {
            margin-bottom: 18px;
        }
        .form-label {
            display: block;
            font-size: 13px;
            font-weight: 600;
            color: #4e5969;
            margin-bottom: 6px;
        }
        .form-input {
            width: 100%;
            padding: 10px 14px;
            border: 1px solid #e5e6eb;
            border-radius: 8px;
            font-size: 14px;
            color: #1d2129;
            transition: all 0.2s;
            outline: none;
        }
        .form-input:focus {
            border-color: #165DFF;
            box-shadow: 0 0 0 3px rgba(22,93,255,0.1);
        }
        .form-row {
            display: flex;
            gap: 12px;
        }
        .form-row .form-group { flex: 1; }
        .form-hint {
            font-size: 12px;
            color: #c9cdd4;
            margin-top: 4px;
        }
        .form-check {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            color: #4e5969;
            cursor: pointer;
        }
        .form-check input[type="checkbox"] {
            width: 16px;
            height: 16px;
            accent-color: #165DFF;
        }

        /* 按钮 */
        .btn-group {
            display: flex;
            justify-content: space-between;
            margin-top: 28px;
            padding-top: 20px;
            border-top: 1px solid #f0f0f0;
        }
        .btn {
            padding: 10px 28px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .btn-primary {
            background: #165DFF;
            color: #fff;
        }
        .btn-primary:hover:not(:disabled) {
            background: #4080FF;
            box-shadow: 0 4px 12px rgba(22,93,255,0.3);
        }
        .btn-outline {
            background: #fff;
            color: #4e5969;
            border: 1px solid #e5e6eb;
        }
        .btn-outline:hover:not(:disabled) {
            border-color: #165DFF;
            color: #165DFF;
        }
        .btn-test {
            background: #00b42a;
            color: #fff;
            padding: 8px 20px;
            font-size: 13px;
        }
        .btn-test:hover:not(:disabled) {
            background: #23c343;
        }
        .btn-success {
            background: #00b42a;
            color: #fff;
            font-size: 16px;
            padding: 12px 36px;
        }
        .btn-success:hover:not(:disabled) {
            background: #23c343;
            box-shadow: 0 4px 12px rgba(0,180,42,0.3);
        }

        /* 提示信息 */
        .msg {
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 13px;
            margin-bottom: 16px;
            display: none;
        }
        .msg.show { display: block; }
        .msg-error {
            background: #fff7f6;
            border: 1px solid #ffece8;
            color: #f53f3f;
        }
        .msg-success {
            background: #f6fff8;
            border: 1px solid #e8ffea;
            color: #00b42a;
        }
        .msg-info {
            background: #f2f3ff;
            border: 1px solid #e5e8ff;
            color: #165DFF;
        }

        /* 完成页面 */
        .done-page {
            text-align: center;
            padding: 20px 0;
        }
        .done-icon {
            width: 80px;
            height: 80px;
            background: linear-gradient(135deg, #00b42a 0%, #23c343 100%);
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 40px;
            color: #fff;
            margin-bottom: 20px;
            box-shadow: 0 8px 24px rgba(0,180,42,0.3);
        }
        .done-title {
            font-size: 22px;
            font-weight: 700;
            color: #1d2129;
            margin-bottom: 8px;
        }
        .done-desc {
            font-size: 14px;
            color: #86909c;
            margin-bottom: 24px;
            line-height: 1.8;
        }
        .done-actions {
            display: flex;
            gap: 12px;
            justify-content: center;
            flex-wrap: wrap;
        }
        .done-actions .btn {
            min-width: 140px;
            justify-content: center;
        }
        .done-warn {
            margin-top: 24px;
            padding: 14px 18px;
            background: #fff7ec;
            border: 1px solid #ffe4ba;
            border-radius: 8px;
            font-size: 13px;
            color: #ff7d00;
            text-align: left;
        }
        .done-warn strong { color: #d4380d; }

        /* Loading */
        .loading {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255,255,255,0.3);
            border-top-color: #fff;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Footer */
        .installer-footer {
            padding: 16px 40px;
            text-align: center;
            font-size: 12px;
            color: #c9cdd4;
            border-top: 1px solid #f0f0f0;
        }

        @media (max-width: 480px) {
            body { padding: 10px; }
            .installer-header { padding: 24px 20px; }
            .steps { padding: 20px; }
            .installer-body { padding: 24px 20px; }
            .step-label { display: none; }
            .form-row { flex-direction: column; gap: 0; }
        }
    </style>
</head>
<body>
    <div class="installer">
        <!-- Header -->
        <div class="installer-header">
            <div class="installer-logo">🎬</div>
            <div class="installer-title">视频矩阵系统</div>
            <div class="installer-subtitle">Video Matrix System v1.0.0 安装向导</div>
        </div>

        <!-- Steps -->
        <div class="steps">
            <div class="step-item">
                <div class="step-num active" id="stepNum1">1</div>
                <div class="step-label active" id="stepLabel1">环境检测</div>
                <div class="step-line" id="stepLine1"></div>
            </div>
            <div class="step-item">
                <div class="step-num" id="stepNum2">2</div>
                <div class="step-label" id="stepLabel2">数据库配置</div>
                <div class="step-line" id="stepLine2"></div>
            </div>
            <div class="step-item">
                <div class="step-num" id="stepNum3">3</div>
                <div class="step-label" id="stepLabel3">管理员账号</div>
            </div>
        </div>

        <!-- Body -->
        <div class="installer-body">
            <!-- Step 1: 环境检测 -->
            <div class="panel active" id="panel1">
                <div class="panel-title">🔍 环境检测</div>
                <div class="panel-desc">检查服务器环境是否满足系统运行要求</div>

                <ul class="check-list">
                    <li class="check-item" id="check-php">
                        <div class="check-icon">⏱</div>
                        <div class="check-name">PHP 版本 ≥ 7.4</div>
                        <div class="check-status" id="check-php-status">检测中...</div>
                    </li>
                    <li class="check-item" id="check-pdo">
                        <div class="check-icon">⏱</div>
                        <div class="check-name">PDO MySQL 扩展</div>
                        <div class="check-status" id="check-pdo-status">检测中...</div>
                    </li>
                    <li class="check-item" id="check-json">
                        <div class="check-icon">⏱</div>
                        <div class="check-name">JSON 扩展</div>
                        <div class="check-status" id="check-json-status">检测中...</div>
                    </li>
                    <li class="check-item" id="check-upload">
                        <div class="check-icon">⏱</div>
                        <div class="check-name">uploads 目录可写</div>
                        <div class="check-status" id="check-upload-status">检测中...</div>
                    </li>
                    <li class="check-item" id="check-config">
                        <div class="check-icon">⏱</div>
                        <div class="check-name">config.php 不存在（可安装）</div>
                        <div class="check-status" id="check-config-status">检测中...</div>
                    </li>
                    <li class="check-item" id="check-writable">
                        <div class="check-icon">⏱</div>
                        <div class="check-name">网站根目录可写（需创建 config.php）</div>
                        <div class="check-status" id="check-writable-status">检测中...</div>
                    </li>
                </ul>

                <div class="btn-group" style="justify-content: flex-end">
                    <button class="btn btn-primary" id="btnStep1Next" disabled onclick="goStep(2)">
                        下一步 →
                    </button>
                </div>
            </div>

            <!-- Step 2: 数据库配置 -->
            <div class="panel" id="panel2">
                <div class="panel-title">🗄️ 数据库配置</div>
                <div class="panel-desc">配置MySQL数据库连接信息</div>

                <div class="msg" id="dbMsg"></div>

                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">数据库地址</label>
                        <input type="text" class="form-input" id="dbHost" value="localhost" placeholder="localhost">
                    </div>
                    <div class="form-group" style="max-width: 120px">
                        <label class="form-label">端口</label>
                        <input type="number" class="form-input" id="dbPort" value="3306" placeholder="3306">
                    </div>
                </div>

                <div class="form-group">
                    <label class="form-label">数据库名</label>
                    <input type="text" class="form-input" id="dbName" value="video_matrix" placeholder="video_matrix">
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">数据库用户名</label>
                        <input type="text" class="form-input" id="dbUser" value="root" placeholder="root">
                    </div>
                    <div class="form-group">
                        <label class="form-label">数据库密码</label>
                        <input type="password" class="form-input" id="dbPass" placeholder="请输入密码">
                    </div>
                </div>

                <div class="form-group">
                    <label class="form-label">表前缀</label>
                    <input type="text" class="form-input" id="dbPrefix" value="vm_" placeholder="vm_" style="max-width: 200px">
                    <div class="form-hint">同一数据库安装多套系统时可修改前缀区分</div>
                </div>

                <div class="form-group">
                    <label class="form-check">
                        <input type="checkbox" id="createDb" checked>
                        自动创建数据库（如不存在）
                    </label>
                </div>

                <div class="btn-group">
                    <button class="btn btn-outline" onclick="goStep(1)">← 上一步</button>
                    <div>
                        <button class="btn btn-test" id="btnTestDb" onclick="testDb()">
                            测试连接
                        </button>
                        <button class="btn btn-primary" id="btnStep2Next" disabled onclick="goStep(3)" style="margin-left: 8px">
                            下一步 →
                        </button>
                    </div>
                </div>
            </div>

            <!-- Step 3: 管理员账号 -->
            <div class="panel" id="panel3">
                <div class="panel-title">👤 管理员账号</div>
                <div class="panel-desc">设置系统管理员的用户名和密码</div>

                <div class="msg" id="installMsg"></div>

                <div class="form-group">
                    <label class="form-label">管理员用户名</label>
                    <input type="text" class="form-input" id="adminUser" value="admin" placeholder="请输入用户名">
                </div>

                <div class="form-group">
                    <label class="form-label">密码</label>
                    <input type="password" class="form-input" id="adminPass" placeholder="请输入密码（至少6位）">
                </div>

                <div class="form-group">
                    <label class="form-label">确认密码</label>
                    <input type="password" class="form-input" id="adminPass2" placeholder="请再次输入密码">
                </div>

                <div class="btn-group">
                    <button class="btn btn-outline" onclick="goStep(2)">← 上一步</button>
                    <button class="btn btn-success" id="btnInstall" onclick="doInstall()">
                        ✅ 完成安装
                    </button>
                </div>
            </div>

            <!-- Step 4: 完成 -->
            <div class="panel" id="panel4">
                <div class="done-page">
                    <div class="done-icon">✓</div>
                    <div class="done-title">🎉 安装成功！</div>
                    <div class="done-desc">
                        视频矩阵系统已成功安装<br>
                        管理员账号已创建，现在可以开始使用了
                    </div>
                    <div class="done-actions">
                        <a href="/" class="btn btn-primary">🏠 进入首页</a>
                        <a href="/api/auth/login" class="btn btn-outline" target="_blank">🔑 测试登录API</a>
                    </div>
                    <div class="done-warn">
                        <strong>⚠️ 安全提示：</strong>为确保系统安全，请完成以下操作：<br><br>
                        1. 立即删除 <code style="background:#fff3e0;padding:2px 6px;border-radius:4px">install/</code> 目录<br>
                        2. 确保 <code style="background:#fff3e0;padding:2px 6px;border-radius:4px">config.php</code> 文件权限为 644<br>
                        3. 确保 <code style="background:#fff3e0;padding:2px 6px;border-radius:4px">uploads/</code> 目录权限为 755<br>
                        4. 首次登录后请修改默认密码
                    </div>
                </div>
            </div>
        </div>

        <!-- Footer -->
        <div class="installer-footer">
            视频矩阵系统 v1.0.0 · Powered by PHP + MySQL
        </div>
    </div>

    <script>
    // ========== 步骤管理 ==========
    let currentStep = 1;
    let dbConnected = false;

    function goStep(step) {
        // 隐藏所有面板
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        document.getElementById('panel' + step).classList.add('active');

        // 更新步骤指示器
        for (let i = 1; i <= 3; i++) {
            const num = document.getElementById('stepNum' + i);
            const label = document.getElementById('stepLabel' + i);
            const line = document.getElementById('stepLine' + i);

            num.className = 'step-num';
            label.className = 'step-label';

            if (i < step) {
                num.className = 'step-num done';
                num.textContent = '✓';
                label.className = 'step-label done';
                if (line) line.className = 'step-line done';
            } else if (i === step) {
                num.className = 'step-num active';
                num.textContent = i;
                label.className = 'step-label active';
            } else {
                num.textContent = i;
                if (line) line.className = 'step-line';
            }
        }

        currentStep = step;
    }

    // ========== Step 1: 环境检测 ==========
    function runChecks() {
        const checks = [
            { id: 'php', pass: <?php echo version_compare(PHP_VERSION, '7.4', '>=') ? 'true' : 'false'; ?>, detail: 'PHP <?php echo PHP_VERSION; ?>' },
            { id: 'pdo', pass: <?php echo extension_loaded('pdo_mysql') ? 'true' : 'false'; ?>, detail: '<?php echo extension_loaded('pdo_mysql') ? '已安装' : '未安装'; ?>' },
            { id: 'json', pass: <?php echo extension_loaded('json') ? 'true' : 'false'; ?>, detail: '<?php echo extension_loaded('json') ? '已安装' : '未安装'; ?>' },
            { id: 'upload', pass: <?php echo is_writable(__DIR__ . '/../uploads') ? 'true' : 'false'; ?>, detail: '<?php echo is_writable(__DIR__ . '/../uploads') ? '可写' : '不可写'; ?>' },
            { id: 'config', pass: <?php echo !file_exists(__DIR__ . '/../config.php') ? 'true' : 'false'; ?>, detail: '<?php echo file_exists(__DIR__ . '/../config.php') ? '已存在（需删除）' : '不存在（可安装）'; ?>' },
            { id: 'writable', pass: <?php echo is_writable(__DIR__ . '/..') ? 'true' : 'false'; ?>, detail: '<?php echo is_writable(__DIR__ . '/..') ? '可写' : '不可写（需 chmod 755 或 chown www-data）'; ?>' },
        ];

        let allPass = true;
        let delay = 0;

        checks.forEach(check => {
            setTimeout(() => {
                const item = document.getElementById('check-' + check.id);
                const status = document.getElementById('check-' + check.id + '-status');

                if (check.pass) {
                    item.className = 'check-item pass';
                    status.textContent = '✓ ' + check.detail;
                } else {
                    item.className = 'check-item fail';
                    status.textContent = '✗ ' + check.detail;
                    allPass = false;
                }

                // 最后一个检测完成后
                if (check.id === 'writable') {
                    setTimeout(() => {
                        document.getElementById('btnStep1Next').disabled = !allPass;
                        if (!allPass) {
                            // 显示提示
                            const hint = document.createElement('div');
                            hint.className = 'msg msg-error show';
                            hint.style.marginTop = '16px';
                            hint.textContent = '部分环境检测未通过，请修复后刷新页面重新检测';
                            document.getElementById('panel1').insertBefore(hint, document.getElementById('panel1').querySelector('.btn-group'));
                        }
                    }, 200);
                }
            }, delay);

            delay += 300;
        });
    }

    // 页面加载后执行检测
    window.addEventListener('load', runChecks);

    // ========== Step 2: 数据库测试 ==========
    function showDbMsg(text, type) {
        const msg = document.getElementById('dbMsg');
        msg.textContent = text;
        msg.className = 'msg show msg-' + type;
    }

    function testDb() {
        const btn = document.getElementById('btnTestDb');
        btn.disabled = true;
        btn.innerHTML = '<span class="loading"></span> 测试中...';

        const formData = new FormData();
        formData.append('ajax', 'check_db');
        formData.append('db_host', document.getElementById('dbHost').value);
        formData.append('db_port', document.getElementById('dbPort').value);
        formData.append('db_name', document.getElementById('dbName').value);
        formData.append('db_user', document.getElementById('dbUser').value);
        formData.append('db_pass', document.getElementById('dbPass').value);
        if (document.getElementById('createDb').checked) {
            formData.append('create_db', '1');
        }

        fetch(window.location.href, {
            method: 'POST',
            body: formData
        })
        .then(r => r.json())
        .then(data => {
            if (data.ok) {
                showDbMsg('✅ ' + data.msg, 'success');
                dbConnected = true;
                document.getElementById('btnStep2Next').disabled = false;
            } else {
                showDbMsg('❌ ' + data.msg, 'error');
                dbConnected = false;
                document.getElementById('btnStep2Next').disabled = true;
            }
        })
        .catch(err => {
            showDbMsg('❌ 请求失败: ' + err.message, 'error');
            dbConnected = false;
        })
        .finally(() => {
            btn.disabled = false;
            btn.innerHTML = '测试连接';
        });
    }

    // ========== Step 3: 执行安装 ==========
    function showInstallMsg(text, type) {
        const msg = document.getElementById('installMsg');
        msg.textContent = text;
        msg.className = 'msg show msg-' + type;
    }

    function doInstall() {
        const adminUser = document.getElementById('adminUser').value.trim();
        const adminPass = document.getElementById('adminPass').value;
        const adminPass2 = document.getElementById('adminPass2').value;

        if (!adminUser) {
            showInstallMsg('请输入管理员用户名', 'error');
            return;
        }
        if (!adminPass || adminPass.length < 6) {
            showInstallMsg('密码长度不能少于6位', 'error');
            return;
        }
        if (adminPass !== adminPass2) {
            showInstallMsg('两次密码输入不一致', 'error');
            return;
        }

        const btn = document.getElementById('btnInstall');
        btn.disabled = true;
        btn.innerHTML = '<span class="loading"></span> 安装中...';

        const formData = new FormData();
        formData.append('ajax', 'install');
        formData.append('db_host', document.getElementById('dbHost').value);
        formData.append('db_port', document.getElementById('dbPort').value);
        formData.append('db_name', document.getElementById('dbName').value);
        formData.append('db_user', document.getElementById('dbUser').value);
        formData.append('db_pass', document.getElementById('dbPass').value);
        formData.append('db_prefix', document.getElementById('dbPrefix').value);
        formData.append('admin_user', adminUser);
        formData.append('admin_pass', adminPass);
        formData.append('admin_pass2', adminPass2);

        fetch(window.location.href, {
            method: 'POST',
            body: formData
        })
        .then(r => r.json())
        .then(data => {
            if (data.ok) {
                // 安装成功，显示完成页面
                goStep(4);
            } else {
                showInstallMsg('❌ ' + data.msg, 'error');
                btn.disabled = false;
                btn.innerHTML = '✅ 完成安装';
            }
        })
        .catch(err => {
            showInstallMsg('❌ 请求失败: ' + err.message, 'error');
            btn.disabled = false;
            btn.innerHTML = '✅ 完成安装';
        });
    }

    // Enter键提交
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            if (currentStep === 2 && !document.getElementById('btnStep2Next').disabled) {
                // 在第二步按回车，如果已测试连接则进入下一步
            }
            if (currentStep === 3) {
                doInstall();
            }
        }
    });
    </script>
</body>
</html>
