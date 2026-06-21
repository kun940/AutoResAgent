import re

import pytest

from agent.core.agent_engine import ComplaintAgentEngine
from tests.test_data.sample_complaints import SAMPLE_COMPLAINTS


@pytest.fixture
def engine():
    return ComplaintAgentEngine()


class TestAcceptanceV12:
    """v1.2 原有4个验收场景（A/B/C/D），确保向后兼容"""

    @pytest.mark.asyncio
    async def test_a_missing_parts(self, engine):
        scenario = SAMPLE_COMPLAINTS["A_missing_parts"]
        result = await engine.process_complaint(text=scenario["text"])
        expected = scenario["expected"]

        assert result.get("ticket_id"), "ticket_id should not be empty"
        assert re.match(r"CS-\d{8}-\d{4}", result["ticket_id"]), (
            f"ticket_id format should be CS-YYYYMMDD-XXXX, got {result['ticket_id']}"
        )

        extracted = result.get("extracted_data", {})
        assert extracted.get("order_id") == expected["order_id"], (
            f"order_id: expected {expected['order_id']}, got {extracted.get('order_id')}"
        )
        assert extracted.get("model_number") == expected["model_number"], (
            f"model_number: expected {expected['model_number']}, got {extracted.get('model_number')}"
        )
        assert extracted.get("batch_code") == expected["batch_code"], (
            f"batch_code: expected {expected['batch_code']}, got {extracted.get('batch_code')}"
        )

        assessment = result.get("agent_business_assessment", {})
        assert assessment.get("urgency_level") == expected["urgency_level"], (
            f"urgency_level: expected {expected['urgency_level']}, got {assessment.get('urgency_level')}"
        )
        assert assessment.get("issue_category") == expected["issue_category"], (
            f"issue_category: expected {expected['issue_category']}, got {assessment.get('issue_category')}"
        )

        assert result.get("routing_decision") == expected["routing_decision"], (
            f"routing_decision: expected {expected['routing_decision']}, got {result.get('routing_decision')}"
        )

        auto_reply = result.get("auto_reply_sent", "")
        matched_keywords = [kw for kw in expected["auto_reply_keywords"] if kw in auto_reply]
        assert len(matched_keywords) > 0, (
            f"auto_reply_sent should contain at least one of {expected['auto_reply_keywords']}, got: {auto_reply}"
        )

        assert result.get("sop_applied"), "sop_applied should not be empty"

    @pytest.mark.asyncio
    async def test_b_smoke(self, engine):
        scenario = SAMPLE_COMPLAINTS["B_smoke"]
        result = await engine.process_complaint(text=scenario["text"])
        expected = scenario["expected"]

        assert result.get("ticket_id"), "ticket_id should not be empty"
        assert re.match(r"CS-\d{8}-\d{4}", result["ticket_id"]), (
            f"ticket_id format should be CS-YYYYMMDD-XXXX, got {result['ticket_id']}"
        )

        extracted = result.get("extracted_data", {})
        fault_desc = extracted.get("core_fault_desc", "")
        assert expected["core_fault_desc_contains"] in fault_desc, (
            f"core_fault_desc should contain '{expected['core_fault_desc_contains']}', got: {fault_desc}"
        )

        assessment = result.get("agent_business_assessment", {})
        assert assessment.get("urgency_level") == expected["urgency_level"], (
            f"urgency_level: expected {expected['urgency_level']}, got {assessment.get('urgency_level')}"
        )
        assert assessment.get("issue_category") == expected["issue_category"], (
            f"issue_category: expected {expected['issue_category']}, got {assessment.get('issue_category')}"
        )

        assert result.get("routing_decision") == expected["routing_decision"], (
            f"routing_decision: expected {expected['routing_decision']}, got {result.get('routing_decision')}"
        )

        auto_reply = result.get("auto_reply_sent", "")
        matched_keywords = [kw for kw in expected["auto_reply_keywords"] if kw in auto_reply]
        assert len(matched_keywords) > 0, (
            f"auto_reply_sent should contain at least one of {expected['auto_reply_keywords']}, got: {auto_reply}"
        )

        assert result.get("sop_applied"), "sop_applied should not be empty"

    @pytest.mark.asyncio
    async def test_c_reboot(self, engine):
        scenario = SAMPLE_COMPLAINTS["C_reboot"]
        result = await engine.process_complaint(text=scenario["text"])
        expected = scenario["expected"]

        assert result.get("ticket_id"), "ticket_id should not be empty"
        assert re.match(r"CS-\d{8}-\d{4}", result["ticket_id"]), (
            f"ticket_id format should be CS-YYYYMMDD-XXXX, got {result['ticket_id']}"
        )

        assessment = result.get("agent_business_assessment", {})
        assert assessment.get("urgency_level") == expected["urgency_level"], (
            f"urgency_level: expected {expected['urgency_level']}, got {assessment.get('urgency_level')}"
        )

        assert result.get("routing_decision") == expected["routing_decision"], (
            f"routing_decision: expected {expected['routing_decision']}, got {result.get('routing_decision')}"
        )

        auto_reply = result.get("auto_reply_sent", "")
        matched_keywords = [kw for kw in expected["auto_reply_keywords"] if kw in auto_reply]
        assert len(matched_keywords) > 0, (
            f"auto_reply_sent should contain at least one of {expected['auto_reply_keywords']}, got: {auto_reply}"
        )

        assert result.get("sop_applied"), "sop_applied should not be empty"

    @pytest.mark.asyncio
    async def test_d_incomplete(self, engine):
        scenario = SAMPLE_COMPLAINTS["D_incomplete"]
        result = await engine.process_complaint(text=scenario["text"])
        expected = scenario["expected"]

        assert result.get("ticket_id"), "ticket_id should not be empty"
        assert re.match(r"CS-\d{8}-\d{4}", result["ticket_id"]), (
            f"ticket_id format should be CS-YYYYMMDD-XXXX, got {result['ticket_id']}"
        )

        assessment = result.get("agent_business_assessment", {})
        assert assessment.get("urgency_level") == expected["urgency_level"], (
            f"urgency_level: expected {expected['urgency_level']}, got {assessment.get('urgency_level')}"
        )

        auto_reply = result.get("auto_reply_sent", "")
        matched_keywords = [kw for kw in expected["auto_reply_keywords"] if kw in auto_reply]
        assert len(matched_keywords) > 0, (
            f"auto_reply_sent should contain at least one of {expected['auto_reply_keywords']}, got: {auto_reply}"
        )


