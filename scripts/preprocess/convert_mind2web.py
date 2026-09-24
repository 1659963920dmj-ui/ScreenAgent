"""Mind2Web 数据集 → 轻量规划样本 schema（无坐标无截图）。"""
from __future__ import annotations

from pathlib import Path

from scripts.preprocess.common import SCHEMA_VERSION, write_jsonl
from scripts.preprocess.convert_screenagent import Stats

# spec §3.2：steps[].op 只能是这三个操作。
ALLOWED_OPS = {"CLICK", "TYPE", "SELECT"}


def _op_value(act: dict):
    """安全取 (op, value)：operation 缺失/null/非 dict/无 op 键四态统一归 (None, None)。

    `operation` 为 truthy 非 dict（如 "CLICK"）时不做 `.get`，避免 AttributeError 逃逸契约（Ruling F16）。
    """
    op_obj = act.get("operation")
    if not isinstance(op_obj, dict):
        return None, None
    return op_obj.get("op"), op_obj.get("value")


def convert_mind2web(rows, out: Path, bad: Path) -> Stats:
    stats = Stats()
    samples, bads = [], []
    for r in rows:
        stats.total += 1
        if not isinstance(r, dict):
            stats.bump("error", "row is not a dict")
            bads.append({"id": "mind2web/<non-dict>", "status": "error",
                         "reason": "row is not a dict"})
            continue
        aid = r.get("annotation_id", "")
        task = r.get("confirmed_task", "")
        if not isinstance(task, str):
            task = ""
        reprs = r.get("action_reprs") or []
        acts = r.get("actions") or []
        if not isinstance(reprs, list) or not isinstance(acts, list):
            stats.bump("error", "action_reprs/actions is not a list")
            bads.append({"id": f"mind2web/{aid}", "status": "error",
                         "reason": "action_reprs/actions is not a list"})
            continue
        if len(reprs) != len(acts):
            stats.bump("unsupported", "repr/actions length mismatch")
            bads.append({"id": f"mind2web/{aid}", "status": "unsupported",
                         "reason": "repr/actions length mismatch"})
            continue
        if not all(isinstance(a, dict) for a in acts):
            stats.bump("error", "action is not a dict")
            bads.append({"id": f"mind2web/{aid}", "status": "error",
                         "reason": "action is not a dict"})
            continue
        op_vals = [_op_value(a)[0] for a in acts]
        if not all(op in ALLOWED_OPS for op in op_vals):
            bad_op = next(op for op in op_vals if op not in ALLOWED_OPS)
            stats.bump("unsupported", f"op {bad_op!r} not in CLICK/TYPE/SELECT")
            bads.append({"id": f"mind2web/{aid}", "status": "unsupported",
                         "reason": f"op {bad_op!r} not in CLICK/TYPE/SELECT"})
            continue
        steps = []
        for rep, act in zip(reprs, acts):
            op, value = _op_value(act)
            steps.append({
                "action_uid": act.get("action_uid"),
                "op": op,
                "value": value,
                "repr": rep,
            })
        samples.append({
            "schema_version": SCHEMA_VERSION,
            "id": f"mind2web/{aid}",
            "source": "mind2web",
            "task": task,
            "steps": steps,
        })
        # Mind2Web 无坐标无截图，属「规划」样本（spec §2.1「用于任务规划」），
        # 计入 plan 使 manifest 的 total 可被分类解释（与 ScreenAgent 的 act/plan 对齐）。
        stats.bump("plan")
    write_jsonl(out, samples)
    write_jsonl(bad, bads)
    return stats
