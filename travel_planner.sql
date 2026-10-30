/* ============================================================
   数据库: travel_planner2 (全新库，不影响旧库)
   字符集: utf8mb4
   ============================================================ */

/* 1. 创建数据库（如果不存在） */
CREATE DATABASE IF NOT EXISTS `travel_planner2` 
CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `travel_planner2`;

/* ============================================================
   2. 删除旧表（全新库，按依赖顺序）
   ============================================================ */
DROP TABLE IF EXISTS `plan_steps`;
DROP TABLE IF EXISTS `favorites`;
DROP TABLE IF EXISTS `plans`;
DROP TABLE IF EXISTS `cost_matrix`;
DROP TABLE IF EXISTS `spots`;
DROP TABLE IF EXISTS `cities`;
DROP TABLE IF EXISTS `users`;

/* ============================================================
   3. 创建表结构
   ============================================================ */

/* 3.1 用户表 */
CREATE TABLE `users` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '用户ID',
  `username` VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
  `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希',
  `email` VARCHAR(100) DEFAULT NULL COMMENT '邮箱',
  `avatar_url` VARCHAR(255) DEFAULT NULL COMMENT '头像链接',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

/* 3.2 城市/枢纽表 */
CREATE TABLE `cities` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '城市ID',
  `name` VARCHAR(50) NOT NULL COMMENT '城市名称',
  `province` VARCHAR(50) DEFAULT NULL COMMENT '所属省份',
  `hub_name` VARCHAR(100) DEFAULT NULL COMMENT '主要枢纽站',
  `lat` DECIMAL(10, 6) NOT NULL COMMENT '纬度',
  `lng` DECIMAL(10, 6) NOT NULL COMMENT '经度',
  `is_hot` TINYINT(1) DEFAULT 0 COMMENT '是否热门城市',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='城市枢纽表';

/* 3.3 景点表 */
CREATE TABLE `spots` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '景点ID',
  `name` VARCHAR(100) NOT NULL COMMENT '景点名称',
  `city_id` INT NOT NULL COMMENT '所属城市ID',
  `description` VARCHAR(500) DEFAULT NULL COMMENT '简短描述',
  `img_url` VARCHAR(255) DEFAULT NULL COMMENT '图片链接',
  `lat` DECIMAL(10, 6) NOT NULL COMMENT '纬度',
  `lng` DECIMAL(10, 6) NOT NULL COMMENT '经度',
  `cost_time_extra` INT DEFAULT 120 COMMENT '游览建议耗时(分钟)',
  PRIMARY KEY (`id`),
  KEY `fk_spot_city` (`city_id`),
  CONSTRAINT `fk_spot_city` FOREIGN KEY (`city_id`) REFERENCES `cities` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='景点表';

/* 3.4 交通成本矩阵表（核心静态数据） */
CREATE TABLE `cost_matrix` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '记录ID',
  `from_city_id` INT NOT NULL COMMENT '出发城市ID',
  `to_city_id` INT NOT NULL COMMENT '到达城市ID',
  `mode` VARCHAR(20) NOT NULL DEFAULT '综合' COMMENT '交通方式',
  `time_cost` INT NOT NULL COMMENT '耗时(分钟)',
  `money_cost` DECIMAL(10, 2) NOT NULL COMMENT '费用(元)',
  `transfer_times` TINYINT DEFAULT 0 COMMENT '换乘次数',
  `discomfort` DECIMAL(5, 2) DEFAULT 0 COMMENT '不适感指数',
  PRIMARY KEY (`id`),
  KEY `fk_cost_from` (`from_city_id`),
  KEY `fk_cost_to` (`to_city_id`),
  CONSTRAINT `fk_cost_from` FOREIGN KEY (`from_city_id`) REFERENCES `cities` (`id`),
  CONSTRAINT `fk_cost_to` FOREIGN KEY (`to_city_id`) REFERENCES `cities` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交通成本矩阵表';

/* 3.5 用户规划记录表 */
CREATE TABLE `plans` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '规划ID',
  `user_id` INT NOT NULL COMMENT '创建者ID',
  `start_city_id` INT NOT NULL COMMENT '起点城市ID',
  `end_city_id` INT NOT NULL COMMENT '终点城市ID',
  `spot_ids` VARCHAR(100) DEFAULT NULL COMMENT '途经景点ID',
  `total_time` INT NOT NULL COMMENT '总耗时(分钟)',
  `total_money` DECIMAL(10, 2) NOT NULL COMMENT '总花费(元)',
  `total_discomfort` DECIMAL(5, 2) DEFAULT 0 COMMENT '总不适感',
  `route_detail` JSON NOT NULL COMMENT '完整路径详情(JSON)',
  `is_public` TINYINT(1) DEFAULT 0 COMMENT '是否公开',
  `rating` TINYINT DEFAULT 0 COMMENT '评分(1-5)',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `fk_plan_user` (`user_id`),
  CONSTRAINT `fk_plan_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='规划记录表';

