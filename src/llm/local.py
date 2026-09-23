"""本地部署后端骨架：本期只提供接口占位，真实加载与推理在第 5 周实现。"""

from __future__ import annotations

import numpy as np

from src.llm.base import LLMConfig, VLMModel


class LocalVLMModel(VLMModel):
    """本地部署后端（第 5 周实现：Transformers 量化加载 → 多模态前向 → 文本解码）。"""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config

    def generate(self, prompt: str, image: np.ndarray) -> str:
        self._validate_input(prompt, image)  # 先公共校验：非法输入 → ValueError
        raise NotImplementedError("本地部署后端将在第 5 周（微调 / 量化）实现")
