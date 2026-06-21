"""图片预处理：校验、压缩"""
import base64
import logging
import os
from io import BytesIO

logger = logging.getLogger(__name__)

MAX_IMAGE_EDGE = 768
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


class ImageProcessor:
    """图片预处理：校验、压缩"""

    @staticmethod
    def preprocess(image_paths: list[str]) -> list[dict]:
        """
        预处理图片列表，返回可传给OCR或Pillow的内容块列表。

        返回: [{"path": str, "pil_image": PIL.Image, "base64": str, "media_type": str}, ...]
        """
        from PIL import Image

        results = []
        for path in image_paths:
            try:
                if not os.path.exists(path):
                    logger.warning(f"Image not found: {path}")
                    continue

                ext = os.path.splitext(path)[1].lower()
                if ext not in SUPPORTED_FORMATS:
                    logger.warning(f"Unsupported image format {ext}: {path}")
                    continue

                img = Image.open(path).convert("RGB")

                # 等比缩放
                w, h = img.size
                if max(w, h) > MAX_IMAGE_EDGE:
                    scale = MAX_IMAGE_EDGE / max(w, h)
                    img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

                # base64编码（供Pillow降级使用）
                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

                results.append({
                    "path": path,
                    "pil_image": img,
                    "base64": b64,
                    "media_type": "image/jpeg",
                })
            except Exception as e:
                logger.warning(f"Preprocess image failed {path}: {e}")
        return results
