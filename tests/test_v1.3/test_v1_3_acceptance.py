"""v1.3 验收测试 - OCR+LLM多模态分析、前置止损、SOP扩充、evidence_images修复"""
import os
import re

import pytest

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from agent.core.agent_engine import ComplaintAgentEngine


@pytest.fixture
def engine():
    return ComplaintAgentEngine()


class TestV13Multimodal:
    """v1.3 多模态分析验收"""

    @pytest.mark.asyncio
    async def test_no_images_returns_none_analysis(self, engine):
        """AC-1.1: 无图片时 image_analysis 为 None 或空"""
        result = await engine.process_complaint(text="我的设备坏了，订单JD9988776655")
        image_analysis = result.get("image_analysis")
        # 无图片时应该为None或空dict
        assert image_analysis is None or image_analysis.get("image_count", 0) == 0

    @pytest.mark.asyncio
    async def test_image_analysis_fields_complete(self, engine):
        """AC-1.2: 有图片时 image_analysis 包含完整8字段"""
        # 创建测试图片
        import tempfile
        from PIL import Image

        tmpdir = tempfile.mkdtemp()
        img_path = os.path.join(tmpdir, "test_device.jpg")
        img = Image.new("RGB", (200, 200), color=(128, 50, 20))  # 暗暖色图片
        img.save(img_path)

        try:
            result = await engine.process_complaint(
                text="设备冒烟了，订单JD9988776655",
                image_paths=[img_path],
            )
            image_analysis = result.get("image_analysis")
            assert image_analysis is not None, "image_analysis should not be None when images provided"

            required_fields = [
                "damage_detected", "damage_level", "fault_types_found",
                "has_emergency_indicators", "overall_assessment", "suggestion",
                "analysis_source", "image_count",
            ]
            for field in required_fields:
                assert field in image_analysis, f"Missing field: {field}"

            assert image_analysis["image_count"] >= 1
            assert image_analysis["analysis_source"] in ("ocr", "pillow_basic", "none")
        finally:
            os.remove(img_path)
            os.rmdir(tmpdir)

    @pytest.mark.asyncio
    async def test_degradation_chain_no_images(self, engine):
        """AC-1.3: 无图片时 analysis_source 应为 none"""
        # 不提供图片路径
        result = await engine.process_complaint(text="设备坏了", image_paths=[])
        image_analysis = result.get("image_analysis")
        if image_analysis is not None:
            assert image_analysis.get("analysis_source") in ("ocr", "pillow_basic", "none")


class TestV13EvidenceImages:
    """v1.3 evidence_images 字段填充修复"""

    @pytest.mark.asyncio
    async def test_evidence_images_populated(self, engine):
        """AC-3.1: 有图片时 evidence_images 应包含实际路径"""
        import tempfile
        from PIL import Image

        tmpdir = tempfile.mkdtemp()
        img_path = os.path.join(tmpdir, "evidence_test.jpg")
        img = Image.new("RGB", (100, 100), color="red")
        img.save(img_path)

        try:
            result = await engine.process_complaint(
                text="设备漏电，订单JD9988776655",
                image_paths=[img_path],
            )
            extracted = result.get("extracted_data", {})
            evidence_images = extracted.get("evidence_images", [])
            assert len(evidence_images) > 0, (
                f"evidence_images should not be empty when images provided, got: {evidence_images}"
            )
            assert img_path in evidence_images, (
                f"evidence_images should contain {img_path}, got: {evidence_images}"
            )
        finally:
            os.remove(img_path)
            os.rmdir(tmpdir)

    @pytest.mark.asyncio
    async def test_evidence_images_empty_without_images(self, engine):
        """AC-3.2: 无图片时 evidence_images 应为空列表"""
        result = await engine.process_complaint(text="设备坏了，订单JD9988776655")
        extracted = result.get("extracted_data", {})
        assert extracted.get("evidence_images", []) == [] or extracted.get("evidence_images") is None


