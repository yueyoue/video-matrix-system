<?php
/**
 * 短视频矩阵系统 - 安装向导
 * 访问 /install 运行安装
 */

// 已安装则跳转
if (file_exists(__DIR__ . '/../config.php')) {
    echo '<!DOCTYPE html><html><head><meta charset="utf-8"><title>已安装</title></head><body style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:system-ui"><div style="text-align:center"><h2>✅ 系统已安装</h2><p>如需重新安装，请先删除 <code>config.php</code> 文件</p><a href="/">进入后台</a></div></body></html>';
    exit;
}

$step = isset($_GET['step']) ? (int)$_GET['step'] : 1;
$error = '';
$success = '';

// 处理表单提交
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if ($step === 2) {
        // 测试数据库连接
        $db_host = trim($_POST['db_host'] ?? 'localhost');
        $db_port = trim($_POST['db_port'] ?? '3306');
        $db_name = trim($_POST['db_name'] ?? '');
        $db_user = trim($_POST['db_user'] ?? '');
        $db_pass = $_POST['db_pass'] ?? '';
        $db_prefix = trim($_POST['db_prefix'] ?? 'vm_');
        $auto_create = isset($_POST['auto_create_db']);

        try {
            // 先连接MySQL（不指定数据库）
            $dsn = "mysql:host={$db_host};port={$db_port};charset=utf8mb4";
            $pdo = new PDO($dsn, $db_user, $db_pass, [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION
            ]);

            // 自动创建数据库
            if ($auto_create) {
                $pdo->exec("CREATE DATABASE IF NOT EXISTS `{$db_name}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");
            }

            // 连接指定数据库
            $dsn = "mysql:host={$db_host};port={$db_port};dbname={$db_name};charset=utf8mb4";
            $pdo = new PDO($dsn, $db_user, $db_pass, [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION
            ]);

            // 保存到 session
            session_start();
            $_SESSION['db'] = [
                'host' => $db_host, 'port' => $db_port,
                'name' => $db_name, 'user' => $db_user,
                'pass' => $db_pass, 'prefix' => $db_prefix
            ];
            header('Location: ?step=3');
            exit;
        } catch (PDOException $e) {
            $error = '数据库连接失败：' . $e->getMessage();
        }
    }

    if ($step === 3) {
        session_start();
        $db = $_SESSION['db'] ?? null;
        if (!$db) {
            header('Location: ?step=2');
            exit;
        }

        $admin_user = trim($_POST['admin_user'] ?? '');
        $admin_pass = $_POST['admin_pass'] ?? '';
        $admin_pass2 = $_POST['admin_pass2'] ?? '';

        if (!$admin_user || !$admin_pass) {
            $error = '请填写管理员账号和密码';
        } elseif ($admin_pass !== $admin_pass2) {
            $error = '两次密码不一致';
        } elseif (strlen($admin_pass) < 6) {
            $error = '密码至少6位';
        } else {
            try {
                $dsn = "mysql:host={$db['host']};port={$db['port']};dbname={$db['name']};charset=utf8mb4";
                $pdo = new PDO($dsn, $db['user'], $db['pass'], [
                    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION
                ]);

                // 读取并执行SQL
                $sql = file_get_contents(__DIR__ . '/install.sql');
                $sql = str_replace('{prefix}', $db['prefix'], $sql);

                // 逐条执行
                $statements = array_filter(array_map('trim', explode(';', $sql)));
                foreach ($statements as $stmt) {
                    if (!empty($stmt) && $stmt !== '--') {
                        $pdo->exec($stmt);
                    }
                }

                // 创建管理员
                $hash = password_hash($admin_pass, PASSWORD_DEFAULT);
                $pdo->prepare("INSERT INTO `{$db['prefix']}sys_user` (`username`, `password`, `role`, `daily_quota`, `status`) VALUES (?, ?, 'admin', 999, 'active')")
                    ->execute([$admin_user, $hash]);

                // 创建配置文件
                $config_content = "<?php\nreturn [\n";
                $config_content .= "    'db_host' => " . var_export($db['host'], true) . ",\n";
                $config_content .= "    'db_port' => " . (int)$db['port'] . ",\n";
                $config_content .= "    'db_name' => " . var_export($db['name'], true) . ",\n";
                $config_content .= "    'db_user' => " . var_export($db['user'], true) . ",\n";
                $config_content .= "    'db_pass' => " . var_export($db['pass'], true) . ",\n";
                $config_content .= "    'db_prefix' => " . var_export($db['prefix'], true) . ",\n";
                $config_content .= "    'jwt_secret' => " . var_export(bin2hex(random_bytes(32)), true) . ",\n";
                $config_content .= "    'upload_path' => __DIR__ . '/uploads/',\n";
                $config_content .= "    'upload_url' => '/uploads/',\n";
                $config_content .= "];\n";

                file_put_contents(__DIR__ . '/../config.php', $config_content);

                // 记录安装日志
                $pdo->prepare("INSERT INTO `{$db['prefix']}operation_log` (`username`, `level`, `module`, `action`, `detail`) VALUES ('system', 'INFO', '系统', '系统安装', '系统初始化完成，管理员：{$admin_user}')")
                    ->execute();

                $success = '安装成功！';
            } catch (Exception $e) {
                $error = '安装失败：' . $e->getMessage();
            }
        }
    }
}
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>系统安装 - 短视频矩阵运营系统</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #f0f2f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .container { width: 100%; max-width: 580px; }
        .header { text-align: center; margin-bottom: 24px; }
        .header h1 { font-size: 24px; color: #1a1a1a; margin-bottom: 8px; }
        .header p { color: #666; font-size: 14px; }
        .card { background: #fff; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,.08); overflow: hidden; }
        .steps { display: flex; border-bottom: 1px solid #f0f0f0; }
        .step { flex: 1; text-align: center; padding: 16px; font-size: 14px; color: #999; position: relative; }
        .step.active { color: #165DFF; font-weight: 600; }
        .step.done { color: #00B42A; }
        .step::after { content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 3px; background: transparent; }
        .step.active::after { background: #165DFF; }
        .step.done::after { background: #00B42A; }
        .step-num { display: inline-block; width: 24px; height: 24px; border-radius: 50%; background: #f0f0f0; color: #999; line-height: 24px; font-size: 12px; margin-right: 6px; }
        .step.active .step-num { background: #165DFF; color: #fff; }
        .step.done .step-num { background: #00B42A; color: #fff; }
        .body { padding: 32px; }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; font-size: 14px; color: #333; margin-bottom: 8px; font-weight: 500; }
        .form-group input, .form-group select { width: 100%; padding: 10px 14px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; outline: none; transition: border-color .2s; }
        .form-group input:focus { border-color: #165DFF; box-shadow: 0 0 0 3px rgba(22,93,255,.1); }
        .form-row { display: flex; gap: 16px; }
        .form-row .form-group { flex: 1; }
        .checkbox { display: flex; align-items: center; gap: 8px; font-size: 14px; color: #666; }
        .checkbox input { width: auto; }
        .btn { display: inline-block; padding: 12px 32px; border: none; border-radius: 8px; font-size: 15px; font-weight: 500; cursor: pointer; transition: all .2s; text-decoration: none; }
        .btn-primary { background: #165DFF; color: #fff; }
        .btn-primary:hover { background: #0e4ad9; }
        .btn-default { background: #f5f5f5; color: #333; border: 1px solid #ddd; }
        .btn-default:hover { background: #eee; }
        .btn-success { background: #00B42A; color: #fff; }
        .btn-success:hover { background: #009a24; }
        .btn-block { display: block; width: 100%; text-align: center; }
        .btn-group { display: flex; gap: 12px; margin-top: 24px; }
        .btn-group .btn { flex: 1; text-align: center; }
        .alert { padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }
        .alert-error { background: #fff2f0; color: #cf1322; border: 1px solid #ffccc7; }
        .alert-success { background: #f6ffed; color: #389e0d; border: 1px solid #b7eb8f; }
        .check-list { list-style: none; }
        .check-list li { padding: 10px 0; border-bottom: 1px solid #f5f5f5; display: flex; justify-content: space-between; align-items: center; font-size: 14px; }
        .check-list li:last-child { border: none; }
        .check-ok { color: #00B42A; font-weight: 600; }
        .check-fail { color: #F53F3F; font-weight: 600; }
        .result { text-align: center; padding: 20px 0; }
        .result .icon { font-size: 64px; margin-bottom: 16px; }
        .result h2 { font-size: 22px; color: #1a1a1a; margin-bottom: 12px; }
        .result p { color: #666; font-size: 14px; line-height: 1.8; }
        .warn { background: #fffbe6; border: 1px solid #ffe58f; border-radius: 8px; padding: 12px 16px; margin-top: 16px; font-size: 13px; color: #ad6800; }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>🎬 短视频矩阵运营系统</h1>
        <p>安装向导</p>
    </div>
    <div class="card">
        <div class="steps">
            <div class="step <?php echo $step >= 1 ? ($step > 1 ? 'done' : 'active') : ''; ?>">
                <span class="step-num"><?php echo $step > 1 ? '✓' : '1'; ?></span>环境检测
            </div>
            <div class="step <?php echo $step >= 2 ? ($step > 2 ? 'done' : 'active') : ''; ?>">
                <span class="step-num"><?php echo $step > 2 ? '✓' : '2'; ?></span>数据库配置
            </div>
            <div class="step <?php echo $step >= 3 ? 'active' : ''; ?>">
                <span class="step-num">3</span>完成安装
            </div>
        </div>
        <div class="body">

            <?php if ($error): ?>
                <div class="alert alert-error">❌ <?php echo htmlspecialchars($error); ?></div>
            <?php endif; ?>

            <!-- ========== Step 1: 环境检测 ========== -->
            <?php if ($step === 1):
                $checks = [
                    ['PHP 版本 ≥ 7.4', version_compare(PHP_VERSION, '7.4.0', '>=')],
                    ['PDO MySQL 扩展', extension_loaded('pdo_mysql')],
                    ['JSON 扩展', extension_loaded('json')],
                    ['Session 支持', extension_loaded('session')],
                    ['uploads 目录可写', is_writable(__DIR__ . '/../uploads') || @mkdir(__DIR__ . '/../uploads', 0755, true)],
                    ['config.php 可写', is_writable(__DIR__ . '/..')],
                ];
                $all_pass = true;
                foreach ($checks as $c) { if (!$c[1]) $all_pass = false; }
            ?>
                <h3 style="font-size:16px;margin-bottom:16px;color:#333;">环境检测</h3>
                <ul class="check-list">
                    <?php foreach ($checks as $c): ?>
                    <li>
                        <span><?php echo $c[0]; ?></span>
                        <span class="<?php echo $c[1] ? 'check-ok' : 'check-fail'; ?>">
                            <?php echo $c[1] ? '✅ 通过' : '❌ 不通过'; ?>
                        </span>
                    </li>
                    <?php endforeach; ?>
                </ul>
                <?php if ($all_pass): ?>
                    <div class="btn-group">
                        <a href="?step=2" class="btn btn-primary btn-block">下一步 →</a>
                    </div>
                <?php else: ?>
                    <div class="alert alert-error" style="margin-top:16px;">请先解决以上不通过的项目再继续安装</div>
                <?php endif; ?>
            <?php endif; ?>

            <!-- ========== Step 2: 数据库配置 ========== -->
            <?php if ($step === 2): ?>
                <h3 style="font-size:16px;margin-bottom:16px;color:#333;">数据库配置</h3>
                <form method="POST" action="?step=2">
                    <div class="form-row">
                        <div class="form-group">
                            <label>数据库地址</label>
                            <input type="text" name="db_host" value="<?php echo htmlspecialchars($_POST['db_host'] ?? 'localhost'); ?>" required>
                        </div>
                        <div class="form-group" style="max-width:120px;">
                            <label>端口</label>
                            <input type="text" name="db_port" value="<?php echo htmlspecialchars($_POST['db_port'] ?? '3306'); ?>" required>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>数据库名</label>
                        <input type="text" name="db_name" value="<?php echo htmlspecialchars($_POST['db_name'] ?? 'video_matrix'); ?>" required>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>数据库用户名</label>
                            <input type="text" name="db_user" value="<?php echo htmlspecialchars($_POST['db_user'] ?? 'root'); ?>" required>
                        </div>
                        <div class="form-group">
                            <label>数据库密码</label>
                            <input type="password" name="db_pass" value="">
                        </div>
                    </div>
                    <div class="form-group">
                        <label>表前缀</label>
                        <input type="text" name="db_prefix" value="<?php echo htmlspecialchars($_POST['db_prefix'] ?? 'vm_'); ?>">
                    </div>
                    <div class="form-group">
                        <label class="checkbox">
                            <input type="checkbox" name="auto_create_db" checked>
                            自动创建数据库（如不存在）
                        </label>
                    </div>
                    <div class="btn-group">
                        <a href="?step=1" class="btn btn-default">← 上一步</a>
                        <button type="submit" class="btn btn-primary">测试连接并继续 →</button>
                    </div>
                </form>
            <?php endif; ?>

            <!-- ========== Step 3: 完成安装 ========== -->
            <?php if ($step === 3):
                if ($success): ?>
                    <div class="result">
                        <div class="icon">🎉</div>
                        <h2>安装成功！</h2>
                        <p>系统已安装完成，请删除 install 目录后进入后台</p>
                        <div class="warn">
                            ⚠️ 安全提示：请立即删除 <code>server/install/</code> 目录，防止被再次安装！
                        </div>
                        <div class="btn-group" style="justify-content:center;">
                            <a href="/" class="btn btn-success">进入管理后台</a>
                        </div>
                    </div>
                <?php else: ?>
                    <h3 style="font-size:16px;margin-bottom:16px;color:#333;">设置管理员账号</h3>
                    <form method="POST" action="?step=3">
                        <div class="form-group">
                            <label>管理员用户名</label>
                            <input type="text" name="admin_user" value="<?php echo htmlspecialchars($_POST['admin_user'] ?? 'admin'); ?>" required>
                        </div>
                        <div class="form-group">
                            <label>密码</label>
                            <input type="password" name="admin_pass" placeholder="至少6位" required>
                        </div>
                        <div class="form-group">
                            <label>确认密码</label>
                            <input type="password" name="admin_pass2" required>
                        </div>
                        <div class="btn-group">
                            <a href="?step=2" class="btn btn-default">← 上一步</a>
                            <button type="submit" class="btn btn-success">✅ 完成安装</button>
                        </div>
                    </form>
                <?php endif; ?>
            <?php endif; ?>

        </div>
    </div>
</div>
</body>
</html>
