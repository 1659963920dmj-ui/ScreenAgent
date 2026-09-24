# llm — 大模型调用接口层

统一的多模态模型调用接口：**文本 prompt + RGB 截图 → 模型原始文本**，API / 本地后端可切换。
本层只做「文本 + 图片 → 文本」，不关心 Agent 业务语义；prompt 是上层已拼好的完整文本，
模型返回文本本身是否合法 JSON 由上层（`src/agent`）判断。

## 接口契约

```python
class VLMModel(ABC):
    def generate(self, prompt: str, image: np.ndarray) -> str: ...
```

- `prompt`：已拼好的完整文本（角色、指令、屏幕描述、输出格式要求）。
- `image`：RGB 截图，numpy ndarray，shape `(H, W, 3)`，dtype `uint8`，`H`/`W` 为正。
- 返回：模型原始文本输出（通常为 JSON 字符串，原样返回，不在此层解析）。

所有实现须在 `generate()` 开头先调用 `VLMModel._validate_input(prompt, image)`，
非法输入抛 `ValueError`（在调用模型之前）。

## 文件说明

| 文件 | 功能 |
| --- | --- |
| [base.py](base.py) | 抽象基座：`LLMError`、`LLMConfig` 配置数据类、`VLMModel` 抽象基类与公共输入校验 |
| [api.py](api.py) | `APIVLMModel`：通过 HTTP 调用 OpenAI 兼容 `chat/completions` 端点，截图转 PNG Base64 |
| [local.py](local.py) | `LocalVLMModel`：本地部署后端骨架（第 5 周实现 Transformers 量化加载与推理，本期抛 `NotImplementedError`） |
| [factory.py](factory.py) | `get_model()` 按 `provider` 分发后端、`load_config()` 从 YAML 读配置 |
| [__init__.py](__init__.py) | 包入口，统一导出上述公共接口 |

## 配置（`LLMConfig`）

`LLMConfig` 是后端无关的纯数据对象（构造时不校验、不读环境变量、不做 I/O），字段：

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `provider` | `"api"` | `"api"` / `"local"` |
| `model` | `""` | 如 `qwen-vl-max` / `Qwen/Qwen2-VL-2B-Instruct` |
| `base_url` | `https://api.openai.com/v1` | OpenAI 兼容端点 |
| `api_key` | `None` | 显式 Key；`None` 时后端构造阶段从 `api_key_env` 读 |
| `api_key_env` | `"LLM_API_KEY"` | 读 `api_key` 的环境变量名 |
| `timeout` | `60.0` | 请求超时（秒） |
| `max_tokens` | `2048` | 生成 token 上限 |
| `temperature` | `0.0` | Agent 决策要确定性，默认 0 |
| `model_path` | `None` | 本地权重路径或 HF 仓库 id（`provider="local"` 专属） |
| `device` | `"auto"` | `"auto"` / `"cuda"` / `"cpu"`（本地后端专属） |
| `quantize` | `None` | `None` / `"4bit"` / `"8bit"`（本地后端专属） |

`model_path` / `device` / `quantize` 留第 5 周本地部署真实实现时使用。

## 快速使用

```python
from src.llm import get_model, load_config, LLMConfig

# 方式一：从 YAML 读配置（configs/llm.yaml）
model = get_model(load_config("configs/llm.yaml"))

# 方式二：代码直接构造
model = get_model(LLMConfig(
    provider="api",
    model="qwen-vl-max",
    base_url="https://api.openai.com/v1",
))

# 生成（prompt 为拼好的完整文本，image 为 (H, W, 3) uint8 ndarray）
# text = model.generate(prompt, screenshot_image_rgb)
```

API Key 不写入配置（会入库），优先从环境变量 `LLM_API_KEY` 读取，或代码显式传 `api_key`。

## 错误处理

- `ValueError`：输入契约 / 配置错误（`prompt` 非 str、`image` 非法、`model`/`base_url` 为空、
  `timeout`/`max_tokens` 非法、未知 `provider`、YAML 含未知字段），在调用模型之前抛出。
- `LLMError`：模型调用过程中的基础设施异常（请求超时、网络失败、HTTP 非 2xx、响应体非合法
  JSON、响应结构不符预期），对外传播，由调用方决定是否重试。

## 扩展后端

新增后端（含专用适配子类）时，在 `factory.get_model` 注册一个 `provider` 分支即可；
若协议与 OpenAI 兼容端点有差异，可继承 `APIVLMModel` 覆盖 `_build_payload` /
`_build_messages` / `_parse_response` / `_image_to_data_url` 钩子，其余逻辑复用通用实现。

## 已知局限

- 本地后端 `LocalVLMModel` 本期仅占位，`generate()` 抛 `NotImplementedError`，
  第 5 周（微调 / 量化）实现真实加载与推理。
- `APIVLMModel` 面向 OpenAI 兼容协议；接入有差异的服务需覆盖钩子，未覆盖的协议差异会
  以 `LLMError` 暴露。