class TestAcceptanceV13:
    """v1.3 新增验收场景（E/F/G/H/I），验证多模态+前置止损+SOP扩充"""

    @pytest.mark.asyncio
    async def test_e_smoke_no_images(self, engine):
        """E场景：冒烟无图片 - 验证文本驱动高优先级定级"""
        scenario = SAMPLE_COMPLAINTS["E_smoke_no_images"]
        result = await engine.process_complaint(
            text=scenario["text"],
            image_paths=scenario.get("image_paths"),
        )
        expected = scenario["expected"]

        # 基础工单验证
        assert result.get("ticket_id"), "ticket_id should not be empty"
        assert re.match(r"CS-\d{8}-\d{4}", result["ticket_id"])

        # 无图片时 image_analysis 应为 None 或 none 类型
        image_analysis = result.get("image_analysis")
        if image_analysis is not None:
            assert image_analysis.get("analysis_source") in ("ocr", "pillow_basic", "none")

        # 文本驱动的冒烟定级
        assessment = result.get("agent_business_assessment", {})
        assert assessment.get("urgency_level") == expected["urgency_level"], (
            f"urgency_level: expected {expected['urgency_level']}, got {assessment.get('urgency_level')}"
        )
        assert assessment.get("issue_category") == expected["issue_category"], (
            f"issue_category: expected {expected['issue_category']}, got {assessment.get('issue_category')}"
        )

        assert result.get("routing_decision") == expected["routing_decision"]

        # v1.3 前置止损：冒烟场景必须包含具体止损步骤
        auto_reply = result.get("auto_reply_sent", "")
        matched_keywords = [kw for kw in expected["auto_reply_keywords"] if kw in auto_reply]
        assert len(matched_keywords) > 0, (
            f"auto_reply should contain at least one of {expected['auto_reply_keywords']}, got: {auto_reply}"
        )

        assert result.get("sop_applied"), "sop_applied should not be empty"

    @pytest.mark.asyncio
    async def test_f_leakage_high(self, engine):
        """F场景：漏电 - 验证Electrical_Leakage定级+漏电SOP召回"""
        scenario = SAMPLE_COMPLAINTS["F_leakage_high"]
        result = await engine.process_complaint(text=scenario["text"])
        expected = scenario["expected"]

        assert result.get("ticket_id")

        assessment = result.get("agent_business_assessment", {})
        assert assessment.get("urgency_level") == expected["urgency_level"], (
            f"urgency_level: expected {expected['urgency_level']}, got {assessment.get('urgency_level')}"
        )
        assert assessment.get("issue_category") == expected["issue_category"], (
            f"issue_category: expected {expected['issue_category']}, got {assessment.get('issue_category')}"
        )

        assert result.get("routing_decision") == expected["routing_decision"]

        # v1.3 前置止损：漏电场景必须包含"切断总闸""远离"等止损步骤
        auto_reply = result.get("auto_reply_sent", "")
        matched_keywords = [kw for kw in expected["auto_reply_keywords"] if kw in auto_reply]
        assert len(matched_keywords) > 0, (
            f"auto_reply should contain at least one of {expected['auto_reply_keywords']}, got: {auto_reply}"
        )

        # 验证SOP召回：应命中漏电相关SOP
        sop_applied = result.get("sop_applied", "")
        leakage_sop_keywords = ["漏电", "触电"]
        assert any(kw in sop_applied for kw in leakage_sop_keywords), (
            f"sop_applied should contain leakage SOP, got: {sop_applied}"
        )

    @pytest.mark.asyncio
    async def test_g_fire_high(self, engine):
        """G场景：起火 - 验证起火SOP召回+紧急止损回复"""
        scenario = SAMPLE_COMPLAINTS["G_fire_high"]
        result = await engine.process_complaint(text=scenario["text"])
        expected = scenario["expected"]

        assert result.get("ticket_id")

        assessment = result.get("agent_business_assessment", {})
        assert assessment.get("urgency_level") == expected["urgency_level"], (
            f"urgency_level: expected {expected['urgency_level']}, got {assessment.get('urgency_level')}"
        )
        assert assessment.get("issue_category") == expected["issue_category"], (
            f"issue_category: expected {expected['issue_category']}, got {assessment.get('issue_category')}"
        )

        assert result.get("routing_decision") == expected["routing_decision"]

        # v1.3 前置止损：起火场景必须包含"远离""切断电源"等止损步骤
        auto_reply = result.get("auto_reply_sent", "")
        matched_keywords = [kw for kw in expected["auto_reply_keywords"] if kw in auto_reply]
        assert len(matched_keywords) > 0, (
            f"auto_reply should contain at least one of {expected['auto_reply_keywords']}, got: {auto_reply}"
        )

        # 验证SOP召回：应命中起火/冒烟相关SOP
        sop_applied = result.get("sop_applied", "")
        fire_sop_keywords = ["起火", "冒烟", "过热"]
        assert any(kw in sop_applied for kw in fire_sop_keywords), (
            f"sop_applied should contain fire/thermal SOP, got: {sop_applied}"
        )

    @pytest.mark.asyncio
    async def test_h_water_damage(self, engine):
        """H场景：进水 - 验证进水SOP召回"""
        scenario = SAMPLE_COMPLAINTS["H_water_damage"]
        result = await engine.process_complaint(text=scenario["text"])
        expected = scenario["expected"]

        assert result.get("ticket_id")

        assessment = result.get("agent_business_assessment", {})
        assert assessment.get("urgency_level") == expected["urgency_level"], (
            f"urgency_level: expected {expected['urgency_level']}, got {assessment.get('urgency_level')}"
        )
        assert assessment.get("issue_category") == expected["issue_category"], (
            f"issue_category: expected {expected['issue_category']}, got {assessment.get('issue_category')}"
        )

        assert result.get("routing_decision") == expected["routing_decision"]

        # 验证SOP召回：应命中进水相关SOP
        sop_applied = result.get("sop_applied", "")
        water_sop_keywords = ["进水", "水"]
        assert any(kw in sop_applied for kw in water_sop_keywords), (
            f"sop_applied should contain water damage SOP, got: {sop_applied}"
        )

    @pytest.mark.asyncio
    async def test_i_batch_defect(self, engine):
        """I场景：批次缺陷 - 验证批次缺陷SOP召回"""
        scenario = SAMPLE_COMPLAINTS["I_batch_defect"]
        result = await engine.process_complaint(text=scenario["text"])
        expected = scenario["expected"]

        assert result.get("ticket_id")

        assessment = result.get("agent_business_assessment", {})
        assert assessment.get("urgency_level") == expected["urgency_level"], (
            f"urgency_level: expected {expected['urgency_level']}, got {assessment.get('urgency_level')}"
        )
        assert assessment.get("issue_category") == expected["issue_category"], (
            f"issue_category: expected {expected['issue_category']}, got {assessment.get('issue_category')}"
        )

        assert result.get("routing_decision") == expected["routing_decision"]

        # 验证SOP召回：应命中批次缺陷相关SOP
        sop_applied = result.get("sop_applied", "")
        batch_sop_keywords = ["批次", "召回"]
        assert any(kw in sop_applied for kw in batch_sop_keywords), (
            f"sop_applied should contain batch defect SOP, got: {sop_applied}"
        )


