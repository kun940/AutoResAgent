-- ============================================================
-- v1.3 迁移脚本 - OCR分析与前置止损增强
-- 注意：MySQL 8.0 不支持 ADD COLUMN IF NOT EXISTS
-- 本脚本使用存储过程实现幂等，可安全重试
-- ============================================================

DELIMITER //

-- 1. tickets 表新增 image_analysis 字段（幂等）
DROP PROCEDURE IF EXISTS _v13_add_image_analysis//
CREATE PROCEDURE _v13_add_image_analysis()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'tickets'
          AND COLUMN_NAME = 'image_analysis'
    ) THEN
        ALTER TABLE `tickets`
            ADD COLUMN `image_analysis` JSON NULL
            COMMENT 'v1.3: 图片分析结果(含damage_detected/damage_level/fault_types_found/has_emergency_indicators/overall_assessment/suggestion/analysis_source/image_count)'
            AFTER `sop_applied`;
    END IF;
END//

CALL _v13_add_image_analysis()//
DROP PROCEDURE IF EXISTS _v13_add_image_analysis//

-- 2. sop_knowledge_base 表新增 emergency_actions 字段（幂等）
DROP PROCEDURE IF EXISTS _v13_add_emergency_actions//
CREATE PROCEDURE _v13_add_emergency_actions()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'sop_knowledge_base'
          AND COLUMN_NAME = 'emergency_actions'
    ) THEN
        ALTER TABLE `sop_knowledge_base`
            ADD COLUMN `emergency_actions` JSON NULL
            COMMENT 'v1.3: 紧急止损动作列表'
            AFTER `keywords`;
    END IF;
END//

CALL _v13_add_emergency_actions()//
DROP PROCEDURE IF EXISTS _v13_add_emergency_actions//

-- 3. sop_knowledge_base 表新增 scenario_tags 字段（幂等）
DROP PROCEDURE IF EXISTS _v13_add_scenario_tags//
CREATE PROCEDURE _v13_add_scenario_tags()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'sop_knowledge_base'
          AND COLUMN_NAME = 'scenario_tags'
    ) THEN
        ALTER TABLE `sop_knowledge_base`
            ADD COLUMN `scenario_tags` JSON NULL
            COMMENT 'v1.3: 适用场景标签'
            AFTER `emergency_actions`;
    END IF;
END//

CALL _v13_add_scenario_tags()//
DROP PROCEDURE IF EXISTS _v13_add_scenario_tags//

DELIMITER ;

-- 4. 回填原有6条SOP的emergency_actions和scenario_tags（幂等：AND emergency_actions IS NULL）

UPDATE `sop_knowledge_base` SET
  `emergency_actions` = JSON_ARRAY('立即切断设备总电源', '人员远离设备保持通风', '严禁用水灭火', '拨打售后紧急热线400-XXX-XXXX'),
  `scenario_tags` = JSON_ARRAY('冒烟', '过热', '烧焦', '起火')
WHERE `title` = '设备过热/冒烟紧急处置' AND `emergency_actions` IS NULL;

UPDATE `sop_knowledge_base` SET
  `emergency_actions` = JSON_ARRAY('立即切断总闸', '人员远离设备', '严禁触碰设备任何部位', '拨打售后紧急热线400-XXX-XXXX'),
  `scenario_tags` = JSON_ARRAY('漏电', '触电', '带电', '麻手')
WHERE `title` = '漏电紧急处置SOP' AND `emergency_actions` IS NULL;

UPDATE `sop_knowledge_base` SET
  `emergency_actions` = JSON_ARRAY('检查电源连接是否稳定', '确认使用环境温度'),
  `scenario_tags` = JSON_ARRAY('重启', '死机', '频繁重启')
WHERE `title` = '设备频繁重启排查指引' AND `emergency_actions` IS NULL;

UPDATE `sop_knowledge_base` SET
  `emergency_actions` = JSON_ARRAY('尝试重启软件并检查更新', '清除缓存和临时文件'),
  `scenario_tags` = JSON_ARRAY('软件崩溃', '闪退', '报错')
WHERE `title` = '软件崩溃恢复操作' AND `emergency_actions` IS NULL;

UPDATE `sop_knowledge_base` SET
  `emergency_actions` = JSON_ARRAY('记录产品批次号', '上报技术质量部'),
  `scenario_tags` = JSON_ARRAY('批次缺陷', '批量故障')
WHERE `title` = '疑似批次缺陷上报流程' AND `emergency_actions` IS NULL;

UPDATE `sop_knowledge_base` SET
  `scenario_tags` = JSON_ARRAY('配件缺失', '少件')
WHERE `title` = '配件缺失补发流程' AND `scenario_tags` IS NULL;
