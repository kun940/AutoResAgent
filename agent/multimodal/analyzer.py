"""多模态证据分析器，三级降级：OCR → Pillow → none"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

MAX_IMAGES_TO_ANALYZE = 3
OCR_TIMEOUT_SECONDS = 30


class MultimodalAnalyzer:
    """多模态证据分析器，三级降级：OCR → Pillow → none"""

    def __init__(self):
        self._ocr_client = None
        self._ocr_init_failed = False
        self._pillow_analyzer = None
        self._pillow_init_failed = False

    @property
    def ocr_client(self):
        """懒加载OCR客户端，失败后不再重试"""
        if self._ocr_init_failed:
            return None
        if self._ocr_client is None:
            try:
                from agent.multimodal.ocr_client import OcrClient
                self._ocr_client = OcrClient()
            except Exception as e:
                logger.warning(f"OCR client init failed, will use pillow fallback: {e}")
                self._ocr_init_failed = True
                return None
        return self._ocr_client

    @property
    def pillow_analyzer(self):
        """懒加载Pillow分析器"""
        if self._pillow_init_failed:
            return None
        if self._pillow_analyzer is None:
            try:
                from agent.multimodal.pillow_analyzer import PillowAnalyzer
                self._pillow_analyzer = PillowAnalyzer()
            except Exception as e:
                logger.warning(f"Pillow analyzer init failed: {e}")
                self._pillow_init_failed = True
                return None
        return self._pillow_analyzer

    async def analyze_images(
        self,
        image_paths: list[str],
        text_context: str = "",
    ) -> dict:
        """
        分析图片证据，返回标准化image_analysis dict。

        降级链：
          1. OCR可用 → PaddleOCR提取文字 + QwQ-32B推理，analysis_source="ocr"
          2. OCR不可用/失败 → Pillow启发式分析，analysis_source="pillow_basic"
          3. Pillow不可用/失败 → 仅记录图片数量，analysis_source="none"
        """
        if not image_paths:
            return self._empty_analysis()

        paths_to_analyze = image_paths[:MAX_IMAGES_TO_ANALYZE]
        image_count = len(image_paths)

        from agent.multimodal.image_processor import ImageProcessor
        valid_images = ImageProcessor.preprocess(paths_to_analyze)
        if not valid_images:
            logger.warning("No valid images after preprocessing")
            return self._empty_analysis(image_count=image_count)

        # 主路径：OCR + LLM 分析
        if self.ocr_client is not None:
            try:
                result = await self.ocr_client.analyze(valid_images, text_context)
                result["image_count"] = image_count
                result["analysis_source"] = "ocr"
                logger.info(f"OCR analysis done: damage_level={result.get('damage_level')}")
                return result
            except Exception as e:
                logger.warning(f"OCR analysis failed, falling back to pillow: {e}")

        # 降级1：Pillow启发式分析
        if self.pillow_analyzer is not None:
            try:
                result = self.pillow_analyzer.analyze(valid_images)
                result["image_count"] = image_count
                result["analysis_source"] = "pillow_basic"
                logger.info(f"Pillow analysis done: damage_level={result.get('damage_level')}")
                return result
            except Exception as e:
                logger.warning(f"Pillow analysis failed: {e}")

        # 降级2：none
        logger.info("All image analysis methods failed, returning none")
        return self._empty_analysis(image_count=image_count)

    @staticmethod
    def _empty_analysis(image_count: int = 0) -> dict:
        return {
            "damage_detected": False,
            "damage_level": "none",
            "fault_types_found": [],
            "has_emergency_indicators": False,
            "overall_assessment": "未提供图片或图片分析不可用" if image_count == 0 else "图片分析服务暂不可用，已记录图片证据",
            "suggestion": "",
            "analysis_source": "none",
            "image_count": image_count,
        }
