import json
import logging
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from agent.config.llm_config import get_llm_for_task
from agent.config.agent_config import EXTRACT_TEMPERATURE, EXTRACT_MAX_TOKENS
from agent.prompts.extract_prompt import EXTRACT_SYSTEM_PROMPT, EXTRACT_USER_PROMPT

logger = logging.getLogger(__name__)


class ExtractionAgent:
    async def extract(
        self,
        text: str,
        image_paths: Optional[list] = None,
        image_analysis: Optional[dict] = None,
    ) -> dict:
        llm = get_llm_for_task("field_extraction", temperature=EXTRACT_TEMPERATURE, max_tokens=EXTRACT_MAX_TOKENS)

        if llm is None:
            return self._fallback_extract(text, image_paths=image_paths, image_analysis=image_analysis)

        # 若有图片分析结果，融合到提取上下文
        extract_text = text
        if image_analysis and image_analysis.get("damage_detected"):
            fault_types = image_analysis.get("fault_types_found", [])
            assessment = image_analysis.get("overall_assessment", "")
            extract_text = f"{text}\n\n[图片证据分析结果] 故障类型: {fault_types}; 描述: {assessment}"

        user_content = EXTRACT_USER_PROMPT.format(text=extract_text)

        messages = [
            SystemMessage(content=EXTRACT_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]

        response = await llm.ainvoke(messages)
        return self._parse_response(response.content, text, image_paths=image_paths, image_analysis=image_analysis)

    def _parse_response(self, content: str, original_text: str, image_paths=None, image_analysis=None) -> dict:
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

            # evidence_images 优先使用实际上传路径
            evidence_images = list(image_paths) if image_paths else []

            # core_fault_desc 融合图片分析结果
            core_fault_desc = result.get("core_fault_desc")
            if image_analysis and image_analysis.get("damage_detected"):
                img_faults = "、".join(image_analysis.get("fault_types_found", []))
                if img_faults:
                    img_suffix = f"（图片证据：{img_faults}）"
                    core_fault_desc = f"{core_fault_desc}{img_suffix}" if core_fault_desc else f"图片证据显示{img_faults}"

            return {
                "order_id": result.get("order_id"),
                "model_number": result.get("model_number"),
                "batch_code": result.get("batch_code"),
                "core_fault_desc": core_fault_desc,
                "evidence_images": evidence_images,
                "evidence_videos": [],
            }
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"Failed to parse extraction response: {e}")
            return self._fallback_extract(original_text, image_paths=image_paths, image_analysis=image_analysis)

    @staticmethod
    def _fallback_extract(text: str, image_paths=None, image_analysis=None) -> dict:
        core_fault_desc = text[:200] if text else None
        if image_analysis and image_analysis.get("damage_detected"):
            img_faults = "、".join(image_analysis.get("fault_types_found", []))
            if img_faults:
                img_suffix = f"（图片证据：{img_faults}）"
                core_fault_desc = f"{core_fault_desc}{img_suffix}" if core_fault_desc else f"图片证据显示{img_faults}"
        return {
            "order_id": None,
            "model_number": None,
            "batch_code": None,
            "core_fault_desc": core_fault_desc,
            "evidence_images": list(image_paths) if image_paths else [],
            "evidence_videos": [],
        }
