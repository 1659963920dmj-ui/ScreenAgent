"""Agent prompt 模板：输出 schema 与完整 prompt 渲染（LangChain PromptTemplate 封装）。

LangChain 仅在本文件出现（封装边界，不泄漏到 agent.py）：用 PromptTemplate
管理/渲染文本 prompt，Agent 循环在 agent.py 自研。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from langchain_core.prompts import PromptTemplate

from src.agent.history import summarize_history
from src.agent.step import AgentStep
from src.control.keys import ALLOWED_KEYS


def build_schema() -> str:
    """返回模型输出 JSON 的 schema 文本，键名白名单从 ALLOWED_KEYS 动态拼接。

    文本须与 parse_step 的解析规则、Action.validate 的校验规则逐字对齐
    （模型照它输出，解析器照它验收）。键名列表来自 ", ".join(sorted(ALLOWED_KEYS))，
    不硬编码 73 个键名，避免与 src/control/keys.py 双份硬编码、未来漂移。
    """
    allowed = ", ".join(sorted(ALLOWED_KEYS))
    return (
        "输出一个 JSON 对象（不要输出其他文字），字段如下：\n"
        '  "status": "action" | "done" | "error"（必填）\n'
        '  "understanding": 字符串（必填，对当前屏幕与任务的理解）\n'
        '  "plan": 字符串（必填，下一步计划）\n'
        '  "action": 对象（仅 status="action" 时）\n'
        '  "summary": 非空字符串（仅 status="done" 时，任务完成总结）\n'
        '  "reason": 字符串（仅 status="error" 时，无法继续的原因）\n'
        "\n"
        'action 对象的字段（"type" 必填）：\n'
        '  "type": "move" | "click" | "double_click" | "right_click" | '
        '"scroll" | "drag" | "type" | "press" | "hotkey"\n'
        '  move / click / double_click / right_click：x、y（整数）\n'
        '  scroll：scroll_amount（整数，正向上负向下），x、y（可选）\n'
        '  drag：x、y（起点）、x2、y2（终点）\n'
        '  type：text（字符串）\n'
        '  press：key（字符串，单个按键）\n'
        '  hotkey：keys（非空字符串数组，组合键）\n'
        '  duration：有限非负秒数（可省略，默认 0.2）\n'
        '  target_id：正整数（可省略，指代屏幕元素编号，仅辅助）\n'
        "\n"
        "坐标约定：屏幕绝对像素坐标（整数），须落在有效坐标范围内。\n"
        f"按键白名单（press.key / hotkey.keys 取值于此）：{allowed}\n"
    )


_PROMPT_TEMPLATE = PromptTemplate(
    template=(
        "{system}\n\n"
        "## 用户任务\n{instruction}\n\n"
        "## 当前屏幕状态\n{screen_state}\n\n"
        "## 历史动作摘要\n{history}"
    ),
    input_variables=["system", "instruction", "screen_state", "history"],
)


def _build_system() -> str:
    return (
        "你是一个桌面 GUI 智能体：根据用户指令、当前屏幕状态与历史动作，"
        "决定下一步操作，只输出一个 JSON 对象。\n\n"
        + build_schema()
    )


def _format_screen_state(
    screen_state: List[Dict[str, Any]], bounds: tuple[int, int, int, int]
) -> str:
    left, top, width, height = bounds
    lines = [
        f"截图尺寸: {width}x{height} @ ({left}, {top})",
        f"有效坐标范围: x ∈ [{left}, {left + width}), y ∈ [{top}, {top + height})",
        "坐标: 屏幕绝对坐标（图像内坐标 + 截图原点偏移；请直接输出屏幕绝对坐标）",
    ]
    for d in screen_state:
        lines.append(
            f"[{d['id']}] {d['type']:<6} \"{d['label']}\" @ "
            f"({d['center'][0]}, {d['center'][1]})"
        )
    return "\n".join(lines)


def _format_history(history: List[AgentStep], max_history_steps: int) -> str:
    return json.dumps(
        summarize_history(history, max_steps=max_history_steps),
        ensure_ascii=False,
    )


def render_prompt(
    instruction: str,
    screen_state: list[dict],
    history: list[AgentStep],
    bounds: tuple[int, int, int, int],
    max_history_steps: int = 5,
) -> str:
    """渲染完整 prompt 文本。

    bounds = (left, top, width, height)：与 parse_step 传入的同一份截图边界，
    用于在 prompt 里写出截图尺寸、原点与有效坐标范围（区域截图下模型
    需要它把图像内坐标换算成屏幕绝对坐标）。

    screen_state（elements_to_dicts 产物）内部序列化为编号文本，坐标为
    屏幕绝对坐标，不二次偏移；history 内部经 summarize_history(history,
    max_steps=max_history_steps) 压缩为 JSON 摘要。
    """
    return _PROMPT_TEMPLATE.invoke(
        {
            "system": _build_system(),
            "instruction": instruction,
            "screen_state": _format_screen_state(screen_state, bounds),
            "history": _format_history(history, max_history_steps),
        }
    ).to_string()
