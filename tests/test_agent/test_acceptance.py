import re

import pytest

from agent.core.agent_engine import ComplaintAgentEngine
from tests.test_data.sample_complaints import SAMPLE_COMPLAINTS


@pytest.fixture
def engine():
    return ComplaintAgentEngine()


class TestAcceptance:

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

    @pytest.mark.asyncio
    async def test_e_smoke_with_images(self, engine):
        """测试带图片的冒烟场景 - 验证图片分析功能。"""
        scenario = SAMPLE_COMPLAINTS["E_smoke_with_images"]
        result = await engine.process_complaint(
            text=scenario["text"],
            image_paths=scenario.get("image_paths"),
        )
        expected = scenario["expected"]

        # 基础工单验证
        assert result.get("ticket_id"), "ticket_id should not be empty"
        assert re.match(r"CS-\d{8}-\d{4}", result["ticket_id"]), (
            f"ticket_id format should be CS-YYYYMMDD-XXXX, got {result['ticket_id']}"
        )

        # 图片分析结果验证
        image_analysis = result.get("image_analysis")
        assert image_analysis is not None, "image_analysis should not be None when images provided"
        assert isinstance(image_analysis, dict), "image_analysis should be a dict"

        # 验证图片分析字段完整性
        assert "damage_detected" in image_analysis
        assert "damage_level" in image_analysis
        assert "fault_types_found" in image_analysis
        assert "has_emergency_indicators" in image_analysis
        assert "overall_assessment" in image_analysis
        assert "suggestion" in image_analysis
        assert "analysis_source" in image_analysis
        assert "image_count" in image_analysis

        # 验证图片数量
        assert image_analysis["image_count"] == len(scenario.get("image_paths", [])), (
            f"image_count: expected {len(scenario.get('image_paths', []))}, got {image_analysis['image_count']}"
        )

        # 未提供真实图片时，分析来源应为 pillow_basic （降级）
        assert image_analysis["analysis_source"] in ("vlm", "pillow_basic", "none"), (
            f"unexpected analysis_source: {image_analysis['analysis_source']}"
        )

        # 验证定级不受影响
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
