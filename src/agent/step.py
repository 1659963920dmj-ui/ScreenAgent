"""Agent 单步输出数据结构。

三态（status）互斥：
- "action"：action 非 None，summary / reason / error_kind 为 None；
- "done"：summary 非 None，action / reason / error_kind 为 None；
- "error"：reason 与 error_kind（"model"/"parse"）非 None，action / summary 为 None。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from src.control.actions import Action


@dataclass
class AgentStep:
    """Agent 单步决策结果。understanding / plan 三态恒有（可能为空串）。"""

    status: Literal["action", "done", "error"]
    understanding: str
    plan: str
    action: Optional[Action] = None
    summary: Optional[str] = None
    reason: Optional[str] = None
    error_kind: Optional[Literal["model", "parse"]] = None

    def validate(self) -> None:
        """严格对象校验：status 合法、三态互斥字段匹配、error_kind 一致。

        status == "action" 时内部调用 action.validate()。
        不合法组合抛 ValueError（区别于解析层的宽容处理）。
        """
        if self.status not in ("action", "done", "error"):
            raise ValueError(
                f"status 必须是 'action'/'done'/'error'，收到 {self.status!r}"
            )
        if not isinstance(self.understanding, str):
            raise ValueError(
                f"understanding 必须是 str，收到 {type(self.understanding).__name__}"
            )
        if not isinstance(self.plan, str):
            raise ValueError(f"plan 必须是 str，收到 {type(self.plan).__name__}")

        if self.status == "action":
            if self.action is None:
                raise ValueError("status='action' 时 action 不能为 None")
            if (
                self.summary is not None
                or self.reason is not None
                or self.error_kind is not None
            ):
                raise ValueError(
                    "status='action' 时 summary/reason/error_kind 必须为 None"
                )
            self.action.validate()
        elif self.status == "done":
            if self.summary is None:
                raise ValueError("status='done' 时 summary 不能为 None")
            if (
                self.action is not None
                or self.reason is not None
                or self.error_kind is not None
            ):
                raise ValueError(
                    "status='done' 时 action/reason/error_kind 必须为 None"
                )
        else:  # error
            if self.reason is None:
                raise ValueError("status='error' 时 reason 不能为 None")
            if self.error_kind not in ("model", "parse"):
                raise ValueError(
                    "status='error' 时 error_kind 必须是 'model'/'parse'，"
                    f"收到 {self.error_kind!r}"
                )
            if self.action is not None or self.summary is not None:
                raise ValueError("status='error' 时 action/summary 必须为 None")
