"""OCR识别客户端（PaddleOCR）+ 文本LLM推理（QwQ-32B）"""
import json
import logging
import re
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from agent.config.llm_config import get_llm_for_task
from agent.config.agent_config import IMAGE_ANALYSIS_TEMPERATURE, IMAGE_ANALYSIS_MAX_TOKENS
from agent.multimodal.prompts import OCR_SYSTEM_PROMPT, OCR_USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)

# v2.0: SN 码/型号/批次号正则规则（用于 extract_sn_info）
SN_PATTERNS = [
    r"(?:SN|S/?N|序列号|Serial\s*No\.?)[\s:：]*([A-Z0-9\-]{6,20})",
    r"\b([A-Z]{2,3}\d{8,12})\b",  # 兜底：2-3字母+8-12数字
]
MODEL_PATTERNS = [
    r"(?:型号|Model|M/?P)[\s:：]*([A-Z0-9\-]{3,30})",
]
BATCH_PATTERNS = [
    r"(?:批次号?|Batch|Lot)[\s:：]*([A-Z0-9\-]{3,30})",
]


class OcrClient:
    """OCR识别 + 文本LLM推理客户端，替代视觉大模型"""

    def __init__(self):
        self._ocr = None
        self._ocr_init_failed = False
        self._llm = None

    def _get_ocr(self):
        """懒加载 PaddleOCR"""
        if self._ocr_init_failed:
            return None
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR
                self._ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)
                logger.info("PaddleOCR initialized successfully")
            except Exception as e:
                logger.warning(f"PaddleOCR init failed: {e}")
                self._ocr_init_failed = True
                return None
        return self._ocr

    def _get_llm(self):
        """获取文本LLM（QwQ-32B）用于推理OCR结果"""
        if self._llm is None:
            self._llm = get_llm_for_task(
                "image_analysis",
                temperature=IMAGE_ANALYSIS_TEMPERATURE,
                max_tokens=IMAGE_ANALYSIS_MAX_TOKENS,
            )
        return self._llm

    async def analyze(self, images: list[dict], text_context: str = "") -> dict:
        """
        OCR提取图片文字 → LLM推理图片故障

        两步流程：
        1. PaddleOCR 从每张图片中提取文字
        2. QwQ-32B 根据OCR文字 + 客诉文本推理图片中的故障迹象

        Args:
            images: ImageProcessor.preprocess 的输出
            text_context: 客诉文本

        Returns: image_analysis dict（不含 analysis_source/image_count，由调用方填充）
        """
        # Step 1: OCR 提取文字
        ocr_texts = []
        ocr = self._get_ocr()
        if ocr is not None:
            for img_data in images:
                try:
                    text = self._ocr_extract(img_data, ocr)
                    if text:
                        ocr_texts.append(text)
                except Exception as e:
                    logger.warning(f"OCR extract failed for image: {e}")
        else:
            # OCR不可用，尝试从图片文件名推断
            for img_data in images:
                path = img_data.get("path", "")
                ocr_texts.append(f"（图片文件: {path}，OCR不可用）")

        # Step 2: LLM 推理
        llm = self._get_llm()
        if llm is None:
            raise RuntimeError("LLM not available for OCR analysis")

        ocr_summary = "\n".join(ocr_texts) if ocr_texts else "（OCR未识别到文字）"
        user_text = OCR_USER_PROMPT_TEMPLATE.format(
            text_context=text_context or "（无文本上下文）",
            ocr_result=ocr_summary,
            image_count=len(images),
        )

        messages = [
            SystemMessage(content=OCR_SYSTEM_PROMPT),
            HumanMessage(content=user_text),
        ]

        response = await llm.ainvoke(messages)
        return self._parse_response(response.content)

    def _ocr_extract(self, img_data: dict, ocr) -> str:
        """从图片中提取文字"""
        import numpy as np

        pil_img = img_data.get("pil_image")
        if pil_img is None:
            return ""

        img_array = np.array(pil_img)
        results = ocr.ocr(img_array, cls=True)

        texts = []
        if results and results[0]:
            for line in results[0]:
                if line and len(line) >= 2:
                    texts.append(line[1][0])  # (text, confidence)

        return "；".join(texts) if texts else ""

    def extract_sn_info(self, images: list[dict]) -> dict:
        """
        v2.0: 仅用 PaddleOCR 提取图片中的结构化铭牌信息，不调用 LLM。

        从所有图片的 OCR 文字中正则匹配 SN 码、型号、批次号。
        OCR 不可用时返回全 None，不抛异常（确保 L1 主路径稳定）。

        Returns:
            {"sn_code": str|None, "model_info": str|None, "batch_no": str|None}
        """
        empty_result = {
            "sn_code": None,
            "model_info": None,
            "batch_no": None,
        }

        ocr = self._get_ocr()
        if ocr is None:
            logger.info("OCR not available, SN info extraction skipped")
            return empty_result

        # 收集所有图片的 OCR 文字
        all_texts = []
        for img_data in images:
            try:
                text = self._ocr_extract(img_data, ocr)
                if text:
                    all_texts.append(text)
            except Exception as e:
                logger.warning(f"OCR extract failed for SN info: {e}")

        if not all_texts:
            return empty_result

        combined_text = " ".join(all_texts)

        return {
            "sn_code": self._match_first(combined_text, SN_PATTERNS),
            "model_info": self._match_first(combined_text, MODEL_PATTERNS),
            "batch_no": self._match_first(combined_text, BATCH_PATTERNS),
        }

    @staticmethod
    def _match_first(text: str, patterns: list[str]) -> Optional[str]:
        """按 patterns 顺序匹配，返回首个命中结果"""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _parse_response(self, content: str) -> dict:
        """解析LLM返回的JSON"""
        cleaned = content.strip()

        # 去除 <think> 标签
        cleaned = re.sub(r'<think\b[^>]*>.*?</think\s*>', '', cleaned, flags=re.DOTALL).strip()

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
            "has_emergency_indicators": bool(result.get("has_emergency_indicators", False)),
            "overall_assessment": str(result.get("overall_assessment", "")),
            "suggestion": str(result.get("suggestion", "")),
        }

    @staticmethod
    def _validate_level(level: str) -> str:
        valid = {"none", "minor", "moderate", "severe"}
        return level if level in valid else "none"
