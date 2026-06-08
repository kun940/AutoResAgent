import json
import logging
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


class AssessmentAgent:
    async def assess(self, extracted_data: dict) -> dict:
        llm = get_llm_for_task("business_assessment", temperature=ASSESS_TEMPERATURE, max_tokens=ASSESS_MAX_TOKENS)

        if llm is None:
            return self._fallback_assess(extracted_data)

        extracted_json = json.dumps(extracted_data, ensure_ascii=False)
        user_content = ASSESS_USER_PROMPT.format(extracted_json=extracted_json)

        messages = [
            SystemMessage(content=ASSESS_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]

        try:
            response = await llm.ainvoke(messages)
            return self._parse_response(response.content, extracted_data)
        except Exception as e:
            logger.error(f"Assessment LLM call failed: {e}")
            return self._fallback_assess(extracted_data)

    def _parse_response(self, content: str, extracted_data: dict) -> dict:
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
            return self._fallback_assess(extracted_data)

    @staticmethod
    def _fallback_assess(extracted_data: dict) -> dict:
        fault = extracted_data.get("core_fault_desc", "")

        if any(kw in fault for kw in ["冒烟", "起火", "漏电", "触电"]):
            return {
                "issue_category": IssueCategory.HARDWARE_THERMAL_RUNAWAY.value,
                "business_impact": BusinessImpact.SAFETY_HAZARD.value,
                "urgency_level": UrgencyLevel.HIGH.value,
                "warranty_status": WarrantyStatus.IN_WARRANTY.value,
            }

        if any(kw in fault for kw in ["批量", "批次", "多台"]):
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