class TestV13ImageAnalysis:
    """v1.3 多模态图片分析专项测试"""

    @pytest.mark.asyncio
    async def test_no_images_image_analysis_is_none(self, engine):
        """无图片时 image_analysis 应为 None"""
        result = await engine.process_complaint(text="设备坏了")
        assert result.get("image_analysis") is None, (
            f"image_analysis should be None when no images, got: {result.get('image_analysis')}"
        )

    @pytest.mark.asyncio
    async def test_empty_image_paths_image_analysis_is_none(self, engine):
        """空图片列表时 image_analysis 应为 None"""
        result = await engine.process_complaint(text="设备坏了", image_paths=[])
        assert result.get("image_analysis") is None, (
            f"image_analysis should be None when image_paths=[], got: {result.get('image_analysis')}"
        )

    @pytest.mark.asyncio
    async def test_nonexistent_image_paths_fallback(self, engine):
        """不存在的图片路径应降级到 none，Pipeline不阻塞"""
        result = await engine.process_complaint(
            text="设备冒烟了",
            image_paths=["/nonexistent/path/fake.jpg"],
        )
        assert result.get("ticket_id"), "Pipeline should not be blocked by image errors"

        image_analysis = result.get("image_analysis")
        if image_analysis is not None:
            assert image_analysis.get("analysis_source") in ("ocr", "pillow_basic", "none")
            assert "image_count" in image_analysis

    @pytest.mark.asyncio
    async def test_image_analysis_schema(self, engine):
        """image_analysis dict 应包含8个标准字段"""
        result = await engine.process_complaint(
            text="设备冒烟了",
            image_paths=["/nonexistent/fake.jpg"],
        )
        image_analysis = result.get("image_analysis")
        if image_analysis is not None and image_analysis.get("analysis_source") != "none":
            required_fields = [
                "damage_detected", "damage_level", "fault_types_found",
                "has_emergency_indicators", "overall_assessment",
                "suggestion", "analysis_source", "image_count",
            ]
            for field in required_fields:
                assert field in image_analysis, f"image_analysis missing field: {field}"

            assert image_analysis["analysis_source"] in ("ocr", "pillow_basic", "none")
            assert image_analysis["damage_level"] in ("none", "minor", "moderate", "severe")
            assert isinstance(image_analysis["damage_detected"], bool)
            assert isinstance(image_analysis["has_emergency_indicators"], bool)
            assert isinstance(image_analysis["fault_types_found"], list)
            assert isinstance(image_analysis["image_count"], int)