/* 3.6 规划步骤详情表 */
CREATE TABLE `plan_steps` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '步骤ID',
  `plan_id` INT NOT NULL COMMENT '所属规划ID',
  `step_order` INT NOT NULL COMMENT '步骤序号',
  `mode` VARCHAR(20) NOT NULL COMMENT '交通方式',
  `from_name` VARCHAR(100) NOT NULL COMMENT '起点名称',
  `to_name` VARCHAR(100) NOT NULL COMMENT '终点名称',
  `duration` INT NOT NULL COMMENT '本段耗时(分钟)',
  `cost` DECIMAL(10, 2) DEFAULT 0 COMMENT '本段花费(元)',
  `instruction` VARCHAR(255) DEFAULT NULL COMMENT '操作指引',
  PRIMARY KEY (`id`),
  KEY `fk_step_plan` (`plan_id`),
  CONSTRAINT `fk_step_plan` FOREIGN KEY (`plan_id`) REFERENCES `plans` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='规划步骤表';

/* 3.7 收藏表 */
CREATE TABLE `favorites` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '收藏ID',
  `user_id` INT NOT NULL COMMENT '用户ID',
  `plan_id` INT NOT NULL COMMENT '规划ID',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '收藏时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_plan` (`user_id`, `plan_id`),
  KEY `fk_fav_plan` (`plan_id`),
  CONSTRAINT `fk_fav_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_fav_plan` FOREIGN KEY (`plan_id`) REFERENCES `plans` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='收藏表';


/* ============================================================
   4. 插入初始测试数据
   ============================================================ */

/* 4.1 插入20个核心城市 */
INSERT INTO `cities` (`name`, `province`, `hub_name`, `lat`, `lng`, `is_hot`) VALUES
('北京', '北京', '北京南站/大兴机场', 39.904200, 116.407400, 1),
('上海', '上海', '上海虹桥站/浦东机场', 31.230400, 121.473700, 1),
('广州', '广东', '广州南站/白云机场', 23.129100, 113.264400, 1),
('深圳', '广东', '深圳北站/宝安机场', 22.543100, 114.057900, 1),
('杭州', '浙江', '杭州东站/萧山机场', 30.274100, 120.155100, 1),
('南京', '江苏', '南京南站/禄口机场', 32.060300, 118.796900, 1),
('武汉', '湖北', '武汉站/天河机场', 30.592800, 114.305500, 1),
('成都', '四川', '成都东站/双流机场', 30.572800, 104.066800, 1),
('重庆', '重庆', '重庆北站/江北机场', 29.563000, 106.551600, 1),
('西安', '陕西', '西安北站/咸阳机场', 34.341600, 108.939800, 1),
('长沙', '湖南', '长沙南站/黄花机场', 28.228200, 112.938800, 1),
('郑州', '河南', '郑州东站/新郑机场', 34.756600, 113.665400, 0),
('贵阳', '贵州', '贵阳北站/龙洞堡机场', 26.647600, 106.630200, 0),
('昆明', '云南', '昆明南站/长水机场', 24.880100, 102.832900, 0),
('厦门', '福建', '厦门北站/高崎机场', 24.479800, 118.089400, 0),
('青岛', '山东', '青岛北站/胶东机场', 36.067100, 120.382600, 0),
('天津', '天津', '天津西站/滨海机场', 39.084200, 117.201000, 0),
('苏州', '江苏', '苏州站/苏南硕放机场', 31.299000, 120.585300, 0),
('宁波', '浙江', '宁波站/栎社机场', 29.868300, 121.544000, 0),
('福州', '福建', '福州南站/长乐机场', 26.074500, 119.296500, 0);

