# control — 桌面控制模块

把结构化动作翻译为底层鼠标键盘操作。设计原则：**动作（`Action`，纯数据）与执行
（`Controller`，副作用）分离**——`Action` 可校验、可日志、可序列化、可单元测试，
`Controller` 是唯一对外入口，上层（第 4 周 Agent 框架）只需构造 `Action` 并调用
`execute()`，无需关心底层实现。

## 数据流

```
AgentStep.action（结构化动作）
        │
        ▼
Controller.execute(action)
        │  action.validate() 通过后按 type 分发
        ├──► MouseController    move / click / double_click / right_click / scroll / drag
        └──► KeyboardController type_text / press / hotkey
```

## 文件说明

| 文件 | 功能 |
| --- | --- |
| [actions.py](actions.py) | `ActionType` 动作类型枚举、`Action` 动作数据类与 `validate()` 参数校验 |
| [controller.py](controller.py) | `Controller` 统一入口，按 `Action.type` 分发执行并记日志 |
| [mouse.py](mouse.py) | `MouseController` 鼠标操作（PyAutoGUI 封装） |
| [keyboard.py](keyboard.py) | `KeyboardController` 键盘操作（Windows 走 SendInput Unicode 注入，非 Windows 走 write/剪贴板回退） |
| [keys.py](keys.py) | `ALLOWED_KEYS` 键名白名单，供 `Action.validate()` 校验 `press.key` / `hotkey.keys` |
| [__init__.py](__init__.py) | 包入口，统一导出上述公共接口 |

## 动作类型（`ActionType`）

| type | 含义 | 必填字段 | 可选字段 |
| --- | --- | --- | --- |
| `move` | 移动鼠标 | `x`、`y` | `duration` |
| `click` | 左键单击 | `x`、`y` | — |
| `double_click` | 左键双击 | `x`、`y` | — |
| `right_click` | 右键单击 | `x`、`y` | — |
| `scroll` | 滚动滚轮 | `scroll_amount`（正向上、负向下） | `x`、`y`（滚动发生位置） |
| `drag` | 拖拽 | `x`、`y`（起点）、`x2`、`y2`（终点） | `duration` |
| `type` | 输入文本 | `text` | — |
| `press` | 按下并释放单键 | `key` | — |
| `hotkey` | 组合键 | `keys`（非空字符串列表） | — |

`duration` 为移动 / 拖拽耗时（默认 `0.2` 秒）；`target_id` 是模型指代的
`screen_state` 元素编号，仅用于日志 / 调试，不参与执行。

## 快速使用

```python
from src.control import Action, ActionType, Controller

ctrl = Controller()
ctrl.execute(Action(type=ActionType.CLICK, x=500, y=300))            # 点击
ctrl.execute(Action(type=ActionType.TYPE, text="ScreenAgent"))       # 输入文本
ctrl.execute(Action(type=ActionType.HOTKEY, keys=["ctrl", "v"]))     # 组合键
```

`Action.validate()` 会先校验参数类型与完整性，非法时抛 `ValueError`，防止错误模型
输出（如把字符串当坐标、键名不在白名单）进入键鼠执行层。

## 关键约定

- **坐标**：统一屏幕绝对像素。`MouseController` / `Action` 不关心 DPI 缩放与坐标系换算，
  由 `src/perception` 的 `Screenshot.to_screen()` 把图像坐标转屏幕坐标，下游直接给绝对坐标。
- **fail-safe**：PyAutoGUI 默认开启，鼠标移到屏幕左上角 `(0, 0)` 会抛异常中止自动化，
  是保护特性，**勿关闭**。Windows 的 SendInput 直接注入不走 PyAutoGUI 的 `write`，无法继承
  其内置检查，故 `KeyboardController` 在长文本输入前显式做 fail-safe 检查。
- **键名白名单**：`press.key` / `hotkey.keys` 取值限于 `ALLOWED_KEYS`（小写规范名），
  别名 `return` / `escape` / `super` 不在白名单内，须用 `enter` / `esc` / `win`。
- **文本输入平台策略**：Windows 用 SendInput 的 `KEYEVENTF_UNICODE` 直接注入，绕过输入法、
  不占用剪贴板；非 Windows 下 ASCII 用 `write`，非 ASCII 经剪贴板粘贴。

## 已知局限

- **需要真实图形桌面**：PyAutoGUI / SendInput 在无头环境（CI、无显示器、部分容器）会失败，
  本模块的单元测试只覆盖 `Action.validate()` 等纯逻辑，不触发真实键鼠。
- **非 Windows 非 ASCII 输入依赖剪贴板**：只能保存 / 恢复文本内容，会丢失用户已复制的
  图片、文件等非文本数据，因此文本输入的「完整支持」目前仅限 Windows。
- **跨分辨率 / DPI 敏感**：屏幕坐标受分辨率和缩放影响，跨分辨率适配是第 2、7 周重点，
  控制层本身不做坐标归一化。
- **`ALLOWED_KEYS` 双份硬编码**：与 `scripts/preprocess/common.py` 的 `ALLOWED_KEYS`
  内容一致，执行侧以本文件为权威定义。
