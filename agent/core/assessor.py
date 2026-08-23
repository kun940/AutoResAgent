import json
import logging
import re
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from agent.config.llm_config import get_llm_for_task
from agent.config.agent_config import ASSESS_TEMPERATURE, ASSESS_MAX_TOKENS
from agent.prompts.assess_prompt import ASSESS_SYSTEM_PROMPT, ASSESS_USER_PROMPT
from shared.constants import UrgencyLevel, IssueCategory, BusinessImpact, WarrantyStatus

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {e.value for e in IssueCategory}
VALID_IMPACTS = {e.value for e in BusinessImpact}
VALID_URGENCIES = {e.value for e in UrgencyLevel}
VALID_WARRANTIES = {e.value for e in WarrantyStatus}

# v1.4: 批次场景关键词匹配——"批次"需排除"批次号/批次编号/批次代码/批次码"等标识符场景
# 避免用户在问题描述中填写批次号作为产品标识时被误判为批次缺陷
BATCH_KEYWORDS = ["批量", "多台", "群体", "同故障", "这批", "这批产品"]
BATCH_REGEX = re.compile(r"批次(?!号|编号|代码|码|ID|id)")


def _match_batch_defect(text: str) -> bool:
    """判断文本是否指示批次缺陷场景（排除"批次号"等标识符场景）"""
    if not text:
        return False
    return any(kw in text for kw in BATCH_KEYWORDS) or bool(BATCH_REGEX.search(text))


