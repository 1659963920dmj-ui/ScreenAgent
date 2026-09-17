"""结构化屏幕描述：把 UI 元素列表格式化为供模型 / 程序消费的描述。

感知链路最后一环（PRD P-4）：
    截图 → OCR + 视觉检测 → merge → 本模块输出结构化描述
下游 Agent 据此生成点击动作。

坐标约定：输出统一为「屏幕绝对坐标」（图像坐标 + 截图原点偏移），
下游可直接用于点击；编号从 1 开始，按阅读顺序（y 优先、x 次之）排列，
符合模型对屏幕自上而下、自左而右的视觉理解。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .detection import UIElement


def elements_to_dicts(
    elements: List[UIElement], left: int = 0, top: int = 0
) -> List[Dict[str, Any]]:
    """把 UI 元素列表转成结构化字典（可 JSON 序列化），按阅读顺序排序。

    Args:
        elements: 合并后的 UIElement 列表。
        left: 截图区域左上角的屏幕 x 坐标（图像坐标 → 屏幕坐标的偏移）。
        top: 截图区域左上角的屏幕 y 坐标。

    Returns:
        字典列表，每项含 id / type / label / center / bbox / confidence，
        坐标为屏幕绝对坐标。
    """
    ordered = sorted(elements, key=lambda e: (e.center[1], e.center[0]))
    result: List[Dict[str, Any]] = []
    for i, e in enumerate(ordered, start=1):
        result.append(
            {
                "id": i,
                "type": e.element_type,
                "label": _clean_label(e.label),
                "center": [e.center[0] + left, e.center[1] + top],
                "bbox": [[x + left, y + top] for x, y in e.bbox],
                "confidence": round(float(e.confidence), 4),
            }
        )
    return result


def describe_elements(
    elements: List[UIElement],
    width: int,
    height: int,
    left: int = 0,
    top: int = 0,
    screen_size: Optional[Tuple[int, int]] = None,
) -> str:
    """生成编号文本列表描述，供多模态模型消费。

    头部始终输出「截图尺寸 + 截图原点」，并标注坐标为屏幕绝对坐标：
        截图尺寸: 100x100 @ (0, 0)
        坐标: 屏幕绝对坐标
        [1] text    "确定"  @ (20, 30)

    仅当显式传入 `screen_size`（真实屏幕尺寸）时，额外在头部输出屏幕尺寸：
        屏幕尺寸: 2560x1440
        截图尺寸: 100x100 @ (0, 0)
        坐标: 屏幕绝对坐标
        [1] ...

    不根据 left/top 是否为零推断「全屏」——原点 (0,0) 的区域截图并非全屏，
    那样会把截图尺寸误写成整个屏幕尺寸。只有调用方显式给出屏幕尺寸时才输出。

    Args:
        elements: 合并后的 UIElement 列表。
        width: 截图宽度（像素）。
        height: 截图高度（像素）。
        left: 截图区域左上角的屏幕 x 坐标。
        top: 截图区域左上角的屏幕 y 坐标。
        screen_size: 可选，真实屏幕尺寸 (宽, 高)，传入时头部额外输出屏幕尺寸。

    Returns:
        编号文本描述，元素按阅读顺序排列。
    """
    items = elements_to_dicts(elements, left=left, top=top)
    lines: List[str] = []
    if screen_size is not None:
        lines.append(f"屏幕尺寸: {screen_size[0]}x{screen_size[1]}")
    lines.append(f"截图尺寸: {width}x{height} @ ({left}, {top})")
    lines.append("坐标: 屏幕绝对坐标")
    for d in items:
        lines.append(
            f"[{d['id']}] {d['type']:<6} \"{d['label']}\" @ "
            f"({d['center'][0]}, {d['center'][1]})"
        )
    return "\n".join(lines)


def _clean_label(label: str) -> str:
    """把标签中的换行 / 制表符 / 连续空白压成单个空格，避免破坏行格式。"""
    return " ".join(str(label).split())
