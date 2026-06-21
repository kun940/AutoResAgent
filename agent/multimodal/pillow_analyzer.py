"""Pillow启发式图像分析（OCR不可用时的降级方案）"""
import base64
import logging
from io import BytesIO

logger = logging.getLogger(__name__)


class PillowAnalyzer:
    """
    Pillow启发式图像分析（OCR不可用时的降级方案）。

    局限性：无法识别"冒烟"等语义内容，但可通过以下启发式信号辅助判断：
      - 图片整体偏暗/偏亮（可能异常环境）
      - 主色调偏黄/偏黑（可能烧焦/烟雾）
      - 图片尺寸异常（可能截图非实拍）
    """

    def analyze(self, images: list[dict]) -> dict:
        """启发式分析图片"""
        from PIL import Image

        emergency_indicators = 0
        fault_types = []
        assessments = []

        for img_data in images:
            try:
                # 优先使用pil_image，否则从base64解码
                pil_img = img_data.get("pil_image")
                if pil_img is None:
                    raw = base64.b64decode(img_data["base64"])
                    pil_img = Image.open(BytesIO(raw)).convert("RGB")

                w, h = pil_img.size

                # 启发式1：主色调分析
                dominant_color, is_warm_dark = self._analyze_color(pil_img)
                if is_warm_dark:
                    emergency_indicators += 1
                    fault_types.append("疑似烧焦/过热痕迹")
                    assessments.append(f"图片主色调偏暗暖色({dominant_color})，疑似烧焦痕迹")

                # 启发式2：尺寸异常检测
                if w < 100 or h < 100:
                    fault_types.append("图片尺寸过小，可能非实拍证据")

            except Exception as e:
                logger.warning(f"Pillow analyze single image failed: {e}")

        damage_detected = emergency_indicators > 0
        damage_level = "severe" if emergency_indicators >= 2 else (
            "moderate" if emergency_indicators == 1 else "none"
        )

        return {
            "damage_detected": damage_detected,
            "damage_level": damage_level,
            "fault_types_found": list(set(fault_types)),
            "has_emergency_indicators": emergency_indicators > 0,
            "overall_assessment": "；".join(assessments) if assessments else "未检测到明显异常信号",
            "suggestion": "建议人工复核图片证据" if damage_detected else "",
        }

    def _analyze_color(self, img) -> tuple[str, bool]:
        """分析主色调，返回(颜色描述, 是否暗暖色)"""
        import colorsys

        small = img.resize((50, 50))
        pixels = list(small.getdata())

        r_avg = sum(p[0] for p in pixels) / len(pixels)
        g_avg = sum(p[1] for p in pixels) / len(pixels)
        b_avg = sum(p[2] for p in pixels) / len(pixels)

        h, s, v = colorsys.rgb_to_hsv(r_avg / 255, g_avg / 255, b_avg / 255)
        hue_deg = h * 360

        is_warm_dark = (
            (0 <= hue_deg <= 60 or hue_deg >= 330) and v < 0.4 and s > 0.3
        )

        color_desc = f"H{hue_deg:.0f}° S{s:.2f} V{v:.2f}"
        return color_desc, is_warm_dark
