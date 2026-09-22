"""ScreenAgent 数据集 → 统一样本 schema。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from scripts.preprocess.common import (
    SCHEMA_VERSION,
    convert_action_sequence,
    parse_actions,
    validate_coords,
    write_jsonl,
)


@dataclass
class Stats:
    total: int = 0
    act: int = 0
    plan: int = 0
    unsupported: int = 0
    empty: int = 0
    empty_after_conversion: int = 0
    error: int = 0
    reasons: dict = field(default_factory=dict)

    def bump(self, key: str, reason: str = "") -> None:
        setattr(self, key, getattr(self, key) + 1)
        if reason:
            self.reasons[reason] = self.reasons.get(reason, 0) + 1


def _pick_task(d: dict) -> str:
    for k in ("task_prompt_zh", "task_prompt", "task_prompt_en"):
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def _fail(record: dict, status: str, reason: str):
    """隔离记录：附 status（error/empty/empty_after_conversion/unsupported）与原因。"""
    return None, {**record, "status": status, "reason": reason}


def _convert_one(json_path: Path, session_id: str, image_root: Path, keep_prompt: bool):
    """返回 (sample_dict, None) 或 (None, 带 status/reason 的隔离记录)。

    status 语义（spec §4.2/§6/§7）：
      error     —— 记录/元数据缺陷（读不出、解析坏、字段缺失、尺寸非法或与截图不符）
      empty     —— 原始动作数组为空
      empty_after_conversion —— 原始动作非空但转换后为空
      unsupported —— 动作存在但无法用于训练（转换不支持，或坐标越界）
    """
    try:
        with json_path.open("r", encoding="utf-8") as f:
            d = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        record = {"id": f"screenagent/{session_id}/{json_path.stem}"}
        return _fail(record, "error", f"json read error: {e}")

    step_index = json_path.stem.removesuffix("_translate")
    record = {"id": f"screenagent/{session_id}/{step_index}",
              "source": "screenagent", "session_id": session_id, "step_index": step_index}

    pr = parse_actions(d.get("LLM_response_editer", ""))
    if pr.status == "error":
        return _fail(record, "error", f"parse error: {pr.note}")
    if pr.status == "empty":
        return _fail(record, "empty", "parse empty")

    conv = convert_action_sequence(pr.actions)
    if conv.status == "unsupported":
        return _fail(record, "unsupported", conv.reason)
    if conv.status == "empty":
        return _fail(record, "empty_after_conversion", "empty after conversion")

    w, h = d.get("video_width"), d.get("video_height")
    if not isinstance(w, int) or not isinstance(h, int) or w <= 0 or h <= 0:
        return _fail(record, "error", "invalid video size")

    for a in conv.actions:
        if a["type"] != "plan" and not validate_coords(a, w, h):
            return _fail(record, "unsupported", f"coord out of range: {a}")

    name = d.get("saved_image_name")
    if not isinstance(name, str) or not name:
        return _fail(record, "error", "missing saved_image_name")
    rel = f"{session_id}/images/{name}"
    if not (image_root / rel).exists():
        return _fail(record, "error", f"missing image: {rel}")

    # spec §6.2：截图实际尺寸须与声明的 video_width/video_height 一致。
    try:
        with Image.open(image_root / rel) as im:
            if im.size != (w, h):
                return _fail(record, "error",
                             f"image size mismatch: expected {(w, h)}, got {im.size}")
    except Exception as e:
        # 图像解码可抛多种异常（UnidentifiedImageError/OSError/ValueError…），
        # 任何读取失败都视为「无法校验尺寸」→ 隔离。
        return _fail(record, "error", f"image read error: {e}")

    sample = {
        "schema_version": SCHEMA_VERSION,
        "id": record["id"],
        "source": "screenagent",
        "sample_kind": "plan" if conv.actions[0]["type"] == "plan" else "act",
        "task": _pick_task(d),
        "session_id": session_id,
        "step_index": step_index,
        "screenshot": rel,
        "image_width": w,
        "image_height": h,
        "actions": conv.actions,
    }
    if keep_prompt:
        sample["prompt"] = d.get("send_prompt", "")
    return sample, None


def convert_screenagent(image_root: Path, out: Path, bad: Path, keep_prompt: bool = True) -> Stats:
    stats = Stats()
    samples, bads = [], []
    for session_dir in sorted((Path(image_root)).iterdir()):
        if not session_dir.is_dir():
            continue
        for json_path in sorted(session_dir.glob("*_translate.json")):
            if json_path.name.endswith("_neg_plan.json"):
                continue
            stats.total += 1
            sample, bad_rec = _convert_one(json_path, session_dir.name, Path(image_root), keep_prompt)
            if sample is not None:
                samples.append(sample)
                stats.bump("plan" if sample["sample_kind"] == "plan" else "act")
            else:
                # spec §7：error/empty/empty_after_conversion/unsupported 分开计数
                stats.bump(bad_rec["status"], bad_rec.get("reason", ""))
                bads.append(bad_rec)
    write_jsonl(out, samples)
    write_jsonl(bad, bads)
    return stats
