"""Agent 输出解析：把模型返回的 JSON 文本解析并校验成 AgentStep。

宽容解析（spec §5.1）：模型 JSON 允许冗余字段（丢弃、不报错），
任何解析/校验失败都映射为 AgentStep(status="error", error_kind="parse")，
不抛异常（模型输出不可控）。
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, Optional, Tuple

from src.agent.step import AgentStep
from src.control.actions import Action, ActionType


def parse_step(json_text: str, bounds: Tuple[int, int, int, int]) -> AgentStep:
    """解析模型输出为 AgentStep。

    Args:
        json_text: 模型返回的原始文本，应能 json.loads 为一个对象。
            不做围栏提取（spec §5.1 第 1 条：文本须直接解析为 JSON 对象；
            围栏剥离属 prompt 模板层职责，spec §11 范围外）。
        bounds: 截图区域边界 (left, top, width, height)，坐标须落在
            [left, left+width) × [top, top+height) 内。由未来 step()
            从 Screenshot 提取 (shot.left, shot.top, shot.width, shot.height)。

    Returns:
        AgentStep；解析/校验失败返回 error_kind="parse"，不抛异常。
    """
    left, top, width, height = bounds

    def fail(reason: str) -> AgentStep:
        return AgentStep(
            status="error", understanding="", plan="", reason=reason,
            error_kind="parse",
        )

    # 1. 根解析
    try:
        obj = json.loads(json_text)
    except (json.JSONDecodeError, TypeError):
        return fail("模型输出不是合法 JSON")
    if not isinstance(obj, dict):
        return fail("JSON 根不是对象")

    # 2. status
    status = obj.get("status")
    if not isinstance(status, str) or status not in ("action", "done", "error"):
        return fail(f"status 非法: {status!r}")

    # 3. understanding / plan 兜底
    understanding = obj.get("understanding")
    plan = obj.get("plan")
    if not isinstance(understanding, str):
        understanding = ""
    if not isinstance(plan, str):
        plan = ""

    # 4. 按 status 构造
    if status == "action":
        action = _build_action(obj.get("action"), bounds)
        if action is None:
            return fail("action 非法")
        return AgentStep(
            status="action", understanding=understanding, plan=plan, action=action,
        )
    if status == "done":
        summary = obj.get("summary")
        if not isinstance(summary, str) or summary == "":
            return fail("done 态 summary 必须是非空字符串")
        return AgentStep(
            status="done", understanding=understanding, plan=plan, summary=summary,
        )
    # error（模型主动失败）
    reason = obj.get("reason")
    if not isinstance(reason, str) or reason == "":
        reason = "未知错误"
    return AgentStep(
        status="error", understanding=understanding, plan=plan,
        reason=reason, error_kind="model",
    )


def _build_action(raw: Any, bounds: Tuple[int, int, int, int]) -> Optional[Action]:
    """从 JSON action 对象构造 Action；任一规则失败返回 None（→ error(parse)）。"""
    left, top, width, height = bounds
    if not isinstance(raw, dict):
        return None

    type_val = raw.get("type")
    if not isinstance(type_val, str):
        return None
    try:
        action_type = ActionType(type_val)
    except ValueError:
        return None

    # 坐标：仅非 None 时校验真 int（拒绝 bool）+ 边界；必填性交给 validate()
    coords: Dict[str, Optional[int]] = {}
    for name in ("x", "y", "x2", "y2"):
        v = raw.get(name)
        if v is None:
            coords[name] = None
        elif isinstance(v, bool) or not isinstance(v, int):
            return None
        else:
            coords[name] = v
    for name, lo, hi in (
        ("x", left, left + width), ("x2", left, left + width),
        ("y", top, top + height), ("y2", top, top + height),
    ):
        v = coords[name]
        if v is not None and not (lo <= v < hi):
            return None

    # duration：缺失用默认 0.2；null/字符串/bool/负/NaN 拒绝
    duration = raw.get("duration", 0.2)
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        return None
    if not math.isfinite(duration) or duration < 0:
        return None

    # target_id：只接受正整数，非法值丢弃置 None（不因它拒绝动作，§5.2 第 5 条）
    target_id = raw.get("target_id")
    if not (
        target_id is None
        or (isinstance(target_id, int) and not isinstance(target_id, bool)
            and target_id > 0)
    ):
        target_id = None

    action = Action(
        type=action_type,
        x=coords["x"], y=coords["y"], x2=coords["x2"], y2=coords["y2"],
        text=raw.get("text"),
        key=raw.get("key"),
        keys=raw.get("keys"),
        scroll_amount=raw.get("scroll_amount"),
        duration=duration,
        target_id=target_id,
    )
    try:
        action.validate()
    except (ValueError, TypeError):
        return None
    return action
