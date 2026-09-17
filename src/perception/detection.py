"""感知模块数据结构：OCR 检测结果与 UI 元素。

坐标约定：bbox 使用「图像坐标」——即输入给 OCR/检测器的图像的像素坐标，
原点在图像左上角，x 向右、y 向下。对全屏截图，图像坐标恰等于屏幕绝对坐标；
对区域截图（Screenshot.left/top 非 0），两者不同，执行点击前需用
Screenshot.to_screen() 把图像坐标转换为屏幕绝对坐标。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


def _center_of(bbox: List[Tuple[int, int]]) -> Tuple[int, int]:
    """计算四边形边界框的中心点（各顶点坐标的平均）。"""
    if not bbox:
        return (0, 0)
    xs = [p[0] for p in bbox]
    ys = [p[1] for p in bbox]
    return (int(sum(xs) / len(xs)), int(sum(ys) / len(ys)))


@dataclass
class TextDetection:
    """OCR 检测到的一段文字。

    Attributes:
        text: 识别出的文字内容。
        bbox: 四点坐标（左上、右上、右下、左下），可为倾斜四边形。
        confidence: 识别置信度，范围 [0, 1]。
    """

    text: str
    bbox: List[Tuple[int, int]]
    confidence: float = 1.0

    @property
    def center(self) -> Tuple[int, int]:
        """边界框中心坐标（图像坐标），点击前需用 to_screen() 转屏幕坐标。"""
        return _center_of(self.bbox)

    @property
    def width(self) -> int:
        """边界框外接矩形宽度。"""
        xs = [p[0] for p in self.bbox]
        return max(xs) - min(xs)

    @property
    def height(self) -> int:
        """边界框外接矩形高度。"""
        ys = [p[1] for p in self.bbox]
        return max(ys) - min(ys)


@dataclass
class UIElement:
    """屏幕上的一个可交互 UI 元素（文字或视觉检测结果）。

    Attributes:
        label: 元素标签（如文字内容或类型描述）。
        bbox: 四点坐标。
        element_type: 元素类型，如 "text"、"button"、"icon"。
        confidence: 检测置信度。
    """

    label: str
    bbox: List[Tuple[int, int]]
    element_type: str = "text"
    confidence: float = 1.0

    @property
    def center(self) -> Tuple[int, int]:
        """元素中心坐标（图像坐标），点击前需用 to_screen() 转屏幕坐标。"""
        return _center_of(self.bbox)


def merge_text_and_elements(
    texts: List[TextDetection],
    elements: List[UIElement],
) -> List[UIElement]:
    """把 OCR 文字框合并进视觉 UI 元素，返回完整的元素列表。

    合并规则：
    1. 每段文字归属给「中心点落在其 bbox 内、且面积最小」的视觉元素
       （即最紧密包围它的控件），避免大框抢走嵌套小控件的文字标签。
    2. 每个元素把归属其下的文字拼接为 label；无文字回退为类型名（如 "button"）。
    3. 归属了任一元素的文字框不再单独出现；未被归属的保留为独立 text 元素。
    4. 同类型视觉元素 IoU > 0.7 时去重（保留面积大者）。

    纯几何逻辑，不依赖 OpenCV，可脱离真实屏幕单元测试。

    Args:
        texts: OCR 识别的文字框列表。
        elements: 视觉检测的元素列表（button / input / icon）。

    Returns:
        合并后的 UIElement 列表（含 text 元素，label 已填充）。
    """
    deduped = _dedupe_elements(elements)

    # 每段文字 → 最紧密包围它的非 text 元素下标（面积最小者）
    owner: List[Optional[int]] = [None] * len(texts)
    for i, det in enumerate(texts):
        cx, cy = _center_of(det.bbox)
        best: Optional[int] = None
        best_area: Optional[int] = None
        for j, elem in enumerate(deduped):
            if elem.element_type == "text":
                continue
            x1, y1, x2, y2 = _bbox_rect(elem.bbox)
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                area = _rect_area(elem.bbox)
                if best_area is None or area < best_area:
                    best = j
                    best_area = area
        owner[i] = best

    # 汇总每个元素归属的文字
    labels_by_elem: Dict[int, List[str]] = {}
    for i, j in enumerate(owner):
        if j is not None:
            labels_by_elem.setdefault(j, []).append(texts[i].text)

    merged: List[UIElement] = []
    for j, elem in enumerate(deduped):
        if elem.element_type == "text":
            merged.append(elem)
            continue
        parts = labels_by_elem.get(j)
        label = " ".join(parts) if parts else (elem.label or elem.element_type)
        merged.append(
            UIElement(
                label=label,
                bbox=elem.bbox,
                element_type=elem.element_type,
                confidence=elem.confidence,
            )
        )

    # 未被归属的文字框保留为独立 text 元素
    for i, det in enumerate(texts):
        if owner[i] is None:
            merged.append(
                UIElement(
                    label=det.text,
                    bbox=det.bbox,
                    element_type="text",
                    confidence=det.confidence,
                )
            )
    return merged


def _dedupe_elements(elements: List[UIElement]) -> List[UIElement]:
    """同类型元素 IoU > 0.7 时去重，保留面积大者。"""
    result: List[UIElement] = []
    for elem in sorted(elements, key=lambda e: _rect_area(e.bbox), reverse=True):
        duplicate = any(
            other.element_type == elem.element_type
            and _iou(elem.bbox, other.bbox) > 0.7
            for other in result
        )
        if not duplicate:
            result.append(elem)
    return result


def _bbox_rect(bbox: List[Tuple[int, int]]) -> Tuple[int, int, int, int]:
    """返回边界框的外接矩形 (x1, y1, x2, y2)，x2/y2 为最大坐标（含）。"""
    xs = [p[0] for p in bbox]
    ys = [p[1] for p in bbox]
    return (min(xs), min(ys), max(xs), max(ys))


def _rect_area(bbox: List[Tuple[int, int]]) -> int:
    x1, y1, x2, y2 = _bbox_rect(bbox)
    return max(0, x2 - x1) * max(0, y2 - y1)


def _iou(a: List[Tuple[int, int]], b: List[Tuple[int, int]]) -> float:
    """两个边界框的交并比（IoU），范围 [0, 1]。

    判断「重复框」用 IoU 而非「交集 / 较小框面积」：后者在父子包含关系下
    恒为 1（如 200×40 输入框内嵌 20×20 图标），会把父控件误当成子控件的重复
    而删除。IoU 下包含关系的值 = 子面积 / 父面积，远小于 1，两类关系可区分。
    """
    ax1, ay1, ax2, ay2 = _bbox_rect(a)
    bx1, by1, bx2, by2 = _bbox_rect(b)
    iw = max(0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    if inter == 0:
        return 0.0
    union = _rect_area(a) + _rect_area(b) - inter
    return inter / union
