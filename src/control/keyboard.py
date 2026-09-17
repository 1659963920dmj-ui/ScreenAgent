"""键盘控制模块，基于 PyAutoGUI。

文本输入的平台策略：
- Windows：SendInput 的 KEYEVENTF_UNICODE 直接注入，绕过输入法，不占用剪贴板。
- 非 Windows：ASCII 用 write，非 ASCII 经剪贴板粘贴。

已知限制：非 Windows 的非 ASCII 输入依赖剪贴板，只能保存/恢复文本内容，
会丢失用户已复制的图片、文件等非文本数据。因此文本输入的「完整支持」目前
仅限 Windows 平台，非 Windows 的中文 / emoji 输入存在剪贴板数据丢失风险。
"""

from __future__ import annotations


class KeyboardController:
    """键盘操作封装：文本输入、单键、组合键。"""

    def __init__(self) -> None:
        import pyautogui

        self._pg = pyautogui

    def type_text(self, text: str, interval: float = 0.05) -> None:
        """输入文本。

        Windows 下统一用 SendInput 的 Unicode 注入，规避系统输入法对虚拟
        键码的拦截（否则系统处于中文输入法时，英文 write 会被 IME 捕获
        导致输出错误）。非 Windows 下：ASCII 用 write，非 ASCII 用剪贴板回退。

        Args:
            text: 待输入文本。
            interval: 每个字符之间的间隔（秒）。
        """
        import platform

        if platform.system() == "Windows":
            self._send_unicode_windows(text, interval=interval)
        elif text.isascii():
            self._pg.write(text, interval=interval)
        else:
            self._paste_unicode(text)

    def _fail_safe_check(self) -> None:
        """执行 PyAutoGUI 的 fail-safe 紧急中止检查。

        fail-safe 开启（pyautogui.FAILSAFE 为 True）且鼠标位于屏幕左上角
        (0, 0) 时抛出 FailSafeException。Windows 的 SendInput 直接注入不走
        PyAutoGUI 的 write，无法继承其内置检查，故需在此显式调用，让长文本
        输入也能被用户紧急中止。
        """
        if self._pg.FAILSAFE and tuple(self._pg.position()) == (0, 0):
            raise self._pg.FailSafeException(
                "PyAutoGUI fail-safe triggered from mouse moving to a corner of the screen."
            )

    def _send_unicode_windows(self, text: str, interval: float = 0.0) -> None:
        """通过 SendInput 的 KEYEVENTF_UNICODE 直接输入文本。

        直接合成 Unicode 键盘事件，不经过输入法（IME），因此不受中文输入法
        状态影响，也不会读写剪贴板（不会覆盖用户已复制的图片、文件等）。

        每个事件发送前执行 fail-safe 检查（鼠标移到屏幕左上角即中止），并
        校验 SendInput 返回值，注入失败（如普通权限进程向管理员窗口输入被
        系统拦截）时抛出异常，而非静默当作成功。
        """
        import ctypes
        import time
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)

        INPUT_KEYBOARD = 1
        KEYEVENTF_KEYUP = 0x0002
        KEYEVENTF_UNICODE = 0x0004

        # ULONG_PTR：32 位 4 字节、64 位 8 字节
        ULONG_PTR = (
            ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
        )

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR),
            ]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [
                ("uMsg", wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD),
            ]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR),
            ]

        class INPUTUNION(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("u", INPUTUNION)]

        SendInput = user32.SendInput
        SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        SendInput.restype = wintypes.UINT

        self._fail_safe_check()
        for unit in _utf16_units(text):
            down = INPUT(
                type=INPUT_KEYBOARD,
                u=INPUTUNION(ki=KEYBDINPUT(0, unit, KEYEVENTF_UNICODE, 0, 0)),
            )
            up = INPUT(
                type=INPUT_KEYBOARD,
                u=INPUTUNION(
                    ki=KEYBDINPUT(0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0)
                ),
            )
            for event in (down, up):
                self._fail_safe_check()
                sent = SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT))
                if sent != 1:
                    err = ctypes.get_last_error()
                    raise OSError(
                        f"SendInput 注入失败：返回 {sent}，系统错误码 {err}"
                    )
            if interval:
                time.sleep(interval)

    def _paste_unicode(self, text: str) -> None:
        """回退方案：通过剪贴板粘贴非 ASCII 文本。

        注意：此方式会占用并覆盖剪贴板，且只能保存/恢复文本内容，
        会丢失用户已复制的图片等非文本数据。Windows 平台已改用
        _send_unicode_windows 避免此问题，这里仅作为非 Windows 回退。
        """
        import platform
        import time

        import pyperclip

        paste_keys = ("command", "v") if platform.system() == "Darwin" else ("ctrl", "v")
        previous = pyperclip.paste()  # 保存原文本剪贴板，粘贴后恢复
        try:
            pyperclip.copy(text)
            self._pg.hotkey(*paste_keys)
            time.sleep(0.1)  # 等待目标应用完成粘贴，再恢复剪贴板
        finally:
            pyperclip.copy(previous)

    def press(self, key: str) -> None:
        """按下并释放单个按键，如 "enter"、"esc"、"f5"。"""
        self._pg.press(key)

    def hotkey(self, *keys: str) -> None:
        """同时按下多个键（组合键），如 hotkey("ctrl", "c")。"""
        self._pg.hotkey(*keys)


def _utf16_units(text: str) -> list[int]:
    """把字符串拆成 UTF-16 code unit 列表（含代理对拆分），供 SendInput 使用。"""
    units: list[int] = []
    for ch in text:
        code = ord(ch)
        if code > 0xFFFF:
            code -= 0x10000
            units.append(0xD800 + (code >> 10))
            units.append(0xDC00 + (code & 0x3FF))
        else:
            units.append(code)
    return units
