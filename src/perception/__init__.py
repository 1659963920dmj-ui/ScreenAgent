"""桌面感知模块：屏幕截图、OCR 识别、UI 元素定位与可视化。"""

from .describe import describe_elements, elements_to_dicts
from .detection import TextDetection, UIElement, merge_text_and_elements
from .detector import UIElementDetector
from .ocr import OCREngine
from .screen import ScreenCapture, Screenshot
from .visualize import draw_detections, draw_elements

__all__ = [
    "TextDetection",
    "UIElement",
    "merge_text_and_elements",
    "UIElementDetector",
    "describe_elements",
    "elements_to_dicts",
    "ScreenCapture",
    "Screenshot",
    "OCREngine",
    "draw_detections",
    "draw_elements",
]