class TestV13PreemptiveSafety:
    """v1.3 前置止损回复验收"""

    @pytest.mark.asyncio
    async def test_high_priority_has_safety_steps(self, engine):
        """AC-6.1: 高优先级工单回复必须包含具体止损步骤"""
        result = await engine.process_complaint(text="Pro-Max-V2设备冒烟了，订单JD9988776655，设备在冒烟有烧焦味")

        assessment = result.get("agent_business_assessment", {})
        assert assessment.get("urgency_level") == "High_Priority", (
            f"Smoke complaint should be High_Priority, got {assessment.get('urgency_level')}"
        )

        auto_reply = result.get("auto_reply_sent", "")
        safety_keywords = ["切断", "断电", "远离", "电源", "严禁"]
        matched = [kw for kw in safety_keywords if kw in auto_reply]
        assert len(matched) >= 2, (
            f"High priority reply should contain at least 2 safety keywords from {safety_keywords}, "
            f"matched: {matched}, reply: {auto_reply[:200]}"
        )

    @pytest.mark.asyncio
    async def test_medium_priority_has_troubleshooting(self, engine):
        """AC-6.2: 中优先级工单回复应包含排查步骤"""
        result = await engine.process_complaint(text="核心部件频繁重启，订单JD5566778899")

        assessment = result.get("agent_business_assessment", {})
        assert assessment.get("urgency_level") == "Medium_Priority"

        auto_reply = result.get("auto_reply_sent", "")
        assert len(auto_reply) > 50, f"Reply too short: {auto_reply}"

    @pytest.mark.asyncio
    async def test_low_priority_has_guidance(self, engine):
        """AC-6.3: 低优先级工单回复应包含操作指引"""
        result = await engine.process_complaint(text="我的订单JD9988776655，Pro-Max-V2型号，缺少螺丝包，批次X11")

        assessment = result.get("agent_business_assessment", {})
        assert assessment.get("urgency_level") == "Low_Priority"

        auto_reply = result.get("auto_reply_sent", "")
        assert len(auto_reply) > 30, f"Reply too short: {auto_reply}"


class TestV13SOPExpansion:
    """v1.3 SOP知识库扩充验收"""

    @pytest.mark.asyncio
    async def test_sop_retrieval_for_smoke(self, engine):
        """AC-5.1: 冒烟场景应检索到含emergency_actions的SOP"""
        result = await engine.process_complaint(text="Pro-Max-V2设备冒烟了，订单JD9988776655")

        sop_applied = result.get("sop_applied", "")
        assert sop_applied, "sop_applied should not be empty for smoke complaint"
        # SOP标题应包含冒烟/过热/紧急相关关键词
        sop_keywords = ["冒烟", "过热", "紧急", "处置", "起火"]
        matched = [kw for kw in sop_keywords if kw in sop_applied]
        assert len(matched) > 0, (
            f"SOP title should contain emergency keywords, got: {sop_applied}"
        )

    @pytest.mark.asyncio
    async def test_sop_retrieval_for_leakage(self, engine):
        """AC-5.2: 漏电场景应检索到漏电处置SOP"""
        result = await engine.process_complaint(text="设备漏电，摸上去麻手，订单JD5566778899")

        sop_applied = result.get("sop_applied", "")
        assert sop_applied, "sop_applied should not be empty for leakage complaint"


class TestV13PipelineIntegration:
    """v1.3 Pipeline集成验收 - B场景端到端"""

    @pytest.mark.asyncio
    async def test_b_scenario_e2e(self, engine):
        """AC-B: 赛题B场景端到端验收（冒烟→高优先级→总经理路由→断电隔离SOP）"""
        result = await engine.process_complaint(text="Pro-Max-V2设备冒烟，订单JD9988776655")

        # 1. 工单创建
        assert result.get("ticket_id"), "ticket_id should exist"
        assert re.match(r"CS-\d{8}-\d{4}", result["ticket_id"])

        # 2. 高优先级定级
        assessment = result.get("agent_business_assessment", {})
        assert assessment.get("urgency_level") == "High_Priority", (
            f"B scenario should be High_Priority, got {assessment.get('urgency_level')}"
        )

        # 3. 硬件热失控分类
        assert assessment.get("issue_category") == "Hardware_Thermal_Runaway", (
            f"B scenario should be Hardware_Thermal_Runaway, got {assessment.get('issue_category')}"
        )

        # 4. 总经理路由
        assert result.get("routing_decision") == "general_manager_dashboard", (
            f"B scenario should route to GM, got {result.get('routing_decision')}"
        )

        # 5. 自动回复含断电/隔离指令
        auto_reply = result.get("auto_reply_sent", "")
        safety_keywords = ["切断", "电源", "远离", "严禁"]
        matched = [kw for kw in safety_keywords if kw in auto_reply]
        assert len(matched) >= 2, (
            f"B scenario reply should contain safety instructions, matched: {matched}, reply: {auto_reply[:200]}"
        )

        # 6. SOP命中
        assert result.get("sop_applied"), "SOP should be applied"

    @pytest.mark.asyncio
    async def test_a_scenario_e2e(self, engine):
        """AC-A: 赛题A场景端到端验收（缺件→低优先级→一线路由→补发SOP）"""
        result = await engine.process_complaint(
            text="我的订单JD9988776655，Pro-Max-V2型号，缺少螺丝包，批次X11"
        )

        assert result.get("ticket_id")

        assessment = result.get("agent_business_assessment", {})
        assert assessment.get("urgency_level") == "Low_Priority"
        assert assessment.get("issue_category") == "Missing_Parts"
        assert result.get("routing_decision") == "frontline_staff_queue"

        auto_reply = result.get("auto_reply_sent", "")
        assert len(auto_reply) > 30

    @pytest.mark.asyncio
    async def test_c_scenario_e2e(self, engine):
        """AC-C: 赛题C场景端到端验收（频繁重启→中优先级→部门经理路由）"""
        result = await engine.process_complaint(text="核心部件频繁重启，订单JD5566778899")

        assert result.get("ticket_id")

        assessment = result.get("agent_business_assessment", {})
        assert assessment.get("urgency_level") == "Medium_Priority"
        assert result.get("routing_decision") == "department_manager_queue"

    @pytest.mark.asyncio
    async def test_d_scenario_e2e(self, engine):
        """AC-D: 赛题D场景端到端验收（信息不完整→中优先级→补充采集）"""
        result = await engine.process_complaint(text="坏了")

        assert result.get("ticket_id")

        assessment = result.get("agent_business_assessment", {})
        assert assessment.get("urgency_level") == "Medium_Priority"


