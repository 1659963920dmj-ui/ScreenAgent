"""桌面控制模块：鼠标键盘控制与结构化动作执行。"""

from .actions import Action, ActionType
from .controller import Controller
from .keyboard import KeyboardController
from .mouse import MouseController

__all__ = [
    "Action",
    "ActionType",
    "Controller",
    "KeyboardController",
    "MouseController",
]
