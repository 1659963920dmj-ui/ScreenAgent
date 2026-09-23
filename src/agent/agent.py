"""Agent 规划循环：step() 把「指令 + 截图 + 屏幕状态 + 历史」变成一步决策。

纯规划层：不截图、不执行动作。screenshot 与 screen_state 由调用方（第 4 周
Runner）准备，产出的 AgentStep.action 由调用方执行。
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from src.agent.parser import parse_step
from src.agent.prompt import render_prompt
from src.agent.step import AgentStep
from src.llm import VLMModel
from src.perception.screen import Screenshot


class Agent:
    """单步规划器：校验输入 → 渲染 prompt → model.generate → parse_step。"""

    def __init__(self, model: VLMModel, max_history_steps: int = 5) -> None:
        """构造规划器。

        Args:
            model: 多模态模型，须实现 generate(prompt, image) -> str。
            max_history_steps: 进 prompt 的最近历史步数，正整数。
        """
        if (
            isinstance(max_history_steps, bool)
            or not isinstance(max_history_steps, int)
            or max_history_steps <= 0
        ):
            raise ValueError(
                f"max_history_steps 必须是正整数，收到 {max_history_steps!r}"
            )
        self._model = model
        self._max_history_steps = max_history_steps

    def step(
        self,
        instruction: str,
        screenshot: Screenshot,
        screen_state: list[dict],
        history: Optional[list[AgentStep]] = None,
    ) -> AgentStep:
        """执行一次规划：校验输入 → 渲染 prompt → model.generate → parse_step。

        不截图、不执行动作——纯规划。失败分四类（对齐 agent-io §6）：
        - 输入契约错误：调用 LLM 前抛 ValueError；
        - 推理基础设施异常（LLMError）：原样向外传播，不构造 AgentStep；
        - 模型响应解析/校验失败：返回 AgentStep(status="error", error_kind="parse")；
        - 模型主动失败：返回 AgentStep(status="error", error_kind="model")。
        """
        self._validate_inputs(instruction, screenshot, screen_state, history)
        bounds = (
            screenshot.left,
            screenshot.top,
            screenshot.width,
            screenshot.height,
        )
        prompt = render_prompt(
            instruction,
            screen_state,
            history if history is not None else [],
            bounds,
            max_history_steps=self._max_history_steps,
        )
        raw = self._model.generate(prompt, screenshot.image)
        return parse_step(raw, bounds)

    @staticmethod
    def _validate_inputs(
        instruction: str,
        screenshot: Screenshot,
        screen_state: list[dict],
        history: Optional[list[AgentStep]],
    ) -> None:
        """输入契约校验：不合法抛 ValueError（调用 LLM 之前）。"""
        if not isinstance(instruction, str):
            raise ValueError(
                f"instruction 必须是 str，收到 {type(instruction).__name__}"
            )
        if not isinstance(screenshot, Screenshot):
            raise ValueError(
                f"screenshot 必须是 Screenshot，收到 {type(screenshot).__name__}"
            )
        if not isinstance(screen_state, list):
            raise ValueError(
                f"screen_state 必须是 list，收到 {type(screen_state).__name__}"
            )
        for d in screen_state:
            if not isinstance(d, dict):
                raise ValueError(
                    f"screen_state 元素必须是 dict，收到 {type(d).__name__}"
                )
            missing = sorted(
                k for k in ("id", "type", "label", "center") if k not in d
            )
            if missing:
                raise ValueError(f"screen_state 元素缺少必要键: {missing}")
            if not isinstance(d["type"], str):
                raise ValueError(
                    f"screen_state 元素的 type 必须是 str，"
                    f"收到 {type(d['type']).__name__}"
                )
            center = d["center"]
            if not isinstance(center, (list, tuple)) or len(center) < 2:
                raise ValueError(
                    "screen_state 元素的 center 必须是长度 ≥ 2 的序列，"
                    f"收到 {center!r}"
                )
        if history is not None:
            if not isinstance(history, list):
                raise ValueError(
                    f"history 必须是 list 或 None，收到 {type(history).__name__}"
                )
            if not all(isinstance(s, AgentStep) for s in history):
                raise ValueError("history 元素必须是 AgentStep")
        if not isinstance(screenshot.image, np.ndarray):
            raise ValueError(
                "screenshot.image 必须是 numpy ndarray，"
                f"收到 {type(screenshot.image).__name__}"
            )
        if screenshot.image.ndim < 2:
            raise ValueError(
                f"screenshot.image 维度必须 ≥ 2，收到 shape={screenshot.image.shape}"
            )
        if (
            screenshot.image.shape[0] != screenshot.height
            or screenshot.image.shape[1] != screenshot.width
        ):
            raise ValueError(
                "screenshot.image 形状与 width/height 不一致："
                f"image={screenshot.image.shape[:2]}，"
                f"声明={screenshot.width}x{screenshot.height}"
            )
