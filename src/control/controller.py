"""统一控制器：根据结构化 Action 分发执行，并记录日志。

Controller 是控制模块的唯一对外入口，上层（第 4 周 Agent 框架）只需构造
Action 并调用 execute()，无需关心底层鼠标键盘实现。
"""

from __future__ import annotations

import logging
from typing import Optional

from .actions import Action, ActionType
from .keyboard import KeyboardController
from .mouse import MouseController

logger = logging.getLogger(__name__)


class Controller:
    """桌面控制统一入口。"""

    def __init__(
        self,
        mouse: Optional[MouseController] = None,
        keyboard: Optional[KeyboardController] = None,
    ) -> None:
        """初始化控制器。

        Args:
            mouse: 鼠标控制器（默认新建）。
            keyboard: 键盘控制器（默认新建）。
        """
        self.mouse = mouse or MouseController()
        self.keyboard = keyboard or KeyboardController()

    def execute(self, action: Action) -> None:
        """执行一个动作。

        Args:
            action: 结构化动作描述。

        Raises:
            ValueError: 动作参数不合法。
        """
        action.validate()
        logger.info("执行动作: %s", action)
        t = action.type

        if t == ActionType.MOVE:
            self.mouse.move(action.x, action.y, duration=action.duration)
        elif t == ActionType.CLICK:
            self.mouse.click(action.x, action.y)
        elif t == ActionType.DOUBLE_CLICK:
            self.mouse.double_click(action.x, action.y)
        elif t == ActionType.RIGHT_CLICK:
            self.mouse.right_click(action.x, action.y)
        elif t == ActionType.SCROLL:
            self.mouse.scroll(action.scroll_amount or 0, x=action.x, y=action.y)
        elif t == ActionType.DRAG:
            self.mouse.drag(
                action.x, action.y, action.x2, action.y2, duration=action.duration
            )
        elif t == ActionType.TYPE:
            self.keyboard.type_text(action.text or "")
        elif t == ActionType.PRESS:
            self.keyboard.press(action.key or "")
        elif t == ActionType.HOTKEY:
            self.keyboard.hotkey(*(action.keys or []))
        else:
            raise ValueError(f"未知动作类型: {t}")
