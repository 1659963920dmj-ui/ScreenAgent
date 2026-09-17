"""检测结果可视化：在截图上绘制边界框与文字。

本模块输入 / 输出统一使用 RGB 图像（与 screen 模块一致）。
文字标签改用 PIL 绘制以支持中文——OpenCV 的 putText 只支持 ASCII，
会把中文渲染成乱码。四边形框与标签背景条同样由 PIL 绘制，颜色按
(R, G, B) 顺序传入，与 RGB 语义一致。
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .detection import TextDetection, UIElement

# 中文字体候选路径（按平台），首个存在者生效。
# 全部缺失时回退为 PIL 默认位图字体（不支持中文，仅兜底，不抛错）。
_FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",  # Windows 微软雅黑
    "C:/Windows/Fonts/simhei.ttf",  # Windows 黑体
    "/System/Library/Fonts/PingFang.ttc",  # macOS 苹方
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux 兜底
]

_LABEL_FONT_SIZE = 16


@lru_cache(maxsize=None)
def _load_font(size: int) -> Optional[ImageFont.FreeTypeFont]:
    """加载第一个可用的中文字体；全部缺失时返回 None。"""
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return None


def draw_detections(
    image: np.ndarray,
    detections: List[TextDetection],
    color: Tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
    draw_text: bool = True,
) -> np.ndarray:
    """在图像上绘制文字检测框，返回新图像（RGB）。

    Args:
        image: RGB 格式 numpy 数组 (H, W, 3)。
        detections: TextDetection 列表。
        color: 边框颜色 (R, G, B)。
        thickness: 线宽（像素）。
        draw_text: 是否在框上方绘制识别文字（支持中文）。

    Returns:
        绘制后的 RGB 图像。
    """
    bboxes = [d.bbox for d in detections]
    labels = [d.text for d in detections]
    return _draw_boxes(image, bboxes, labels, color, thickness, draw_text)


def draw_elements(
    image: np.ndarray,
    elements: List[UIElement],
    color: Tuple[int, int, int] = (255, 0, 0),
    thickness: int = 2,
) -> np.ndarray:
    """在图像上绘制 UI 元素框，返回新图像（RGB）。"""
    bboxes = [e.bbox for e in elements]
    labels = [e.label for e in elements]
    return _draw_boxes(image, bboxes, labels, color, thickness, True)


def _draw_boxes(
    image: np.ndarray,
    bboxes: List[List[Tuple[int, int]]],
    labels: List[str],
    color: Tuple[int, int, int],
    thickness: int,
    draw_text: bool,
) -> np.ndarray:
    """在 RGB 图像上绘制四边形框与文字标签，返回新图像。

    整张图只做一次 numpy ↔ PIL 转换；框用 ImageDraw.polygon 绘制，
    文字用中文字体绘制并垫一层实心背景条以保证可读性。
    """
    img = Image.fromarray(image)
    draw = ImageDraw.Draw(img)
    font = _load_font(_LABEL_FONT_SIZE)

    for bbox, label in zip(bboxes, labels):
        if not bbox or len(bbox) < 3:
            continue
        pts = [(int(p[0]), int(p[1])) for p in bbox]
        draw.polygon(pts, outline=color, width=max(1, thickness))
        if draw_text and label:
            _draw_label(draw, font, label, color, pts[0])

    return np.asarray(img)


def _draw_label(
    draw: ImageDraw.ImageDraw,
    font: Optional[ImageFont.FreeTypeFont],
    label: str,
    color: Tuple[int, int, int],
    anchor: Tuple[int, int],
) -> None:
    """在 anchor（框左上角）上方绘制文字标签，支持中文。

    标签垫一层框色背景条，文字用黑色，保证在复杂背景上可读；
    贴近图像顶部时下移，避免越界。
    """
    x, y = anchor
    if font is None:
        # 兜底：默认字体不支持中文，直接按框色绘制（英文仍可读）
        draw.text((x, max(y - 14, 2)), label, fill=color)
        return

    left, top, right, bottom = font.getbbox(label)
    tw, th = right - left, bottom - top
    ty = max(y - th - 6, 2)
    draw.rectangle([x, ty, x + tw + 6, ty + th + 6], fill=color)
    draw.text((x + 3, ty + 3), label, font=font, fill=(0, 0, 0))
