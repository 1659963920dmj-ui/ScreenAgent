"""历史决策摘要：把 AgentStep 历史压缩为进 prompt 的简短记录。

spec §3.1：每步进 prompt 前按动作类型保留关键参数，默认只取最近 5 步。
target_id 不进入历史（跨截图 id 重编号，无意义）。
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.agent.step import AgentStep
from src.control.actions import Action, ActionType


def summarize_history(
    history: List[AgentStep], max_steps: int = 5
) -> List[Dict[str, Any]]:
    """取最近 max_steps 步，返回可 JSON 序列化的摘要列表。"""
    return [_summarize_step(s) for s in history[-max_steps:]]


def _summarize_step(step: AgentStep) -> Dict[str, Any]:
    if step.status == "action":
        return _summarize_action(step.action)
    if step.status == "done":
        return {"status": "done", "summary": step.summary}
    return {"status": "error", "reason": step.reason}


def _summarize_action(action: Action) -> Dict[str, Any]:
    d: Dict[str, Any] = {"type": action.type.value}
    t = action.type
    if t in (
        ActionType.MOVE,
        ActionType.CLICK,
        ActionType.DOUBLE_CLICK,
        ActionType.RIGHT_CLICK,
    ):
        d["x"] = action.x
        d["y"] = action.y
    elif t == ActionType.SCROLL:
        d["scroll_amount"] = action.scroll_amount
        if action.x is not None:
            d["x"] = action.x
            d["y"] = action.y
    elif t == ActionType.DRAG:
        d["x"] = action.x
        d["y"] = action.y
        d["x2"] = action.x2
        d["y2"] = action.y2
    elif t == ActionType.TYPE:
        d["text"] = (action.text or "")[:50]
    elif t == ActionType.PRESS:
        d["key"] = action.key
    elif t == ActionType.HOTKEY:
        d["keys"] = action.keys
    return d
