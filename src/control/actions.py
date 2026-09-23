"""动作数据结构。

设计原则：动作（Action，纯数据）与执行（Controller，副作用）分离。
Action 可校验、可日志、可序列化、可单元测试，为第 4 周 Agent 框架集成
做铺垫——Agent 产出结构化 Action，控制模块负责执行。
"""

from __future__ import annotations

import math

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from .keys import ALLOWED_KEYS


class ActionType(str, Enum):
    """桌面动作类型。"""

    MOVE = "move"                    # 移动鼠标到 (x, y)
    CLICK = "click"                  # 左键单击 (x, y)
    DOUBLE_CLICK = "double_click"    # 左键双击 (x, y)
    RIGHT_CLICK = "right_click"      # 右键单击 (x, y)
    SCROLL = "scroll"                # 滚动（scroll_amount 正向上、负向下）
    DRAG = "drag"                    # 从 (x, y) 拖拽到 (x2, y2)
    TYPE = "type"                    # 输入文本
    PRESS = "press"                  # 按下并释放单个按键
    HOTKEY = "hotkey"                # 组合键，如 ["ctrl", "c"]


@dataclass
class Action:
    """一个待执行的桌面动作。

    字段按动作类型按需取用：
    - MOVE / CLICK / DOUBLE_CLICK / RIGHT_CLICK：x, y
    - SCROLL：scroll_amount（必填），x, y（滚动发生位置，可选）
    - DRAG：x, y（起点），x2, y2（终点）
    - TYPE：text
    - PRESS：key
    - HOTKEY：keys
    """

    type: ActionType
    x: Optional[int] = None
    y: Optional[int] = None
    x2: Optional[int] = None
    y2: Optional[int] = None
    text: Optional[str] = None
    key: Optional[str] = None
    keys: Optional[List[str]] = None
    scroll_amount: Optional[int] = None
    duration: float = 0.2  # 移动 / 拖拽耗时（秒）
    target_id: Optional[int] = None  # 模型指代的 screen_state 元素编号，仅日志/调试

    def validate(self) -> None:
        """校验动作参数的类型与完整性，不合法时抛出 ValueError。

        除必填字段外，还校验字段类型，防止错误模型输出（如把字符串传给
        keys 或坐标）进入键鼠执行层。
        """
        if not isinstance(self.type, ActionType):
            raise ValueError(
                f"动作 type 必须是 ActionType，收到 {type(self.type).__name__}"
            )

        # 坐标字段须为真整数（拒绝 bool——bool 是 int 子类但非合法坐标）
        for name in ("x", "y", "x2", "y2"):
            val = getattr(self, name)
            if val is not None and (isinstance(val, bool) or not isinstance(val, int)):
                raise ValueError(
                    f"{self.type.value} 动作的 {name} 必须是 int，"
                    f"收到 {type(val).__name__}"
                )

        # duration 须为有限非负数值
        if isinstance(self.duration, bool) or not isinstance(self.duration, (int, float)):
            raise ValueError(
                f"{self.type.value} 动作的 duration 必须是数值，"
                f"收到 {type(self.duration).__name__}"
            )
        if not math.isfinite(self.duration) or self.duration < 0:
            raise ValueError(f"{self.type.value} 动作的 duration 必须有限且非负")

        t = self.type
        if t in (
            ActionType.MOVE,
            ActionType.CLICK,
            ActionType.DOUBLE_CLICK,
            ActionType.RIGHT_CLICK,
        ):
            if self.x is None or self.y is None:
                raise ValueError(f"{t.value} 动作需要 x、y 坐标")
        elif t == ActionType.SCROLL:
            if self.scroll_amount is None:
                raise ValueError("SCROLL 动作需要 scroll_amount")
            if not isinstance(self.scroll_amount, int):
                raise ValueError(
                    f"SCROLL 动作的 scroll_amount 必须是 int，"
                    f"收到 {type(self.scroll_amount).__name__}"
                )
        elif t == ActionType.DRAG:
            if None in (self.x, self.y, self.x2, self.y2):
                raise ValueError("DRAG 动作需要 x、y、x2、y2")
        elif t == ActionType.TYPE:
            if self.text is None:
                raise ValueError("TYPE 动作需要 text")
            if not isinstance(self.text, str):
                raise ValueError(
                    f"TYPE 动作的 text 必须是 str，收到 {type(self.text).__name__}"
                )
        elif t == ActionType.PRESS:
            if self.key is None:
                raise ValueError("PRESS 动作需要 key")
            if not isinstance(self.key, str):
                raise ValueError(
                    f"PRESS 动作的 key 必须是 str，收到 {type(self.key).__name__}"
                )
            if self.key not in ALLOWED_KEYS:
                raise ValueError(f"PRESS 动作的 key {self.key!r} 不在键名白名单")
        elif t == ActionType.HOTKEY:
            if (
                not isinstance(self.keys, list)
                or not self.keys
                or not all(isinstance(k, str) for k in self.keys)
            ):
                raise ValueError("HOTKEY 动作需要非空字符串列表 keys")
            for k in self.keys:
                if k not in ALLOWED_KEYS:
                    raise ValueError(f"HOTKEY 动作的 key {k!r} 不在键名白名单")