/* 4.2 插入10个著名景点 */
INSERT INTO `spots` (`name`, `city_id`, `description`, `img_url`, `lat`, `lng`, `cost_time_extra`) VALUES
('故宫博物院', 1, '世界最大的宫殿建筑群', 'https://example.com/gugong.jpg', 39.916300, 116.397200, 180),
('外滩', 2, '万国建筑博览群，上海地标', 'https://example.com/waitan.jpg', 31.241000, 121.488200, 60),
('广州塔', 3, '昵称小蛮腰，广州地标', 'https://example.com/canton_tower.jpg', 23.106400, 113.324500, 90),
('西湖', 5, '人间天堂，免费5A景区', 'https://example.com/west_lake.jpg', 30.255200, 120.141000, 120),
('夫子庙', 6, '秦淮河畔，金陵文化', 'https://example.com/fuzimiao.jpg', 32.020200, 118.783100, 90),
('黄鹤楼', 7, '天下江山第一楼', 'https://example.com/huanghelou.jpg', 30.547000, 114.297000, 60),
('宽窄巷子', 8, '成都慢生活地标', 'https://example.com/kuanzhai.jpg', 30.663300, 104.058800, 60),
('洪崖洞', 9, '网红打卡地，现实版千与千寻', 'https://example.com/hongyadong.jpg', 29.559800, 106.582800, 90),
('兵马俑', 10, '世界第八大奇迹', 'https://example.com/bingmayong.jpg', 34.384800, 109.273400, 150),
('橘子洲', 11, '毛泽东青年雕像', 'https://example.com/juzizhou.jpg', 28.203400, 112.965500, 60);

/* 4.3 插入交通成本矩阵（模拟数据，用于算法演示） */
INSERT INTO `cost_matrix` (`from_city_id`, `to_city_id`, `mode`, `time_cost`, `money_cost`, `transfer_times`, `discomfort`) VALUES
(1, 1, '综合', 30, 15.00, 1, 1.0),   -- 北京市内
(1, 17, '综合', 150, 65.00, 1, 1.5),  -- 北京->天津
(1, 2, '综合', 360, 660.00, 1, 2.0),  -- 北京->上海 (调为接近真实)
(1, 3, '综合', 540, 860.00, 2, 3.0),  -- 北京->广州
(1, 8, '综合', 540, 750.00, 2, 3.5),  -- 北京->成都
(1, 13, '综合', 480, 850.00, 2, 4.0), -- 北京->贵阳
(2, 5, '综合', 90, 100.00, 0, 0.5),   -- 上海->杭州
(2, 6, '综合', 160, 150.00, 0, 1.0),  -- 上海->南京
(3, 4, '综合', 50, 40.00, 0, 0.5),    -- 广州->深圳
(8, 9, '综合', 120, 150.00, 0, 0.5),  -- 成都->重庆
(7, 11, '综合', 150, 200.00, 1, 1.5), -- 武汉->长沙
(10, 12, '综合', 120, 220.00, 1, 1.0),-- 西安->郑州
(13, 8, '综合', 300, 600.00, 2, 3.0); -- 贵阳->成都

/* 4.4 插入一个测试用户（密码稍后后端生成，先占位） */
INSERT INTO `users` (`username`, `password_hash`, `email`) VALUES
('test_user', 'scrypt:32768:8:1$placeholder', 'test@demo.com');

/* 4.5 插入一条演示规划记录（用于展示分步效果） */
INSERT INTO `plans` (`user_id`, `start_city_id`, `end_city_id`, `spot_ids`, `total_time`, `total_money`, `total_discomfort`, `route_detail`, `is_public`, `rating`) VALUES
(1, 1, 2, '1,2', 480, 850.00, 3.5, '{"steps": [{"mode":"地铁","from":"北京南站","to":"上海虹桥站","duration":300,"cost":550}]}', 1, 4);

INSERT INTO `plan_steps` (`plan_id`, `step_order`, `mode`, `from_name`, `to_name`, `duration`, `cost`, `instruction`) VALUES
(1, 1, '步行', '故宫', '地铁天安门东站', 15, 0.00, '步行至地铁站'),
(1, 2, '地铁', '天安门东', '北京南站', 30, 5.00, '乘坐地铁4号线'),
(1, 3, '高铁', '北京南站', '上海虹桥站', 300, 550.00, '乘坐G1次高铁'),
(1, 4, '地铁', '上海虹桥站', '外滩', 40, 6.00, '乘坐地铁10号线');

/* 全部执行完毕 */
SELECT '✅ 数据库 travel_planner2 创建成功！所有表及测试数据已插入！' AS '状态';