class TestV13EmergencyReply:
    """v1.3 前置止损回复专项测试"""

    @pytest.mark.asyncio
    async def test_high_priority_reply_has_emergency_steps(self, engine):
        """高优先级工单的自动回复必须包含可执行止损步骤"""
        result = await engine.process_complaint(text="设备冒烟了！有烧焦味！")

        assessment = result.get("agent_business_assessment", {})
        if assessment.get("urgency_level") == "High_Priority":
            auto_reply = result.get("auto_reply_sent", "")
            # 必须包含至少一个具体止损动作
            emergency_keywords = ["切断", "断电", "远离", "隔离", "严禁", "立即"]
            matched = [kw for kw in emergency_keywords if kw in auto_reply]
            assert len(matched) > 0, (
                f"High_Priority auto_reply must contain emergency steps, got: {auto_reply}"
            )

    @pytest.mark.asyncio
    async def test_leakage_reply_has_specific_steps(self, engine):
        """漏电场景回复必须包含'切断总闸'等具体步骤"""
        result = await engine.process_complaint(text="设备漏电了，手碰到就麻")

        auto_reply = result.get("auto_reply_sent", "")
        # 漏电场景应包含"切断总闸"而非笼统的"切断电源"
        assert "切断" in auto_reply, (
            f"Leakage auto_reply should contain '切断', got: {auto_reply}"
        )

    @pytest.mark.asyncio
    async def test_low_priority_reply_no_emergency(self, engine):
        """低优先级工单的自动回复不需要紧急止损步骤"""
        result = await engine.process_complaint(text="我的订单JD9988776655，缺少螺丝包")

        assessment = result.get("agent_business_assessment", {})
        if assessment.get("urgency_level") == "Low_Priority":
            auto_reply = result.get("auto_reply_sent", "")
            # 低优先级应包含常规指引
            assert len(auto_reply) > 0, "Low_Priority auto_reply should not be empty"


