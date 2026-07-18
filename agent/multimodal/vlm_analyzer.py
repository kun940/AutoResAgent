"""v2.0: 多模态大模型（VLM）图片分析器，主路径"""
import json
import logging
import re
import time
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from agent.config.llm_config import get_llm_for_task
from agent.config.agent_config import VLM_TEMPERATURE, VLM_MAX_TOKENS
from agent.multimodal.prompts import VLM_SYSTEM_PROMPT, VLM_USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


class VlmAnalyzer:
    """多模态大模型图片分析器（主路径）

    直接将图片以 base64 dataurl 形式传入 VLM（xopqwen35v35b），
    端到端输出 damage_level / fault_types_found 等结构化字段。
    """

    def __init__(self):
        self._llm = None
        self._init_failed = False

    def _get_llm(self):
        """懒加载 VLM，通过 image_vlm_analysis 任务获取"""
        if self._init_failed:
            return None
        if self._llm is None:
            try:
                self._llm = get_llm_for_task(
                    "image_vlm_analysis",
                    temperature=VLM_TEMPERATURE,
                    max_tokens=VLM_MAX_TOKENS,
                )
                if self._llm is None:
                    self._init_failed = True
                    logger.warning("VLM LLM factory returned None")
            except Exception as e:
                logger.warning(f"VLM init failed: {e}")
                self._init_failed = True
                return None
        return self._llm

    async def analyze(
        self,
        images: list[dict],
        text_context: str = "",
    ) -> dict:
        """
        调用 VLM 分析图片，返回 image_analysis dict（不含 analysis_source/image_count）。

        Args:
            images: ImageProcessor.preprocess 的输出，需包含 base64 字段
            text_context: 客诉文本

        Returns:
            image_analysis dict，额外含 vlm_latency_ms

        Raises:
            RuntimeError: VLM 不可用
            Exception: VLM 调用或解析失败（由编排器捕获并降级）
        """
        from backend.app.config import settings

        llm = self._get_llm()
        if llm is None:
            raise RuntimeError("VLM LLM not available")

        # 限制图片数量
        max_images = settings.VLM_MAX_IMAGES
        images_to_analyze = images[:max_images]

        messages = self._build_messages(images_to_analyze, text_context)

        start_ms = time.time() * 1000
        response = await llm.ainvoke(messages)
        elapsed_ms = int(time.time() * 1000 - start_ms)

        result = self._parse_response(response.content)
        result["vlm_latency_ms"] = elapsed_ms
        logger.info(
            f"VLM analysis done in {elapsed_ms}ms: "
            f"damage_level={result.get('damage_level')}"
        )
        return result

    def _build_messages(
        self,
        images: list[dict],
        text_context: str,
    ) -> list:
        """构造多模态消息列表

        HumanMessage.content 采用多块格式：
          [{"type": "text", "text": ...}, {"type": "image_url", "image_url": {"url": "data:..."}}, ...]
        """
        user_text = VLM_USER_PROMPT_TEMPLATE.format(
            image_count=len(images),
            text_context=text_context or "（无文本上下文）",
        )

        content_blocks = [{"type": "text", "text": user_text}]

        for img_data in images:
            b64 = img_data.get("base64")
            media_type = img_data.get("media_type", "image/jpeg")
            if not b64:
                continue
            dataurl = f"data:{media_type};base64,{b64}"
            content_blocks.append({
                "type": "image_url",
                "image_url": {"url": dataurl},
            })

        return [
            SystemMessage(content=VLM_SYSTEM_PROMPT),
            HumanMessage(content=content_blocks),
        ]

    def _parse_response(self, content: str) -> dict:
        """解析 VLM 返回的 JSON，复用 OcrClient 的清洗逻辑"""
        cleaned = content.strip()

        # 去除 <think>...</think> 标签
        cleaned = re.sub(
            r'<think\b[^>]*>.*?</think\s*>', '', cleaned, flags=re.DOTALL
        ).strip()

        # 去除 markdown 代码块
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        result = json.loads(cleaned)

        return {
            "damage_detected": bool(result.get("damage_detected", False)),
            "damage_level": self._validate_level(result.get("damage_level", "none")),
            "fault_types_found": list(result.get("fault_types_found", [])),
            "has_emergency_indicators": bool(
                result.get("has_emergency_indicators", False)
            ),
            "overall_assessment": str(result.get("overall_assessment", "")),
            "suggestion": str(result.get("suggestion", "")),
        }

    @staticmethod
    def _validate_level(level: str) -> str:
        valid = {"none", "minor", "moderate", "severe"}
        return level if level in valid else "none"
