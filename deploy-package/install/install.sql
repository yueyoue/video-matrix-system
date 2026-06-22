-- 短视频矩阵运营系统 - 建表SQL
-- 兼容 MySQL 5.5+（每个表最多一个 TIMESTAMP 列带 CURRENT_TIMESTAMP）

CREATE TABLE IF NOT EXISTS `{prefix}sys_user` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `username` VARCHAR(50) UNIQUE NOT NULL,
  `password` VARCHAR(255) NOT NULL,
  `role` ENUM('admin','operator') DEFAULT 'operator',
  `daily_quota` INT DEFAULT 50,
  `used_quota` INT DEFAULT 0,
  `status` ENUM('active','disabled') DEFAULT 'active',
  `last_login` DATETIME,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `{prefix}platform_account` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NOT NULL,
  `platform` ENUM('douyin','kuaishou','xiaohongshu','weixin') NOT NULL,
  `nickname` VARCHAR(100) NOT NULL,
  `avatar_url` VARCHAR(500),
  `cookie` TEXT,
  `status` ENUM('active','expired') DEFAULT 'active',
  `works_count` INT DEFAULT 0,
  `total_plays` BIGINT DEFAULT 0,
  `today_publish` VARCHAR(20) DEFAULT '0/3',
  `last_login` DATETIME,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `{prefix}video_task` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NOT NULL,
  `file_name` VARCHAR(255) NOT NULL,
  `file_path` VARCHAR(500),
  `file_size` BIGINT DEFAULT 0,
  `duration` INT DEFAULT 0,
  `type` ENUM('cut','mix') NOT NULL,
  `status` ENUM('pending','processing','done','failed') DEFAULT 'pending',
  `source_ids` TEXT,
  `config` TEXT,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `{prefix}publish_record` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NOT NULL,
  `account_id` INT,
  `video_id` INT,
  `platform` VARCHAR(20),
  `account_name` VARCHAR(100),
  `video_title` VARCHAR(255),
  `scheduled_time` DATETIME,
  `published_time` DATETIME,
  `status` ENUM('waiting','publishing','success','failed') DEFAULT 'waiting',
  `error_msg` TEXT,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `{prefix}video_data` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `publish_id` INT,
  `platform` VARCHAR(20),
  `account_name` VARCHAR(100),
  `video_title` VARCHAR(255),
  `plays` BIGINT DEFAULT 0,
  `likes` INT DEFAULT 0,
  `comments` INT DEFAULT 0,
  `shares` INT DEFAULT 0,
  `publish_time` DATETIME,
  `synced_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `{prefix}ai_voice` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(100) NOT NULL,
  `voice_id` VARCHAR(50) NOT NULL,
  `type` ENUM('male','female') DEFAULT 'female',
  `scene` VARCHAR(200),
  `status` ENUM('active','disabled') DEFAULT 'active',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `{prefix}ai_config` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `provider` VARCHAR(50) DEFAULT 'aliyun',
  `app_id` VARCHAR(100),
  `secret_key` VARCHAR(255),
  `daily_limit` INT DEFAULT 100,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `{prefix}platform_config` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `platform` VARCHAR(20) NOT NULL UNIQUE,
  `config_json` TEXT,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `{prefix}app_version` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `version` VARCHAR(20) NOT NULL,
  `changelog` TEXT,
  `download_url` VARCHAR(500),
  `status` ENUM('current','archived','delisted') DEFAULT 'current',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `{prefix}operation_log` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT,
  `username` VARCHAR(50),
  `level` ENUM('INFO','WARN','ERROR') DEFAULT 'INFO',
  `module` VARCHAR(50),
  `action` VARCHAR(100),
  `detail` TEXT,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX `idx_created` (`created_at`),
  INDEX `idx_level` (`level`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `{prefix}publish_rule` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NOT NULL,
  `platforms` TEXT,
  `daily_limit` INT DEFAULT 3,
  `publish_times` TEXT,
  `order_mode` VARCHAR(20) DEFAULT 'sequence',
  `auto_remove` TINYINT DEFAULT 1,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 初始数据

INSERT INTO `{prefix}ai_voice` (`name`, `voice_id`, `type`, `scene`) VALUES
('温柔女声-小云', 'xiaoyun', 'female', '通用、讲解'),
('磁性男声-阿凯', 'akai', 'male', '解说、旁白'),
('活力少女-小桃', 'xiaotao', 'female', '娱乐、种草'),
('沉稳旁白-老周', 'laozhou', 'male', '纪录片、正式');

INSERT INTO `{prefix}ai_config` (`provider`, `app_id`, `secret_key`, `daily_limit`) VALUES
('aliyun', '', '', 100);

INSERT INTO `{prefix}platform_config` (`platform`, `config_json`) VALUES
('douyin', '{"creatorUrl":"https://creator.douyin.com/","loginCheck":"https://creator.douyin.com/api/login/check","videoList":"https://creator.douyin.com/api/videolist","publish":"https://creator.douyin.com/api/publish","publishBtn":".publish-btn","cookieDays":30}'),
('kuaishou', '{"creatorUrl":"https://cp.kuaishou.com/","loginCheck":"https://cp.kuaishou.com/api/login/check","videoList":"https://cp.kuaishou.com/api/videolist","publish":"https://cp.kuaishou.com/api/publish","publishBtn":".upload-btn","cookieDays":15}'),
('xiaohongshu', '{"creatorUrl":"https://creator.xiaohongshu.com/","loginCheck":"https://creator.xiaohongshu.com/api/login/check","videoList":"https://creator.xiaohongshu.com/api/videolist","publish":"https://creator.xiaohongshu.com/api/publish","publishBtn":".submit-btn","cookieDays":7}'),
('weixin', '{"creatorUrl":"https://channels.weixin.qq.com/","loginCheck":"https://channels.weixin.qq.com/api/login/check","videoList":"https://channels.weixin.qq.com/api/videolist","publish":"https://channels.weixin.qq.com/api/publish","publishBtn":".post-btn","cookieDays":30}');

INSERT INTO `{prefix}app_version` (`version`, `changelog`, `status`) VALUES
('v1.0.0', '系统首发版本', 'current');

INSERT INTO `{prefix}operation_log` (`username`, `level`, `module`, `action`, `detail`) VALUES
('system', 'INFO', '系统', '系统安装', '系统初始化完成');
