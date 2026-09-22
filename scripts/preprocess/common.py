"""数据预处理公共逻辑：解析、键名、序列级转换、写出。"""
from __future__ import annotations

import json
import re
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
