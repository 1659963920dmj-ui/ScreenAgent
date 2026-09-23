"""Agent prompt 模板：输出 schema 与完整 prompt 渲染（LangChain PromptTemplate 封装）。

LangChain 仅在本文件出现（封装边界，不泄漏到 agent.py）：用 PromptTemplate
管理/渲染文本 prompt，Agent 循环在 agent.py 自研。
"""

from __future__ import annotations

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