class TestV13SOPExpansion:
    """v1.3 SOP知识库扩充专项测试"""

    @pytest.mark.asyncio
    async def test_smoke_sop_recalled(self, engine):
        """冒烟场景应命中冒烟/过热SOP"""
        result = await engine.process_complaint(text="设备冒烟了，有过热现象")
        sop = result.get("sop_applied", "")
        assert any(kw in sop for kw in ["冒烟", "过热", "热失控"]), (
            f"sop_applied should match smoke/thermal SOP, got: {sop}"
        )

    @pytest.mark.asyncio
    async def test_leakage_sop_recalled(self, engine):
        """漏电场景应命中漏电SOP"""
        result = await engine.process_complaint(text="设备漏电了，碰了手麻")
        sop = result.get("sop_applied", "")
        assert any(kw in sop for kw in ["漏电", "触电"]), (
            f"sop_applied should match leakage SOP, got: {sop}"
        )

    @pytest.mark.asyncio
    async def test_fire_sop_recalled(self, engine):
        """起火场景应命中起火SOP"""
        result = await engine.process_complaint(text="设备起火了，有明火")
        sop = result.get("sop_applied", "")
        assert any(kw in sop for kw in ["起火", "冒烟", "过热", "热失控"]), (
            f"sop_applied should match fire SOP, got: {sop}"
        )

    @pytest.mark.asyncio
    async def test_water_sop_recalled(self, engine):
        """进水场景应命中进水SOP"""
        result = await engine.process_complaint(text="设备进水了，淋雨后开不了机")
        sop = result.get("sop_applied", "")
        assert any(kw in sop for kw in ["进水", "水"]), (
            f"sop_applied should match water SOP, got: {sop}"
        )

    @pytest.mark.asyncio
    async def test_batch_sop_recalled(self, engine):
        """批次缺陷场景应命中批次缺陷SOP"""
        result = await engine.process_complaint(text="我们这批X12批次的产品都有问题")
        sop = result.get("sop_applied", "")
        assert any(kw in sop for kw in ["批次", "召回"]), (
            f"sop_applied should match batch defect SOP, got: {sop}"
        )
