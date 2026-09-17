"""UI 元素视觉检测模块（第 2 周：OpenCV 启发式粗版）。

用两个与主题无关的视觉特征识别可交互元素：
- 输入框 / 按钮：矩形边框（Canny 边缘 → 闭合四边形），按长宽比分类；
- 图标：高饱和度彩色区域（HSV），无论浅色 / 深色主题的彩色图标都能检出。

对浅色主题下「白色填充输入框」同样有效——其矩形边界也会被 Canny 检出。

已知局限：纯启发式无法可靠区分「按钮 vs 面板」「图标 vs 彩色装饰」，
误检率较高，故用 confidence 表达不确定性。第 6 周「感知准确率优化」
会替换内部实现为深度学习目标检测，detect() 接口保持不变。

坐标约定：返回的 bbox 为「图像坐标」，与 detection.py 一致；点击前
需用 Screenshot.to_screen() 转为屏幕绝对坐标。
"""

from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np

from .detection import UIElement, _iou


class UIElementDetector:
    """基于 OpenCV 的 UI 元素检测器（启发式，第 2 周粗版）。"""

    # 矩形边框的尺寸上限：更大的闭合四边形是窗口 / 面板 / 工具栏，不是可交互元素。
    _MAX_W = 250
    _MAX_H = 80
    _MIN_W = 20
    _MIN_H = 15
    # 输入框判定：长宽比超过该值视为横向长条输入框，否则为按钮。
    _INPUT_ASPECT = 2.5

    def detect(self, image: np.ndarray) -> List[UIElement]:
        """检测图像中的 UI 元素。

        Args:
            image: RGB 格式 numpy 数组 (H, W, 3)。

        Returns:
            UIElement 列表（element_type 为 "input" / "button" / "icon"）。
            空图 / 无法检测时返回空列表，不抛异常。
        """
        if image is None or image.size == 0 or image.ndim != 3:
            return []
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)

        icons = self._detect_color_icons(hsv)
        # 彩色图标的矩形边缘也会被 Canny 检出，需排除，避免同一区域重复判为 button。
        # 用 IoU 而非「交集/较小框面积」：后者会把「内含图标的大控件」误判为图标重复
        # 而删除（如输入框内嵌小图标时重叠率=1）；IoU 下包含关系值很小，不受影响。
        borders = [
            r
            for r in self._detect_rect_borders(gray)
            if not any(_iou(self._rect_bbox(*r), e.bbox) > 0.7 for e in icons)
        ]
        return self._classify_borders(borders) + icons

    # ---- 矩形边框（输入框 / 按钮） ----

    def _detect_rect_borders(self, gray: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Canny 边缘中的闭合四边形 → 尺寸过滤 → 去重，返回 (x, y, w, h)。"""
        edges = cv2.Canny(gray, 50, 150)
        # RETR_LIST 检出所有层次轮廓，避免漏掉嵌在面板内部的输入框边框
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        rects: List[Tuple[int, int, int, int]] = []
        for c in contours:
            approx = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
            if len(approx) != 4:
                continue
            x, y, w, h = cv2.boundingRect(c)
            if not (self._MIN_W <= w <= self._MAX_W and self._MIN_H <= h <= self._MAX_H):
                continue
            rects.append((x, y, w, h))
        return self._dedupe_rects(rects)

    def _classify_borders(
        self, rects: List[Tuple[int, int, int, int]]
    ) -> List[UIElement]:
        """按长宽比把矩形边框分为 input（横向长条）与 button。"""
        elements: List[UIElement] = []
        for x, y, w, h in rects:
            aspect = w / h
            if aspect >= self._INPUT_ASPECT:
                elements.append(
                    self._make("input", x, y, w, h, self._aspect_confidence(aspect, ideal=5.0))
                )
            else:
                elements.append(
                    UIElement(
                        label="button",
                        bbox=self._rect_bbox(x, y, w, h),
                        element_type="button",
                        confidence=0.55,
                    )
                )
        return elements

    # ---- 彩色图标 ----

    def _detect_color_icons(self, hsv: np.ndarray) -> List[UIElement]:
        """高饱和度彩色区域 → icon（覆盖深色 / 浅色主题的彩色图标）。

        饱和度阈值取 180：任务栏 / 桌面图标饱和度中位数约 200，而网页里的
        彩色文字、图片、按钮等噪声多在 80~150，抬高阈值能大幅减少把网页
        内容误判为图标。
        """
        mask = cv2.inRange(hsv, (0, 180, 80), (180, 255, 255))
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        elements: List[UIElement] = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            ca = cv2.contourArea(c)
            if not (200 <= ca <= 2500):
                continue
            if not (0.5 <= w / h <= 2.5):
                continue
            fill = ca / max(1.0, w * h)
            if fill < 0.3:
                continue  # 排除空心彩色边框
            conf = 0.4 + 0.5 * min(1.0, fill)
            elements.append(self._make("icon", x, y, w, h, conf))
        return elements

    # ---- 工具 ----

    def _dedupe_rects(
        self, rects: List[Tuple[int, int, int, int]]
    ) -> List[Tuple[int, int, int, int]]:
        """合并重叠的矩形边框（边框的内外边缘会产生重复候选），保留面积大者。"""
        result: List[Tuple[int, int, int, int]] = []
        for r in sorted(rects, key=lambda r: r[2] * r[3], reverse=True):
            bbox = self._rect_bbox(*r)
            if any(
                _iou(bbox, self._rect_bbox(*other)) > 0.7 for other in result
            ):
                continue
            result.append(r)
        return result

    @staticmethod
    def _make(
        element_type: str, x: int, y: int, w: int, h: int, confidence: float
    ) -> UIElement:
        bbox = UIElementDetector._rect_bbox(x, y, w, h)
        return UIElement(
            label=element_type,
            bbox=bbox,
            element_type=element_type,
            confidence=round(float(confidence), 2),
        )

    @staticmethod
    def _rect_bbox(x: int, y: int, w: int, h: int) -> List[Tuple[int, int]]:
        """外接矩形 → 四点坐标（左上、右上、右下、左下）。"""
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]

    @staticmethod
    def _aspect_confidence(value: float, ideal: float) -> float:
        """长宽比偏离理想值越远，置信度越低（下限 0.4）。"""
        return max(0.4, 1.0 - abs(value - ideal) / ideal)
