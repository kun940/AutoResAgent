-- ============================================================
-- 迁移脚本 v1.1 - 出单管理模块
-- 新增表: service_orders, quality_trace_index, order_mapping_rules
-- 修改表: tickets (新增 order_status 字段)
-- 初始数据: 27条出单映射规则
-- 历史数据: 回填 quality_trace_index
-- ============================================================

-- ------------------------------------------------------------
-- 1. 创建 service_orders 表（服务工单）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `service_orders` (
    `id`            BIGINT          NOT NULL AUTO_INCREMENT,
    `order_no`      VARCHAR(50)     NOT NULL                    COMMENT '单据编号 SO-{TYPE_PREFIX}-{YYYYMMDD}-{SEQ}',
    `ticket_id`     VARCHAR(50)     NOT NULL                    COMMENT '关联工单ID',
    `order_type`    VARCHAR(30)     NOT NULL                    COMMENT '工单类型: Replacement/Repair/Return_Exchange/Tech_Support/QC',
    `order_type_label` VARCHAR(20)  NOT NULL                    COMMENT '工单类型标签: 补发单/维修单/退换单/技术支援单/质检单',
    `status`        VARCHAR(30)     NOT NULL DEFAULT 'pending'  COMMENT '状态: pending/processing/executing/completed/cancelled',
    `priority`      VARCHAR(30)     NOT NULL DEFAULT 'Medium_Priority' COMMENT '优先级',
    `department`    VARCHAR(100)    NOT NULL                    COMMENT '责任部门',
    `sla_hours`     INT             NOT NULL DEFAULT 48         COMMENT 'SLA时限(小时)',
    `deadline`      DATETIME        NULL                        COMMENT '截止时间',
    `material_list` JSON            NULL                        COMMENT '物料清单',
    `issue_category` VARCHAR(100)   NULL                        COMMENT '问题分类',
    `urgency_level` VARCHAR(50)     NULL                        COMMENT '紧急程度',
    `model_number`  VARCHAR(100)    NULL                        COMMENT '产品型号',
    `batch_code`    VARCHAR(50)     NULL                        COMMENT '批次号',
    `assigned_to`   BIGINT          NULL                        COMMENT '指派处理人ID',
    `completed_at`  DATETIME        NULL                        COMMENT '完成时间',
    `completed_by`  BIGINT          NULL                        COMMENT '完成人ID',
    `remark`        TEXT            NULL                        COMMENT '备注',
    `created_at`    DATETIME        DEFAULT CURRENT_TIMESTAMP   COMMENT '创建时间',
    `updated_at`    DATETIME        DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_order_no` (`order_no`),
    KEY `idx_order_no` (`order_no`),
    KEY `idx_order_type` (`order_type`),
    KEY `idx_so_ticket_id` (`ticket_id`),
    KEY `idx_so_status` (`status`),
    KEY `idx_so_department` (`department`),
    KEY `idx_so_created_at` (`created_at`),
    KEY `idx_so_model_number` (`model_number`),
    KEY `idx_so_batch_code` (`batch_code`),
    CONSTRAINT `fk_so_ticket_id` FOREIGN KEY (`ticket_id`) REFERENCES `tickets` (`ticket_id`) ON DELETE CASCADE,
    CONSTRAINT `fk_so_assigned_to` FOREIGN KEY (`assigned_to`) REFERENCES `users` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_so_completed_by` FOREIGN KEY (`completed_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='服务工单表';


-- ------------------------------------------------------------
-- 2. 创建 quality_trace_index 表（质量追溯索引）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `quality_trace_index` (
    `id`                BIGINT          NOT NULL AUTO_INCREMENT,
    `ticket_id`         VARCHAR(50)     NOT NULL                    COMMENT '关联工单ID',
    `order_id`          BIGINT          NULL                        COMMENT '关联服务工单ID',
    `model_number`      VARCHAR(100)    NULL                       COMMENT '产品型号',
    `batch_code`        VARCHAR(50)     NULL                       COMMENT '批次号',
    `issue_category`    VARCHAR(100)    NULL                       COMMENT '问题分类',
    `urgency_level`     VARCHAR(50)     NULL                       COMMENT '紧急程度',
    `order_type`        VARCHAR(30)     NULL                       COMMENT '工单类型',
    `warranty_status`   VARCHAR(50)     NULL                       COMMENT '质保状态',
    `resolution_days`   DECIMAL(10,2)   NULL                       COMMENT '解决天数',
    `satisfaction_rating` SMALLINT      NULL                       COMMENT '满意度评分(预留)',
    `trace_date`        DATE            NOT NULL                   COMMENT '追溯日期',
    `created_at`        DATETIME        DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_qti_ticket_id` (`ticket_id`),
    KEY `idx_qti_model_number` (`model_number`),
    KEY `idx_qti_batch_code` (`batch_code`),
    KEY `idx_qti_issue_category` (`issue_category`),
    KEY `idx_qti_trace_date` (`trace_date`),
    KEY `idx_qti_model_batch` (`model_number`, `batch_code`),
    KEY `idx_qti_model_date` (`model_number`, `trace_date`),
    CONSTRAINT `fk_qti_ticket_id` FOREIGN KEY (`ticket_id`) REFERENCES `tickets` (`ticket_id`) ON DELETE CASCADE,
    CONSTRAINT `fk_qti_order_id` FOREIGN KEY (`order_id`) REFERENCES `service_orders` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='质量追溯索引表';


-- ------------------------------------------------------------
-- 3. 创建 order_mapping_rules 表（出单映射规则）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `order_mapping_rules` (
    `id`              BIGINT          NOT NULL AUTO_INCREMENT,
    `issue_category`  VARCHAR(100)    NOT NULL                    COMMENT '问题分类',
    `urgency_level`   VARCHAR(50)     NOT NULL                    COMMENT '紧急程度',
    `order_type`      VARCHAR(30)     NOT NULL                    COMMENT '映射工单类型',
    `department`      VARCHAR(100)    NOT NULL                    COMMENT '责任部门',
    `sla_hours`       INT             NOT NULL DEFAULT 48         COMMENT 'SLA时限(小时)',
    `is_active`       SMALLINT        NOT NULL DEFAULT 1          COMMENT '是否启用 1=是 0=否',
    `priority`        INT             NOT NULL DEFAULT 0          COMMENT '优先级(数值越大越优先)',
    `description`     VARCHAR(500)    NULL                        COMMENT '规则描述',
    `created_at`      DATETIME        DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',
    `updated_at`      DATETIME        DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_omr_issue_category` (`issue_category`),
    KEY `idx_omr_urgency_level` (`urgency_level`),
    KEY `idx_omr_is_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='出单映射规则表';


-- ------------------------------------------------------------
-- 4. 修改 tickets 表 - 新增 order_status 字段
-- ------------------------------------------------------------
ALTER TABLE `tickets` ADD COLUMN `order_status` VARCHAR(30) DEFAULT 'none' COMMENT '出单状态: none/pending_manual/ordered' AFTER `updated_at`;


-- ------------------------------------------------------------
-- 5. 插入 order_mapping_rules 初始数据（27条规则）
-- ------------------------------------------------------------

-- Missing_Parts -> Replacement (补发单, 售后服务部)
INSERT INTO `order_mapping_rules` (`issue_category`, `urgency_level`, `order_type`, `department`, `sla_hours`, `priority`, `description`) VALUES
('Missing_Parts',      'Low_Priority',    'Replacement',     '售后服务部', 72, 10, '缺件-低优先级-补发单'),
('Missing_Parts',      'Medium_Priority', 'Replacement',     '售后服务部', 48, 20, '缺件-中优先级-补发单'),
('Missing_Parts',      'High_Priority',   'Replacement',     '售后服务部', 24, 30, '缺件-高优先级-补发单');

-- Operation_Error -> Tech_Support (技术支援单, 技术支持部)
INSERT INTO `order_mapping_rules` (`issue_category`, `urgency_level`, `order_type`, `department`, `sla_hours`, `priority`, `description`) VALUES
('Operation_Error',    'Low_Priority',    'Tech_Support',   '技术支持部', 72, 10, '操作失误-低优先级-技术支援单'),
('Operation_Error',    'Medium_Priority', 'Tech_Support',   '技术支持部', 48, 20, '操作失误-中优先级-技术支援单'),
('Operation_Error',    'High_Priority',   'Tech_Support',   '技术支持部', 24, 30, '操作失误-高优先级-技术支援单');

-- Software_Bug -> Tech_Support (技术支援单, 技术支持部)
INSERT INTO `order_mapping_rules` (`issue_category`, `urgency_level`, `order_type`, `department`, `sla_hours`, `priority`, `description`) VALUES
('Software_Bug',       'Low_Priority',    'Tech_Support',   '技术支持部', 72, 10, '软件缺陷-低优先级-技术支援单'),
('Software_Bug',       'Medium_Priority', 'Tech_Support',   '技术支持部', 48, 20, '软件缺陷-中优先级-技术支援单'),
('Software_Bug',       'High_Priority',   'Tech_Support',   '技术支持部', 24, 30, '软件缺陷-高优先级-技术支援单');

-- Hardware_Malfunction -> Repair (维修单, 技术维修部)
INSERT INTO `order_mapping_rules` (`issue_category`, `urgency_level`, `order_type`, `department`, `sla_hours`, `priority`, `description`) VALUES
('Hardware_Malfunction', 'Low_Priority',    'Repair',         '技术维修部', 120, 10, '硬件故障-低优先级-维修单'),
('Hardware_Malfunction', 'Medium_Priority',  'Repair',         '技术维修部', 72,  20, '硬件故障-中优先级-维修单'),
('Hardware_Malfunction', 'High_Priority',    'Repair',         '技术维修部', 24,  30, '硬件故障-高优先级-维修单');

-- Hardware_Thermal_Runaway -> Repair (维修单, 技术维修部)
INSERT INTO `order_mapping_rules` (`issue_category`, `urgency_level`, `order_type`, `department`, `sla_hours`, `priority`, `description`) VALUES
('Hardware_Thermal_Runaway', 'Low_Priority',    'Repair',       '技术维修部', 72,  10, '热失控-低优先级-维修单'),
('Hardware_Thermal_Runaway', 'Medium_Priority',  'Repair',       '技术维修部', 24,  20, '热失控-中优先级-维修单'),
('Hardware_Thermal_Runaway', 'High_Priority',    'Repair',       '技术维修部', 4,   30, '热失控-高优先级-维修单');

-- Electrical_Leakage -> Repair (维修单, 技术维修部)
INSERT INTO `order_mapping_rules` (`issue_category`, `urgency_level`, `order_type`, `department`, `sla_hours`, `priority`, `description`) VALUES
('Electrical_Leakage', 'Low_Priority',    'Repair',           '技术维修部', 72,  10, '漏电-低优先级-维修单'),
('Electrical_Leakage', 'Medium_Priority', 'Repair',           '技术维修部', 24,  20, '漏电-中优先级-维修单'),
('Electrical_Leakage', 'High_Priority',   'Repair',           '技术维修部', 4,   30, '漏电-高优先级-维修单');

-- Batch_Defect -> Return_Exchange (退换单, 售后服务部)
INSERT INTO `order_mapping_rules` (`issue_category`, `urgency_level`, `order_type`, `department`, `sla_hours`, `priority`, `description`) VALUES
('Batch_Defect',       'Medium_Priority', 'Return_Exchange', '售后服务部', 48, 20, '批次缺陷-中优先级-退换单'),
('Batch_Defect',       'High_Priority',   'Return_Exchange', '售后服务部', 24, 30, '批次缺陷-高优先级-退换单');

-- Safety_Hazard -> Return_Exchange (退换单, 售后服务部)
INSERT INTO `order_mapping_rules` (`issue_category`, `urgency_level`, `order_type`, `department`, `sla_hours`, `priority`, `description`) VALUES
('Safety_Hazard',      'Low_Priority',    'Return_Exchange', '售后服务部', 48, 10, '安全隐患-低优先级-退换单'),
('Safety_Hazard',      'Medium_Priority', 'Return_Exchange', '售后服务部', 24, 20, '安全隐患-中优先级-退换单'),
('Safety_Hazard',      'High_Priority',   'Return_Exchange', '售后服务部', 4,  30, '安全隐患-高优先级-退换单');

-- Batch_Defect -> QC (质检单, 质量管理部)
INSERT INTO `order_mapping_rules` (`issue_category`, `urgency_level`, `order_type`, `department`, `sla_hours`, `priority`, `description`) VALUES
('Batch_Defect',       'Medium_Priority', 'QC',              '质量管理部', 48, 15, '批次缺陷-中优先级-质检单'),
('Batch_Defect',       'High_Priority',   'QC',              '质量管理部', 24, 25, '批次缺陷-高优先级-质检单');

-- Safety_Hazard -> QC (质检单, 质量管理部)
INSERT INTO `order_mapping_rules` (`issue_category`, `urgency_level`, `order_type`, `department`, `sla_hours`, `priority`, `description`) VALUES
('Safety_Hazard',      'Low_Priority',    'QC',              '质量管理部', 48, 5,  '安全隐患-低优先级-质检单'),
('Safety_Hazard',      'Medium_Priority', 'QC',              '质量管理部', 24, 15, '安全隐患-中优先级-质检单'),
('Safety_Hazard',      'High_Priority',   'QC',              '质量管理部', 4,  25, '安全隐患-高优先级-质检单');


-- ------------------------------------------------------------
-- 6. 历史数据回填 quality_trace_index
--    从已有 tickets 表中提取数据，写入质量追溯索引
-- ------------------------------------------------------------
INSERT INTO `quality_trace_index` (`ticket_id`, `order_id`, `model_number`, `batch_code`, `issue_category`, `urgency_level`, `order_type`, `warranty_status`, `trace_date`, `created_at`)
SELECT
    t.ticket_id,
    NULL AS order_id,
    JSON_UNQUOTE(JSON_EXTRACT(t.extracted_data, '$.model_number')) AS model_number,
    JSON_UNQUOTE(JSON_EXTRACT(t.extracted_data, '$.batch_code')) AS batch_code,
    t.issue_category,
    t.urgency_level,
    NULL AS order_type,
    t.warranty_status,
    DATE(t.created_at) AS trace_date,
    t.created_at
FROM `tickets` t
WHERE t.issue_category IS NOT NULL
  AND t.urgency_level IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM `quality_trace_index` qti WHERE qti.ticket_id = t.ticket_id
  );
