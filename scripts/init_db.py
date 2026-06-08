import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiomysql
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", ".env"))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "complaint_agent")
DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")


async def create_database():
    conn = await aiomysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, charset=DB_CHARSET
    )
    async with conn.cursor() as cur:
        await cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET {DB_CHARSET} COLLATE {DB_CHARSET}_unicode_ci"
        )
    await conn.commit()
    conn.close()
    print(f"数据库 {DB_NAME} 创建成功")


async def create_tables():
    conn = await aiomysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        db=DB_NAME, charset=DB_CHARSET
    )

    tables = [
        """
        CREATE TABLE IF NOT EXISTS `users` (
            `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
            `username` VARCHAR(100) NOT NULL UNIQUE,
            `password_hash` VARCHAR(255) NOT NULL,
            `role` ENUM('admin','frontline_staff','department_manager','general_manager') NOT NULL DEFAULT 'frontline_staff',
            `department` VARCHAR(100) NULL,
            `is_active` TINYINT(1) DEFAULT 1,
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX `idx_username` (`username`),
            INDEX `idx_role` (`role`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS `tickets` (
            `ticket_id` VARCHAR(50) PRIMARY KEY,
            `customer_name` VARCHAR(100) NULL,
            `customer_phone` VARCHAR(20) NULL,
            `raw_input` TEXT NOT NULL,
            `extracted_data` JSON NULL,
            `agent_business_assessment` JSON NULL,
            `urgency_level` VARCHAR(50) NULL,
            `issue_category` VARCHAR(100) NULL,
            `warranty_status` VARCHAR(50) NULL,
            `routing_decision` VARCHAR(100) NULL,
            `auto_reply_sent` TEXT NULL,
            `sop_applied` VARCHAR(200) NULL,
            `status` ENUM('pending','processing','routed','resolved','closed','cancelled') DEFAULT 'pending',
            `assigned_to` BIGINT NULL,
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            `resolved_at` DATETIME NULL,
            `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX `idx_status` (`status`),
            INDEX `idx_urgency_level` (`urgency_level`),
            INDEX `idx_issue_category` (`issue_category`),
            INDEX `idx_created_at` (`created_at`),
            INDEX `idx_routing_decision` (`routing_decision`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS `evidence_files` (
            `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
            `ticket_id` VARCHAR(50) NOT NULL,
            `file_path` VARCHAR(500) NOT NULL,
            `thumbnail_path` VARCHAR(500) NULL,
            `file_type` ENUM('image','video','document') NOT NULL,
            `file_size` BIGINT NULL,
            `uploaded_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX `idx_ticket_id` (`ticket_id`),
            CONSTRAINT `fk_evidence_ticket` FOREIGN KEY (`ticket_id`) REFERENCES `tickets`(`ticket_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS `sop_knowledge_base` (
            `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
            `issue_category` VARCHAR(100) NOT NULL,
            `title` VARCHAR(200) NOT NULL,
            `content` TEXT NOT NULL,
            `urgency_level` VARCHAR(50) NULL,
            `keywords` JSON NULL,
            `is_active` TINYINT(1) DEFAULT 1,
            `version` INT DEFAULT 1,
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX `idx_issue_category` (`issue_category`),
            INDEX `idx_urgency_level` (`urgency_level`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS `warranty_records` (
            `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
            `sn_code` VARCHAR(100) NOT NULL UNIQUE,
            `model_number` VARCHAR(100) NOT NULL,
            `batch_code` VARCHAR(50) NULL,
            `warranty_start` DATE NOT NULL,
            `warranty_end` DATE NOT NULL,
            `customer_name` VARCHAR(100) NULL,
            `order_id` VARCHAR(100) NULL,
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX `idx_sn_code` (`sn_code`),
            INDEX `idx_model_number` (`model_number`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS `routing_rules` (
            `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
            `urgency_level` VARCHAR(50) NOT NULL,
            `target_role` VARCHAR(100) NOT NULL,
            `target_department` VARCHAR(100) NOT NULL,
            `sla_hours` INT NOT NULL DEFAULT 24,
            `description` VARCHAR(500) NULL,
            `is_active` TINYINT(1) DEFAULT 1,
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX `idx_urgency_level` (`urgency_level`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS `notifications` (
            `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
            `ticket_id` VARCHAR(50) NOT NULL,
            `target_user_id` BIGINT NOT NULL,
            `type` ENUM('new_ticket','escalation','sla_warning','reassign') NOT NULL,
            `content` TEXT NULL,
            `is_read` TINYINT(1) DEFAULT 0,
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX `idx_ticket_id` (`ticket_id`),
            INDEX `idx_target_user_id` (`target_user_id`),
            INDEX `idx_is_read` (`is_read`),
            CONSTRAINT `fk_notification_ticket` FOREIGN KEY (`ticket_id`) REFERENCES `tickets`(`ticket_id`),
            CONSTRAINT `fk_notification_user` FOREIGN KEY (`target_user_id`) REFERENCES `users`(`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS `escalation_rules` (
            `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
            `from_level` VARCHAR(50) NOT NULL,
            `to_level` VARCHAR(50) NOT NULL,
            `trigger_condition` VARCHAR(200) NULL,
            `auto_escalate_hours` INT NULL,
            INDEX `idx_from_level` (`from_level`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS `ticket_logs` (
            `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
            `ticket_id` VARCHAR(50) NOT NULL,
            `action` ENUM('status_change','escalation','reassign','note') NOT NULL,
            `operator_id` BIGINT NULL,
            `detail` TEXT NULL,
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX `idx_ticket_id` (`ticket_id`),
            INDEX `idx_created_at` (`created_at`),
            CONSTRAINT `fk_log_ticket` FOREIGN KEY (`ticket_id`) REFERENCES `tickets`(`ticket_id`),
            CONSTRAINT `fk_log_operator` FOREIGN KEY (`operator_id`) REFERENCES `users`(`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    ]

    async with conn.cursor() as cur:
        for i, sql in enumerate(tables):
            await cur.execute(sql)
            print(f"  表 {i + 1}/9 创建成功")

    await conn.commit()
    conn.close()
    print("全部9张表创建成功")


async def main():
    print("=" * 50)
    print("客诉自动回复出单智能体 - 数据库初始化")
    print("=" * 50)
    print(f"MySQL: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print()

    print("[1/2] 创建数据库...")
    await create_database()

    print("[2/2] 创建数据表...")
    await create_tables()

    print()
    print("初始化完成！请继续运行 seed_data.py 插入种子数据")


if __name__ == "__main__":
    asyncio.run(main())
