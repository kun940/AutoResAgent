-- ============================================================
-- 迁移脚本 v1.2 - 删除出单模块，强化归档与质量追溯
-- 基线版本: v1.1
-- 变更内容:
--   1. 备份出单历史数据（service_orders / order_mapping_rules）
--   2. 改造 quality_trace_index 表（解除出单外键，新增归档完整性字段）
--   3. 删除 tickets.order_status 字段
--   4. 删除 service_orders / order_mapping_rules 表
--   5. 历史质量追溯数据回填
-- ============================================================

-- ------------------------------------------------------------
-- 1. 备份出单历史数据（保留审计痕迹，不再参与业务流转）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `service_orders_archive_v1_1` AS
SELECT * FROM `service_orders`;

CREATE TABLE IF NOT EXISTS `order_mapping_rules_archive_v1_1` AS
SELECT * FROM `order_mapping_rules`;


-- ------------------------------------------------------------
-- 2. 改造 quality_trace_index 表
-- ------------------------------------------------------------

-- 2.1 解除对 service_orders 的外键依赖
ALTER TABLE `quality_trace_index` DROP FOREIGN KEY `fk_qti_order_id`;

-- 2.2 order_type 字段语义变更为「处理动作类型」
--     v1.2: Auto_Reply/Routed/Manual_Resolved/Escalated
--     v1.1 历史数据保留原出单类型（Replacement/Repair 等）
ALTER TABLE `quality_trace_index`
  MODIFY COLUMN `order_type` VARCHAR(30) NULL
  COMMENT '处理动作类型(v1.2): Auto_Reply/Routed/Manual_Resolved/Escalated；v1.1历史数据保留原出单类型';

-- 2.3 新增归档完整性标记字段
ALTER TABLE `quality_trace_index`
  ADD COLUMN `archive_complete` TINYINT NOT NULL DEFAULT 1
  COMMENT '归档完整性: 1=完整(含证据+研判+回复) 0=部分缺失'
  AFTER `satisfaction_rating`;


-- ------------------------------------------------------------
-- 3. 删除 tickets.order_status 字段
-- ------------------------------------------------------------
ALTER TABLE `tickets` DROP COLUMN `order_status`;


-- ------------------------------------------------------------
-- 4. 删除出单相关表
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `order_mapping_rules`;
DROP TABLE IF EXISTS `service_orders`;


-- ------------------------------------------------------------
-- 5. 历史质量追溯数据回填（基于工单归档）
--    对未写入追溯索引的工单进行回填
-- ------------------------------------------------------------
INSERT INTO `quality_trace_index` (
  `ticket_id`, `order_id`, `model_number`, `batch_code`,
  `issue_category`, `urgency_level`, `order_type`, `warranty_status`,
  `trace_date`, `created_at`, `archive_complete`
)
SELECT
  t.ticket_id,
  NULL AS order_id,
  JSON_UNQUOTE(JSON_EXTRACT(t.extracted_data, '$.model_number')) AS model_number,
  JSON_UNQUOTE(JSON_EXTRACT(t.extracted_data, '$.batch_code')) AS batch_code,
  t.issue_category,
  t.urgency_level,
  CASE
    WHEN t.status = 'resolved' OR t.status = 'closed' THEN 'Manual_Resolved'
    ELSE 'Auto_Reply'
  END AS order_type,
  t.warranty_status,
  DATE(t.created_at) AS trace_date,
  t.created_at,
  CASE
    WHEN t.raw_input IS NOT NULL
     AND t.extracted_data IS NOT NULL
     AND t.agent_business_assessment IS NOT NULL
     AND t.auto_reply_sent IS NOT NULL
    THEN 1 ELSE 0
  END AS archive_complete
FROM `tickets` t
WHERE t.issue_category IS NOT NULL
  AND t.urgency_level IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM `quality_trace_index` qti WHERE qti.ticket_id = t.ticket_id
  );
