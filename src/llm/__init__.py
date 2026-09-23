"""大模型调用接口层：统一 generate(prompt, image) -> str，API / 本地后端可切换。"""

from src.llm.api import APIVLMModel
from src.llm.base import LLMConfig, LLMError, VLMModel
from src.llm.local import LocalVLMModel

__all__ = ["VLMModel", "APIVLMModel", "LocalVLMModel", "LLMConfig", "LLMError"]
