"""跨平台屏幕截图模块。

默认使用 mss（高性能截图）作为后端，PyAutoGUI 作为备选。
截图统一返回 RGB 格式的 numpy 数组（H, W, 3），坐标为屏幕绝对像素。

已知限制：在 Windows 高 DPI（显示缩放）下，mss 返回物理像素，
与 PyAutoGUI 的逻辑像素可能不一致，跨分辨率适配在第 6 周专项处理。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


@dataclass
class Screenshot:
    """一次截图的结果，包含图像数据、尺寸与屏幕原点。

    Attributes:
        image: RGB 格式 numpy 数组，shape 为 (H, W, 3)。
        width: 图像宽度（像素）。
        height: 图像高度（像素）。
        left: 截图区域左上角在屏幕上的 x 坐标。
        top: 截图区域左上角在屏幕上的 y 坐标。
    """

    image: np.ndarray
    width: int
    height: int
    left: int = 0
    top: int = 0

    def to_screen(self, x: int, y: int) -> Tuple[int, int]:
        """把图像内坐标转换为屏幕绝对坐标（加上截图原点偏移）。"""
        return (x + self.left, y + self.top)


class ScreenCapture:
    """屏幕截图器，支持全屏与区域截图。"""

    def __init__(self, backend: str = "mss") -> None:
        """初始化截图器。

        Args:
            backend: "mss"（推荐，高性能）或 "pyautogui"（备选）。
        """
        self._mss = None  # 先初始化，确保 __del__ 在任何异常路径下都安全
        if backend == "mss":
            self._backend = "mss"
            import mss

            self._mss = mss.MSS()
        elif backend == "pyautogui":
            self._backend = "pyautogui"
        else:
            raise ValueError(f"未知截图后端: {backend!r}（可选 mss / pyautogui）")

    def capture(self, region: Optional[Tuple[int, int, int, int]] = None) -> Screenshot:
        """截取屏幕。

        Args:
            region: 可选区域 (left, top, width, height)，None 表示全屏。

        Returns:
            Screenshot 对象，image 为 RGB numpy 数组，left/top 记录截图原点。
        """
        if self._backend == "mss":
            return self._capture_mss(region)
        return self._capture_pyautogui(region)

    def _capture_mss(self, region: Optional[Tuple[int, int, int, int]]) -> Screenshot:
        if region is None:
            monitor = self._mss.monitors[1]  # 主显示器
            left, top = monitor["left"], monitor["top"]
            width, height = monitor["width"], monitor["height"]
        else:
            left, top, width, height = region

        shot = self._mss.grab(
            {"left": left, "top": top, "width": width, "height": height}
        )
        # mss 返回 BGRA（4 通道），取前 3 通道并反转为 RGB
        img = np.asarray(shot, dtype=np.uint8)
        img = img[:, :, :3][:, :, ::-1].copy()
        return Screenshot(image=img, width=width, height=height, left=left, top=top)

    def _capture_pyautogui(self, region: Optional[Tuple[int, int, int, int]]) -> Screenshot:
        import pyautogui

        if region is None:
            left, top = 0, 0
            img = pyautogui.screenshot()  # PIL Image，RGB
        else:
            left, top, width, height = region
            img = pyautogui.screenshot(region=(left, top, width, height))
        return Screenshot(
            image=np.asarray(img), width=img.width, height=img.height, left=left, top=top
        )

    def screen_size(self) -> Tuple[int, int]:
        """返回主显示器分辨率 (width, height)。"""
        if self._backend == "mss":
            monitor = self._mss.monitors[1]
            return (monitor["width"], monitor["height"])
        import pyautogui

        return pyautogui.size()

    def close(self) -> None:
        """释放底层资源。"""
        if self._mss is not None:
            try:
                self._mss.close()
            except Exception:
                pass
            self._mss = None

    def __del__(self) -> None:
        self.close()
