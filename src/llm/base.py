"""大模型调用接口抽象基座：LLMError、LLMConfig、VLMModel 契约。

分层（对齐 agent-io spec §9）：本层只做「文本 + 图片 → 文本」，不关心 Agent
业务语义；prompt 是上层已拼好的完整文本，图片的 ndarray→base64 由 API 后端
处理，模型返回文本本身是否合法 JSON 由上层判断。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


class LLMError(Exception):
    """模型调用过程中发生的基础设施异常。"""


@dataclass
class LLMConfig:
    """后端无关的模型调用配置（纯数据对象：构造时不校验、不读环境变量、不做 I/O）。

    provider == "local" 专属的 model_path / device / quantize 留第 5 周真实实现时使用。
    """

    provider: str = "api"                        # "api" | "local"
    model: str = ""                              # 如 "qwen-vl-max" / "Qwen/Qwen2-VL-2B-Instruct"
    base_url: str = "https://api.openai.com/v1"  # OpenAI 兼容端点
    api_key: str | None = None                   # 显式 Key；None 时后端构造阶段从 api_key_env 读
    api_key_env: str = "LLM_API_KEY"             # 读 api_key 的环境变量名
    timeout: float = 60.0
    max_tokens: int = 2048
    temperature: float = 0.0                     # Agent 决策要确定性，默认 0
    model_path: str | None = None                # 本地权重路径或 HF 仓库 id
    device: str = "auto"                         # "auto" | "cuda" | "cpu"
    quantize: str | None = None                  # None | "4bit" | "8bit"


class VLMModel(ABC):
    """多模态大模型调用抽象基类，统一 generate(prompt, image) -> str。"""

    @abstractmethod
    def generate(self, prompt: str, image: np.ndarray) -> str:
        """文本 + RGB 截图 → 模型原始文本输出。

        Args:
            prompt: 已拼好的完整文本（角色、指令、屏幕描述、输出格式要求）。
            image: RGB 截图，numpy ndarray，shape (H, W, 3)，dtype uint8，H>0 且 W>0。

        Returns:
            模型原始文本输出（通常为 JSON 字符串，由上层 parse；模型文本本身是否
            合法 JSON 不在 llm 层判断，一律原样返回）。

        Raises:
            ValueError: 输入契约错误（prompt 非 str、image 非 ndarray / 形状非法 /
                        dtype 非 uint8 / H 或 W 非正），在调用模型之前抛出。
            LLMError:   模型调用过程中发生的基础设施异常，向外传播。
        """

    def _validate_input(self, prompt: str, image: np.ndarray) -> None:
        """公共输入校验，所有实现须在 generate 开头先调用；不合法 → ValueError。"""
        if not isinstance(prompt, str):
            raise ValueError(f"prompt 必须是 str，收到 {type(prompt).__name__}")
        if not isinstance(image, np.ndarray):
            raise ValueError(
                f"image 必须是 numpy ndarray，收到 {type(image).__name__}"
            )
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError(f"image 形状必须是 (H, W, 3)，收到 {image.shape}")
        if image.dtype != np.uint8:
            raise ValueError(f"image dtype 必须是 uint8，收到 {image.dtype}")
        if image.shape[0] <= 0 or image.shape[1] <= 0:
            raise ValueError(f"image 的 H、W 必须为正，收到 {image.shape[:2]}")
