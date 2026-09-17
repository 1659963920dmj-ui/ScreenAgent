"""OCR 文字识别模块。

封装 PaddleOCR 与 EasyOCR，提供统一接口：
    recognize(image: np.ndarray) -> List[TextDetection]

模型采用懒加载：首次调用 recognize 时才初始化（可能触发权重下载），
避免 import 本模块与运行单元测试时过慢。
"""

from __future__ import annotations

from typing import List

import numpy as np

from .detection import TextDetection

# EasyOCR 与 PaddleOCR 的语言代码缩写不同，需做映射。
# "ch" 是 PaddleOCR 的中英混合约定，EasyOCR 需拆分为简体中文 + 英文。
_EASYOCR_LANG_MAP = {
    "ch": ["ch_sim", "en"],
    "en": ["en"],
}


class OCREngine:
    """OCR 引擎统一封装，屏蔽 PaddleOCR / EasyOCR 的接口差异。"""

    def __init__(self, engine: str = "paddle", lang: str = "ch", lazy: bool = True) -> None:
        """初始化 OCR 引擎。

        Args:
            engine: "paddle" 或 "easy"。
            lang: 语言代码，如 "ch"（中英文）、"en"。
            lazy: True 时延迟加载模型（首次 recognize 才加载）。
        """
        if engine not in ("paddle", "easy"):
            raise ValueError(f"未知 OCR 引擎: {engine!r}（可选 paddle / easy）")
        self.engine = engine
        self.lang = lang
        self._ocr = None
        if not lazy:
            self._load()

    def _load(self) -> None:
        """加载底层 OCR 模型（可能下载权重，耗时较长）。"""
        if self._ocr is not None:
            return
        if self.engine == "paddle":
            from paddleocr import PaddleOCR

            # PaddleOCR 3.x 已移除 use_angle_cls / show_log 参数，直接按 lang 初始化。
            # CPU 上 3.x 默认启用 MKLDNN，但 paddle 3.3.1 的 PIR + oneDNN 处理
            # PP-OCRv6 模型会抛 ConvertPirAttribute2RuntimeAttribute 未实现错误，
            # 故显式禁用 MKLDNN，改走纯 paddle 后端（对 GPU 用户无影响）。
            self._ocr = PaddleOCR(lang=self.lang, enable_mkldnn=False)
        else:
            import easyocr

            self._ocr = easyocr.Reader(self._easyocr_langs())

    def _easyocr_langs(self) -> List[str]:
        """将统一 lang 缩写映射为 EasyOCR 语言代码列表。

        默认 "ch" 表示中英混合，映射为 ["ch_sim", "en"]；其余透传，
        兼容用户直接传入 EasyOCR 原生代码（如 "ch_sim"、"ja"）。
        """
        return _EASYOCR_LANG_MAP.get(self.lang, [self.lang])

    def recognize(self, image: np.ndarray) -> List[TextDetection]:
        """识别图像中的文字。

        Args:
            image: RGB 格式 numpy 数组 (H, W, 3)。

        Returns:
            TextDetection 列表（按检测顺序排列）。
        """
        self._load()
        if self.engine == "paddle":
            return self._recognize_paddle(image)
        return self._recognize_easy(image)

    def _recognize_paddle(self, image: np.ndarray) -> List[TextDetection]:
        # PaddleOCR 输入为 BGR
        bgr = image[:, :, ::-1]
        detections: List[TextDetection] = []

        # PaddleOCR 3.x 使用 predict() 接口，异常直接抛出以暴露真实错误
        # （显存不足、结果解析错误等）。3.x 的 ocr() 只是转调 predict()，
        # 不会切换 2.x 实现，故不再做吞异常后的回退。
        #
        # 3.x 默认 use_doc_preprocessor=True / use_textline_orientation=True，
        # 会先对图像做文档方向分类与透视矫正，返回的坐标落在矫正后坐标系里，
        # 与屏幕截图不对齐。桌面截图文字方向是正的，显式关闭这两项，让检测
        # 直接作用于原图，保证 bbox 即原图像素坐标。
        result = self._ocr.predict(
            bgr,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        for res in result:
            texts = res.get("rec_texts", [])
            scores = res.get("rec_scores", [])
            polys = res.get("rec_polys", res.get("dt_polys", []))
            for box, text, conf in zip(polys, texts, scores):
                bbox = [(int(float(p[0])), int(float(p[1]))) for p in box]
                detections.append(
                    TextDetection(text=str(text), bbox=bbox, confidence=float(conf))
                )
        return detections

    def _recognize_easy(self, image: np.ndarray) -> List[TextDetection]:
        detections: List[TextDetection] = []
        for box, text, conf in self._ocr.readtext(image):
            bbox = [(int(float(p[0])), int(float(p[1]))) for p in box]
            detections.append(
                TextDetection(text=str(text), bbox=bbox, confidence=float(conf))
            )
        return detections