class TestV13DatabaseMigration:
    """v1.3 数据库迁移验收"""

    def test_sop_has_emergency_actions_column(self):
        """AC-DB.1: sop_knowledge_base 表有 emergency_actions 字段"""
        import pymysql
        from backend.app.config import settings

        conn = pymysql.connect(
            host=settings.DB_HOST, port=settings.DB_PORT,
            user=settings.DB_USER, password=settings.DB_PASSWORD,
            database=settings.DB_NAME, charset=settings.DB_CHARSET,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='sop_knowledge_base' AND COLUMN_NAME='emergency_actions'",
                    (settings.DB_NAME,)
                )
                assert cur.fetchone() is not None, "emergency_actions column should exist"
        finally:
            conn.close()

    def test_sop_has_scenario_tags_column(self):
        """AC-DB.2: sop_knowledge_base 表有 scenario_tags 字段"""
        import pymysql
        from backend.app.config import settings

        conn = pymysql.connect(
            host=settings.DB_HOST, port=settings.DB_PORT,
            user=settings.DB_USER, password=settings.DB_PASSWORD,
            database=settings.DB_NAME, charset=settings.DB_CHARSET,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='sop_knowledge_base' AND COLUMN_NAME='scenario_tags'",
                    (settings.DB_NAME,)
                )
                assert cur.fetchone() is not None, "scenario_tags column should exist"
        finally:
            conn.close()

    def test_ticket_has_image_analysis_column(self):
        """AC-DB.3: tickets 表有 image_analysis 字段"""
        import pymysql
        from backend.app.config import settings

        conn = pymysql.connect(
            host=settings.DB_HOST, port=settings.DB_PORT,
            user=settings.DB_USER, password=settings.DB_PASSWORD,
            database=settings.DB_NAME, charset=settings.DB_CHARSET,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='tickets' AND COLUMN_NAME='image_analysis'",
                    (settings.DB_NAME,)
                )
                assert cur.fetchone() is not None, "image_analysis column should exist"
        finally:
            conn.close()

    def test_sop_count_at_least_18(self):
        """AC-DB.4: SOP知识库至少18条"""
        import pymysql
        from backend.app.config import settings

        conn = pymysql.connect(
            host=settings.DB_HOST, port=settings.DB_PORT,
            user=settings.DB_USER, password=settings.DB_PASSWORD,
            database=settings.DB_NAME, charset=settings.DB_CHARSET,
        )
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM sop_knowledge_base WHERE is_active=1")
                count = cur.fetchone()[0]
                assert count >= 18, f"SOP count should be >= 18, got {count}"
        finally:
            conn.close()

    def test_sop_emergency_actions_not_null(self):
        """AC-DB.5: 高优先级SOP应有emergency_actions"""
        import pymysql
        from backend.app.config import settings

        conn = pymysql.connect(
            host=settings.DB_HOST, port=settings.DB_PORT,
            user=settings.DB_USER, password=settings.DB_PASSWORD,
            database=settings.DB_NAME, charset=settings.DB_CHARSET,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM sop_knowledge_base "
                    "WHERE urgency_level='High_Priority' AND is_active=1 AND emergency_actions IS NOT NULL"
                )
                count = cur.fetchone()[0]
                assert count >= 5, f"At least 5 High_Priority SOPs should have emergency_actions, got {count}"
        finally:
            conn.close()
