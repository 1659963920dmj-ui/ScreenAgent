"""大模型调用接口层：统一 generate(prompt, image) -> str，API / 本地后端可切换。"""

from __future__ import annotations

from src.llm.api import APIVLMModel
from src.llm.base import LLMConfig, LLMError, VLMModel
from src.llm.factory import get_model, load_config
from src.llm.local import LocalVLMModel

__all__ = [
    "VLMModel",
    "APIVLMModel",
    "LocalVLMModel",
    "get_model",
    "LLMConfig",
    "LLMError",
    "load_config",
]
