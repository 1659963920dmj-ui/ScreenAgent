# agent — 任务规划模块

Agent 是纯规划层：把「自然语言指令 + 当前截图 + 结构化屏幕状态 + 历史动作」变成
**一步决策**（`AgentStep`）。它不截图、不执行动作——screenshot 与 screen_state 由调用方
（第 4 周 Runner）准备，产出的 `AgentStep.action` 由调用方翻译成鼠标键盘操作执行。

## 数据流

```
instruction + screenshot + screen_state + history
                      │
                      ▼
        Agent.step()  ── 校验输入 ──► render_prompt()（拼完整 prompt）
                      │                         │
                      │                         ▼
                      │            model.generate(prompt, image) ──► 原始文本
                      │                         │
                      ▼                         ▼
                parse_step(raw, bounds)  ◄──────┘
                      │
                      ▼
                  AgentStep（action / done / error 三态）
```

## 文件说明

| 文件 | 功能 |
| --- | --- |
| [agent.py](agent.py) | `Agent` 类与 `step()` 规划循环（校验 → 渲染 → 生成 → 解析），并做输入契约校验 |
| [step.py](step.py) | `AgentStep` 三态数据结构与 `validate()` 严格校验 |
| [parser.py](parser.py) | `parse_step()` 把模型原始 JSON 解析并校验成 `AgentStep`（宽容解析 + 严格校验） |
| [prompt.py](prompt.py) | `build_schema()` 输出 schema 文本、`render_prompt()` 用 LangChain `PromptTemplate` 渲染完整 prompt |
| [history.py](history.py) | `summarize_history()` 把历史 `AgentStep` 压缩为进 prompt 的简短 JSON 摘要 |
| [__init__.py](__init__.py) | 包入口，统一导出上述公共接口 |

## 三态输出（`AgentStep`）

`AgentStep` 用 `status` 区分三种互斥结果，`understanding` / `plan` 三态恒有（用于日志、
调试与后续评估）：

| status | 有效字段 | 含义 |
| --- | --- | --- |
| `action` | `action`（非 None） | 生成下一步可执行动作 |
| `done` | `summary`（非 None） | 任务完成，返回总结 |
| `error` | `reason` + `error_kind`（`"model"`/`"parse"`） | 无法继续，返回原因 |

`error_kind` 区分两种失败来源：`"model"` 表示模型主动声明失败（输出 `status="error"`），
`"parse"` 表示模型输出无法通过解析或校验。两者的共同点是都不会把无效动作交给控制层执行。

## 解析与校验策略

- **宽容解析**：模型 JSON 允许冗余字段（丢弃、不报错）；无法解析时返回
  `AgentStep(status="error", error_kind="parse")`，不抛异常（模型输出不可控）。
- **严格校验**：`AgentStep.validate()` 与 `Action.validate()` 对最终产物做严格互斥检查，
  非法组合抛 `ValueError`（区别于解析层的宽容处理）。
- `parse_step` 的**坐标边界**由 `bounds = (left, top, width, height)` 限定，坐标须落在
  `[left, left+width) × [top, top+height)` 内——区域截图下用它把图像内坐标换算成屏幕绝对坐标。

## 快速使用

```python
import numpy as np

from src.agent import Agent
from src.llm import VLMModel
from src.perception.screen import Screenshot


class FakeVLMModel(VLMModel):
    """最小可用模型：返回一条 click 动作。"""
    def generate(self, prompt: str, image: np.ndarray) -> str:
        return ('{"status":"action","understanding":"浏览器首页","plan":"点击搜索框",'
                '"action":{"type":"click","x":487,"y":193}}')


agent = Agent(FakeVLMModel())                        # 默认最多带 5 步历史
shot = Screenshot(
    image=np.zeros((768, 1024, 3), dtype=np.uint8),
    width=1024, height=768,
)
screen_state = [
    {"id": 1, "type": "textbox", "label": "搜索框", "center": [487, 193]},
    {"id": 2, "type": "button",  "label": "搜索",   "center": [560, 193]},
]
step = agent.step("在浏览器中搜索 ScreenAgent", shot, screen_state)
print(step.status)          # "action"
print(step.action)          # Action(type=click, x=487, y=193)
```

## 关键约定

- **纯规划、无副作用**：`Agent` 不截图、不执行动作；`screenshot.image` 必须是 `(H, W, 3)`
  的 `uint8` ndarray，且与 `screenshot.width/height` 一致（否则 `step()` 抛 `ValueError`）。
- **失败分四类**（对齐 agent-io spec §6）：
  1. 输入契约错误 → 调用 LLM 前抛 `ValueError`；
  2. 推理基础设施异常（`LLMError`）→ 原样向外传播，不构造 `AgentStep`；
  3. 模型响应解析/校验失败 → `error_kind="parse"`；
  4. 模型主动失败 → `error_kind="model"`。
- **历史由外部显式传入**：`history` 是 `list[AgentStep]`，进 prompt 前经
  `summarize_history(history, max_steps=5)` 只保留最近几部的关键参数（`target_id` 不入历史，
  跨截图 id 重编号无意义），降低重复操作概率。
- **屏幕状态**：`screen_state` 元素须含 `id` / `type` / `label` / `center` 四个键，坐标为
  屏幕绝对坐标（来自 `src/perception` 的 `elements_to_dicts` 产物），不二次偏移。

## 已知局限

- 当前只做**单步决策**，多步任务中的错误恢复、重复动作检测、自动重试由第 4 周 Runner 负责。
- `Agent` 依赖 `VLMModel` 接口（`src/llm`），模型输出的 JSON 格式靠 prompt 模板约束，
  解析器的宽容策略只能兜底降级，不能保证模型一定输出合法动作。
- LangChain 仅在 `prompt.py` 出现（封装边界），`PromptTemplate` 用于文本渲染；Agent 循环
  逻辑在 `agent.py` 自研，不引入 LangChain Agent 抽象。
