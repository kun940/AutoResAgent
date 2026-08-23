"""v2.0: 多模态证据分析器，四级降级：VLM → OCR+文本推理 → Pillow → none"""
import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

MAX_IMAGES_TO_ANALYZE = 3
OCR_TIMEOUT_SECONDS = 30


class MultimodalAnalyzer:
    """v2.0: 多模态证据分析器，四级降级：VLM → OCR+文本推理 → Pillow → none

    L1 主路径：VLM 端到端分析 + OCR 提取 SN 码（并行），analysis_source="vlm"
    L2 降级：OCR + 文本 LLM 推理（v1.3 主路径），analysis_source="ocr_v13"
    L3 降级：Pillow 启发式分析，analysis_source="pillow_basic"
    L4 兜底：仅记录图片数量，analysis_source="none"
    """

    def __init__(self):
        self._vlm_analyzer = None
        self._vlm_init_failed = False
        self._ocr_client = None
        self._ocr_init_failed = False
        self._pillow_analyzer = None
        self._pillow_init_failed = False

    @property
    def vlm_analyzer(self):
        """懒加载 VLM 客户端，失败后不再重试"""
        if self._vlm_init_failed:
            return None
        if self._vlm_analyzer is None:
            try:
                from agent.multimodal.vlm_analyzer import VlmAnalyzer
                self._vlm_analyzer = VlmAnalyzer()
            except Exception as e:
                logger.warning(f"VLM analyzer init failed: {e}")
                self._vlm_init_failed = True
                return None
        return self._vlm_analyzer

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

        v2.0 降级链：
          1. VLM 主路径可用 → VLM 分析 + OCR 提取 SN 码（并行），analysis_source="vlm"
             ├─ VLM 成功 → 合并 OCR SN 结果返回
             └─ VLM 失败/超时/返回非JSON → 降级 L2
          2. OCR + 文本 LLM 推理（v1.3 主路径），analysis_source="ocr_v13"
             ├─ 成功 → 返回（并尝试补抽 SN 码）
             └─ 失败 → 降级 L3
          3. Pillow 启发式分析，analysis_source="pillow_basic"
          4. none
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

        # L1 主路径：VLM + OCR 并行
        vlm_enabled = self._is_vlm_enabled()
        if vlm_enabled and self.vlm_analyzer is not None:
            try:
                result = await self._run_vlm_with_sn(valid_images, text_context)
                result["image_count"] = image_count
                result["analysis_source"] = "vlm"
                logger.info(
                    f"VLM analysis done: damage_level={result.get('damage_level')}"
                )
                return result
            except Exception as e:
                logger.warning(
                    f"VLM analysis failed, falling back to OCR+LLM: {e}"
                )

        # L2 降级：OCR + 文本 LLM 推理（v1.3 主路径）
        if self.ocr_client is not None:
            try:
                result = await self.ocr_client.analyze(valid_images, text_context)
                result["image_count"] = image_count
                result["analysis_source"] = "ocr_v13"
                # 补抽 SN 码（L2 路径也尝试提取结构化信息）
                try:
                    sn_info = await asyncio.to_thread(
                        self.ocr_client.extract_sn_info, valid_images
                    )
                    result.update(sn_info)
                except Exception as sn_err:
                    logger.warning(f"SN info extract failed in L2: {sn_err}")
                    result.update({
                        "sn_code": None, "model_info": None, "batch_no": None,
                        "order_no": None,
                    })
                logger.info(
                    f"OCR+LLM analysis done: damage_level={result.get('damage_level')}"
                )
                return result
            except Exception as e:
                logger.warning(f"OCR+LLM analysis failed, falling back to pillow: {e}")

        # L3 降级：Pillow 启发式分析
        if self.pillow_analyzer is not None:
            try:
                result = self.pillow_analyzer.analyze(valid_images)
                result["image_count"] = image_count
                result["analysis_source"] = "pillow_basic"
                result.setdefault("sn_code", None)
                result.setdefault("model_info", None)
                result.setdefault("batch_no", None)
                result.setdefault("order_no", None)
                result.setdefault("vlm_latency_ms", None)
                logger.info(
                    f"Pillow analysis done: damage_level={result.get('damage_level')}"
                )
                return result
            except Exception as e:
                logger.warning(f"Pillow analysis failed: {e}")

        # L4 兜底
        logger.info("All image analysis methods failed, returning none")
        return self._empty_analysis(image_count=image_count)

    async def _run_vlm_with_sn(
        self,
        valid_images: list[dict],
        text_context: str,
    ) -> dict:
        """L1 主路径：并行执行 VLM 分析与 OCR SN 提取，合并结果

        - VLM 失败 → 整体抛异常，由 analyze_images 捕获降级到 L2
        - OCR 失败 → 不降级，仅 OCR 字段置 None
        - v2.1: VLM 直接提取铭牌字段（sn_code/model_info/batch_no/order_no），
          优先于 OCR；OCR 仅补充 VLM 未提取到的 sn_code/model_info/batch_no
        """
        vlm_task = self.vlm_analyzer.analyze(valid_images, text_context)

        # OCR SN 提取是同步方法，用 asyncio.to_thread 包裹后并行
        sn_task = asyncio.to_thread(self._safe_extract_sn, valid_images)

        try:
            vlm_result, sn_result = await asyncio.gather(
                vlm_task, sn_task, return_exceptions=True
            )
        except Exception as e:
            # gather 整体异常（极少见），抛出触发降级
            raise

        # VLM 异常 → 整体降级
        if isinstance(vlm_result, Exception):
            raise vlm_result

        # OCR 异常 → 不降级，仅 OCR 字段置 None
        if isinstance(sn_result, Exception):
            logger.warning(
                f"OCR SN extract failed, sn fields set to None: {sn_result}"
            )
            sn_result = {}

        # v2.1: VLM 提取的铭牌字段优先；OCR 仅补充 VLM 未提取到的字段
        # （OCR 不可用时 sn_result 为空 dict，VLM 结果原样保留）
        if not isinstance(sn_result, dict):
            sn_result = {}
        for key in ("sn_code", "model_info", "batch_no", "order_no"):
            if not vlm_result.get(key):
                ocr_val = sn_result.get(key)
                if ocr_val:
                    vlm_result[key] = ocr_val
            vlm_result.setdefault(key, None)
        return vlm_result

    def _safe_extract_sn(self, valid_images: list[dict]) -> dict:
        """安全调用 OCR SN 提取（OCR 不可用时返回全 None）"""
        if self.ocr_client is None:
            return {"sn_code": None, "model_info": None, "batch_no": None}
        return self.ocr_client.extract_sn_info(valid_images)

    @staticmethod
    def _is_vlm_enabled() -> bool:
        """读取 VLM_ENABLED 配置开关"""
        try:
            from backend.app.config import settings
            return settings.VLM_ENABLED == "1"
        except Exception:
            return True  # 配置读取失败时默认启用

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
            "sn_code": None,
            "model_info": None,
            "batch_no": None,
            "order_no": None,
            "vlm_latency_ms": None,
        }
