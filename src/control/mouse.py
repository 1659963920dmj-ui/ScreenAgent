"""鼠标控制模块，基于 PyAutoGUI。

坐标统一为屏幕绝对像素。注意：PyAutoGUI 默认开启 fail-safe 机制，
鼠标移动到屏幕左上角 (0, 0) 会抛出异常以中止自动化，这是保护特性，勿关闭。
"""

from __future__ import annotations

from typing import Optional


class MouseController:
    """鼠标操作封装：移动、点击、双击、右键、滚动、拖拽。"""

    def __init__(self, auto_delay: float = 0.1) -> None:
        """初始化鼠标控制器。

        Args:
            auto_delay: 每次操作间的全局自动延迟（秒），降低误操作风险。
        """
        import pyautogui

        self._pg = pyautogui
        pyautogui.PAUSE = auto_delay

    def move(self, x: int, y: int, duration: float = 0.2) -> None:
        """移动鼠标到 (x, y)。"""
        self._pg.moveTo(x, y, duration=duration)

    def click(self, x: Optional[int] = None, y: Optional[int] = None) -> None:
        """左键单击；未给坐标时在当前位置点击。"""
        self._pg.click(x=x, y=y)

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> None:
        """左键双击。"""
        self._pg.doubleClick(x=x, y=y)

    def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> None:
        """右键单击。"""
        self._pg.rightClick(x=x, y=y)

    def scroll(self, amount: int, x: Optional[int] = None, y: Optional[int] = None) -> None:
        """滚动鼠标滚轮。

        Args:
            amount: 滚动量（单位），正数向上滚、负数向下滚。
            x, y: 滚动发生位置（可选）。
        """
        self._pg.scroll(amount, x=x, y=y)

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.3) -> None:
        """从 (x1, y1) 拖拽到 (x2, y2)。"""
        self._pg.moveTo(x1, y1)
        self._pg.dragTo(x2, y2, duration=duration)
