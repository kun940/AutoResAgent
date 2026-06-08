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
    ) -> dict:
        llm = get_llm_for_task("field_extraction", temperature=EXTRACT_TEMPERATURE, max_tokens=EXTRACT_MAX_TOKENS)

        if llm is None:
            return self._fallback_extract(text)

        user_content = EXTRACT_USER_PROMPT.format(text=text)

        messages = [
            SystemMessage(content=EXTRACT_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]

        response = await llm.ainvoke(messages)
        return self._parse_response(response.content, text)

    def _parse_response(self, content: str, original_text: str) -> dict:
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

            return {
                "order_id": result.get("order_id"),
                "model_number": result.get("model_number"),
                "batch_code": result.get("batch_code"),
                "core_fault_desc": result.get("core_fault_desc"),
                "evidence_images": result.get("evidence_images", []),
                "evidence_videos": result.get("evidence_videos", []),
            }
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"Failed to parse extraction response: {e}")
            return self._fallback_extract(original_text)

    @staticmethod
    def _fallback_extract(text: str) -> dict:
        return {
            "order_id": None,
            "model_number": None,
            "batch_code": None,
            "core_fault_desc": text[:200] if text else None,
            "evidence_images": [],
            "evidence_videos": [],
        }