class AssessmentAgent:
    async def assess(self, extracted_data: dict, image_analysis: dict = None, raw_text: str = None) -> dict:
        llm = get_llm_for_task("business_assessment", temperature=ASSESS_TEMPERATURE, max_tokens=ASSESS_MAX_TOKENS)

        if llm is None:
            return self._fallback_assess(extracted_data, image_analysis=image_analysis)

        # 若有图片分析结果，将图片证据信息添加到 extracted_data 中
        assess_data = dict(extracted_data)
        if image_analysis and image_analysis.get("damage_detected"):
            assess_data["image_evidence"] = {
                "damage_detected": image_analysis.get("damage_detected", False),
                "damage_level": image_analysis.get("damage_level", "none"),
                "fault_types_found": image_analysis.get("fault_types_found", []),
                "has_emergency_indicators": image_analysis.get("has_emergency_indicators", False),
            }

        extracted_json = json.dumps(assess_data, ensure_ascii=False)
        user_content = ASSESS_USER_PROMPT.format(extracted_json=extracted_json)

        messages = [
            SystemMessage(content=ASSESS_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]

        try:
            response = await llm.ainvoke(messages)
            return self._parse_response(response.content, extracted_data, image_analysis=image_analysis, raw_text=raw_text)
        except Exception as e:
            logger.error(f"Assessment LLM call failed: {e}")
            return self._fallback_assess(extracted_data, image_analysis=image_analysis)

    def _parse_response(self, content: str, extracted_data: dict, image_analysis=None, raw_text: str = None) -> dict:
        try:
            cleaned = content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            result = json.loads(cleaned)

            issue_category = result.get("issue_category", "Other")
            business_impact = result.get("business_impact", "Minor_Inconvenience")
            urgency_level = result.get("urgency_level", "Medium_Priority")
            warranty_status = result.get("warranty_status", "Unknown")

            # 图片证据定级覆盖：紧急指标强制高优先级
            if image_analysis and image_analysis.get("has_emergency_indicators"):
                urgency_level = "High_Priority"
            if image_analysis and image_analysis.get("damage_level") == "severe":
                if business_impact not in ("Safety_Hazard", "Group_Risk"):
                    business_impact = "Safety_Hazard"

            # v1.3 关键词强制覆盖：防止LLM对边界case判断不稳定
            # 合并原始客诉文本和故障描述进行关键词匹配
            original_text = ((raw_text or "") + " " + (extracted_data.get("core_fault_desc") or "")).lower()

            # 进水场景：短路+触电风险，强制High_Priority
            if any(kw in original_text for kw in ["进水", "淋雨", "水浸", "水渍", "液体泼溅", "泡水"]):
                urgency_level = "High_Priority"
                if business_impact not in ("Safety_Hazard", "Group_Risk"):
                    business_impact = "Safety_Hazard"
                if issue_category not in ("Hardware_Malfunction", "Electrical_Leakage"):
                    issue_category = "Hardware_Malfunction"

            # 批次/批量场景：群体性风险，强制Batch_Defect + High_Priority
            # v1.4: 排除"批次号/批次编号"等标识符场景，避免用户填写批次号时被误判
            if _match_batch_defect(original_text):
                urgency_level = "High_Priority"
                business_impact = "Group_Risk"
                issue_category = "Batch_Defect"

            # 漏电/触电场景：强制Electrical_Leakage + High_Priority
            if any(kw in original_text for kw in ["漏电", "触电", "电击", "麻手", "麻了"]):
                urgency_level = "High_Priority"
                business_impact = "Safety_Hazard"
                issue_category = "Electrical_Leakage"

            # 冒烟/起火场景：强制Hardware_Thermal_Runaway + High_Priority
            if any(kw in original_text for kw in ["冒烟", "起火", "明火", "烧焦", "烧起来"]):
                urgency_level = "High_Priority"
                business_impact = "Safety_Hazard"
                issue_category = "Hardware_Thermal_Runaway"

            if issue_category not in VALID_CATEGORIES:
                issue_category = "Other"
            if business_impact not in VALID_IMPACTS:
                business_impact = "Minor_Inconvenience"
            if urgency_level not in VALID_URGENCIES:
                urgency_level = "Medium_Priority"
            if warranty_status not in VALID_WARRANTIES:
                warranty_status = "Unknown"

            return {
                "issue_category": issue_category,
                "business_impact": business_impact,
                "urgency_level": urgency_level,
                "warranty_status": warranty_status,
            }
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"Failed to parse assessment response: {e}")
            return self._fallback_assess(extracted_data, image_analysis=image_analysis)

    @staticmethod
    def _fallback_assess(extracted_data: dict, image_analysis=None) -> dict:
        fault = extracted_data.get("core_fault_desc", "")

        # 图片证据中的紧急指标 → 强制 High_Priority
        if image_analysis and image_analysis.get("has_emergency_indicators"):
            fault_types = image_analysis.get("fault_types_found", [])
            if any(t in str(fault_types) for t in ["冒烟", "烧焦", "起火"]):
                return {
                    "issue_category": IssueCategory.HARDWARE_THERMAL_RUNAWAY.value,
                    "business_impact": BusinessImpact.SAFETY_HAZARD.value,
                    "urgency_level": UrgencyLevel.HIGH.value,
                    "warranty_status": WarrantyStatus.IN_WARRANTY.value,
                }
            if any(t in str(fault_types) for t in ["漏电", "触电", "水渍"]):
                return {
                    "issue_category": IssueCategory.ELECTRICAL_LEAKAGE.value,
                    "business_impact": BusinessImpact.SAFETY_HAZARD.value,
                    "urgency_level": UrgencyLevel.HIGH.value,
                    "warranty_status": WarrantyStatus.IN_WARRANTY.value,
                }
            return {
                "issue_category": IssueCategory.OTHER.value,
                "business_impact": BusinessImpact.SAFETY_HAZARD.value,
                "urgency_level": UrgencyLevel.HIGH.value,
                "warranty_status": WarrantyStatus.UNKNOWN.value,
            }

        if any(kw in fault for kw in ["冒烟", "起火", "漏电", "触电"]):
            return {
                "issue_category": IssueCategory.HARDWARE_THERMAL_RUNAWAY.value,
                "business_impact": BusinessImpact.SAFETY_HAZARD.value,
                "urgency_level": UrgencyLevel.HIGH.value,
                "warranty_status": WarrantyStatus.IN_WARRANTY.value,
            }

        # 进水场景：短路+触电风险，High_Priority
        if any(kw in fault for kw in ["进水", "淋雨", "水浸", "水渍", "液体"]):
            return {
                "issue_category": IssueCategory.HARDWARE_MALFUNCTION.value,
                "business_impact": BusinessImpact.SAFETY_HAZARD.value,
                "urgency_level": UrgencyLevel.HIGH.value,
                "warranty_status": WarrantyStatus.IN_WARRANTY.value,
            }

        # v1.4: 排除"批次号/批次编号"等标识符场景，避免误判
        if _match_batch_defect(fault):
            return {
                "issue_category": IssueCategory.BATCH_DEFECT.value,
                "business_impact": BusinessImpact.GROUP_RISK.value,
                "urgency_level": UrgencyLevel.HIGH.value,
                "warranty_status": WarrantyStatus.UNKNOWN.value,
            }

        if any(kw in fault for kw in ["无法使用", "不工作", "死机"]):
            return {
                "issue_category": IssueCategory.HARDWARE_MALFUNCTION.value,
                "business_impact": BusinessImpact.FUNCTIONAL_LOSS.value,
                "urgency_level": UrgencyLevel.MEDIUM.value,
                "warranty_status": WarrantyStatus.IN_WARRANTY.value,
            }

        return {
            "issue_category": IssueCategory.OTHER.value,
            "business_impact": BusinessImpact.MINOR_INCONVENIENCE.value,
            "urgency_level": UrgencyLevel.MEDIUM.value,
            "warranty_status": WarrantyStatus.UNKNOWN.value,
        }