"""数据预处理公共逻辑：解析、键名、序列级转换、写出。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import NamedTuple

SCHEMA_VERSION = "1.0"


class ParseResult(NamedTuple):
    status: str       # "ok" | "empty" | "error"
    actions: list[dict]
    note: str


_JSON_FENCE_RE = re.compile(r"```json\s*(.*?)```", re.DOTALL)
# 仅匹配键名位置的非法转义： "…\_…" 后紧跟冒号
_KEY_UNESCAPE_RE = re.compile(r'("[^"]*?)\\_([^"]*?")(\s*:)')


def _extract_candidates(text: str) -> list[str]:
    candidates = [text.strip()]
    for block in _JSON_FENCE_RE.findall(text):
        candidates.append(block.strip())
    return candidates


def _try_parse(candidate: str) -> tuple[bool, bool, object]:
    """返回 (成功, 是否用了修复, 解析结果)。"""
    try:
        return True, False, json.loads(candidate)
    except json.JSONDecodeError:
        pass
    fixed = _KEY_UNESCAPE_RE.sub(lambda m: m.group(1) + "_" + m.group(2) + m.group(3), candidate)
    if fixed != candidate:
        try:
            return True, True, json.loads(fixed)
        except json.JSONDecodeError:
            pass
    return False, False, None


def parse_actions(text: str) -> ParseResult:
    for candidate in _extract_candidates(text):
        if not candidate:
            continue
        ok, fixed, obj = _try_parse(candidate)
        if not ok:
            continue
        if not isinstance(obj, list):
            return ParseResult("error", [], "parsed result is not a list")
        if not obj:
            return ParseResult("empty", [], "empty action list")
        if not all(isinstance(a, dict) for a in obj):
            return ParseResult("error", [], "action list contains non-dict item")
        note = "applied key-name unescape fix" if fixed else ""
        return ParseResult("ok", obj, note)
    return ParseResult("error", [], "no JSON candidate parsed")


KEY_ALIASES = {
    "control_l": "ctrl", "control_r": "ctrl", "control": "ctrl", "ctrl": "ctrl",
    "shift_l": "shift", "shift_r": "shift",
    "alt_l": "alt", "alt_r": "alt",
    "super_l": "win", "super_r": "win", "super": "win", "win": "win", "cmd": "win",
    "return": "enter", "enter": "enter",
    "escape": "esc", "esc": "esc",
    "backspace": "backspace",
    "space": "space",
    "tab": "tab",
    "delete": "delete", "insert": "insert",
    "home": "home", "end": "end",
    "page_up": "pageup", "pageup": "pageup",
    "page_down": "pagedown", "pagedown": "pagedown",
    "up": "up", "down": "down", "left": "left", "right": "right",
    "caps_lock": "capslock", "capslock": "capslock",
}

ALLOWED_KEYS = (
    set(chr(c) for c in range(ord("a"), ord("z") + 1))
    | set(str(i) for i in range(10))
    | {f"f{i}" for i in range(1, 13)}
    | {"ctrl", "alt", "shift", "win"}
    | {"enter", "esc", "tab", "space", "backspace", "delete", "insert",
       "home", "end", "pageup", "pagedown", "up", "down", "left", "right",
       "capslock", "numlock", "printscreen", "scrolllock", "pause", "menu"}
)


def key_alias(keysym: str) -> str:
    k = keysym.strip()
    if not k:
        return ""
    return KEY_ALIASES.get(k.lower(), k.lower())


@dataclass
class ConversionResult:
    status: str        # "ok" | "unsupported" | "empty"
    actions: list[dict]
    reason: str


_MODIFIER_KEYS = {"ctrl", "shift", "alt", "win"}
_KNOWN_TYPES = {"PlanAction", "MouseAction", "KeyboardAction", "WaitAction", "EvaluateSubTaskAction"}


def _to_int(v):
    """坐标转为 int；非整数 float、bool、非数值一律 None（spec §6.3 坐标须为有限 int）。"""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return None


def _position(a: dict):
    p = a.get("mouse_position")
    if isinstance(p, dict):
        x, y = _to_int(p.get("width")), _to_int(p.get("height"))
        if x is not None and y is not None:
            return (x, y)
    return None


def _button(a: dict) -> str:
    b = a.get("mouse_button")
    if b is None:
        return "left"
    return b.lower() if isinstance(b, str) else ""


def _fail(reason: str) -> ConversionResult:
    return ConversionResult("unsupported", [], reason)


def convert_action_sequence(actions: list[dict]) -> ConversionResult:
    plan_seen = any(isinstance(a, dict) and a.get("action_type") == "PlanAction" for a in actions)
    exec_seen = any(isinstance(a, dict) and a.get("action_type") in ("MouseAction", "KeyboardAction") for a in actions)
    if plan_seen and exec_seen:
        return _fail("mixed plan and exec actions")

    mouse_pos: tuple[int, int] | None = None
    pending_mods: list[str] = []
    out: list[dict] = []

    for a in actions:
        if not isinstance(a, dict):
            return _fail("action is not a dict")
        atype = a.get("action_type")
        if atype not in _KNOWN_TYPES:
            return _fail(f"unknown action_type {atype!r}")

        if atype == "PlanAction":
            element = a.get("element")
            if not isinstance(element, str):
                return _fail("PlanAction missing string element")
            out.append({"type": "plan", "text": element})

        elif atype == "WaitAction" or atype == "EvaluateSubTaskAction":
            continue  # 跳过，不改变动作语义

        elif atype == "MouseAction":
            if pending_mods:
                # spec §4.2：无「修饰键+鼠标」动作，pending_mods 非空期间出现鼠标操作 → 整样本隔离
                return _fail("mouse action while modifiers held")
            matype = a.get("mouse_action_type")
            if matype == "move":
                pos = _position(a)
                if pos is None:
                    return _fail("move without position")
                out.append({"type": "move", "x": pos[0], "y": pos[1]})
                mouse_pos = pos
            elif matype in ("click", "double_click"):
                btn = _button(a)
                if matype == "click":
                    if btn == "left":
                        t = "click"
                    elif btn == "right":
                        t = "right_click"
                    else:
                        return _fail(f"unsupported click button {btn!r}")
                else:  # double_click
                    if btn != "left":
                        return _fail(f"unsupported double_click button {btn!r}")
                    t = "double_click"
                pos = _position(a) or mouse_pos
                if pos is None:
                    return _fail(f"{matype} without position")
                out.append({"type": t, "x": pos[0], "y": pos[1]})
                mouse_pos = pos
            elif matype == "drag":
                if _button(a) != "left":
                    return _fail("drag only supports left button")
                end = _position(a)
                if end is None or mouse_pos is None:
                    return _fail("drag without start or end")
                out.append({"type": "drag", "x": mouse_pos[0], "y": mouse_pos[1],
                            "x2": end[0], "y2": end[1]})
                mouse_pos = end
            elif matype in ("scroll_up", "scroll_down"):
                repeat = a.get("scroll_repeat", 1)
                if not isinstance(repeat, int) or repeat <= 0:
                    return _fail(f"invalid scroll_repeat {repeat!r}")
                amount = repeat if matype == "scroll_up" else -repeat
                out.append({"type": "scroll", "scroll_amount": amount})
            elif matype in ("down", "up"):
                return _fail("mouse down/up not supported")
            else:
                return _fail(f"unknown mouse_action_type {matype!r}")

        elif atype == "KeyboardAction":
            katype = a.get("keyboard_action_type")
            if katype == "text":
                if pending_mods:
                    return _fail("text while modifiers held")
                txt = a.get("keyboard_text", a.get("keyboard_input"))
                if not isinstance(txt, str):
                    return _fail("text without keyboard_text")
                out.append({"type": "type", "text": txt})
            elif katype == "press":
                key = a.get("keyboard_key")
                if not isinstance(key, str) or not key:
                    return _fail("press without keyboard_key")
                if "+" in key:
                    parts = [key_alias(p) for p in key.split("+")]
                else:
                    parts = [key_alias(key)]
                if any(p not in ALLOWED_KEYS for p in parts):
                    return _fail(f"key not in whitelist: {parts!r}")
                if pending_mods:
                    parts = pending_mods + parts
                    out.append({"type": "hotkey", "keys": parts})
                elif len(parts) > 1:
                    out.append({"type": "hotkey", "keys": parts})
                else:
                    out.append({"type": "press", "key": parts[0]})
            elif katype in ("down", "up"):
                key = a.get("keyboard_key")
                mod = key_alias(key) if isinstance(key, str) else ""
                if mod not in _MODIFIER_KEYS:
                    return _fail(f"non-modifier {katype}: {key!r}")
                if katype == "down":
                    if mod in pending_mods:
                        return _fail(f"duplicate modifier down {mod!r}")
                    pending_mods.append(mod)
                else:  # up
                    if mod not in pending_mods:
                        return _fail(f"unmatched modifier up {mod!r}")
                    pending_mods.remove(mod)
            else:
                return _fail(f"unknown keyboard_action_type {katype!r}")

    if pending_mods:
        return _fail("unreleased modifier")
    if not out:
        return ConversionResult("empty", [], "no converted actions")
    return ConversionResult("ok", out, "")
