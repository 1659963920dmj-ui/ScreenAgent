"""键名白名单：control 层允许的按键名。

与 scripts/preprocess/common.py 的 ALLOWED_KEYS 内容一致（两处硬编码），
此处为执行侧权威定义，供 Action.validate() 校验 press.key / hotkey.keys。
键名一律为小写规范名（别名如 return/escape/super 不在白名单内）。
"""

from __future__ import annotations

ALLOWED_KEYS: frozenset[str] = frozenset({
    *[chr(c) for c in range(ord("a"), ord("z") + 1)],
    *[str(i) for i in range(10)],
    *[f"f{i}" for i in range(1, 13)],
    "ctrl", "alt", "shift", "win",
    "enter", "esc", "tab", "space", "backspace", "delete", "insert",
    "home", "end", "pageup", "pagedown", "up", "down", "left", "right",
    "capslock", "numlock", "printscreen", "scrolllock", "pause", "menu",
})
