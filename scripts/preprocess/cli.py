"""命令行入口：把 ScreenAgent / Mind2Web 转成统一 JSONL。"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.preprocess.common import SCHEMA_VERSION, write_jsonl
from scripts.preprocess.convert_mind2web import convert_mind2web
from scripts.preprocess.convert_screenagent import Stats, convert_screenagent

# spec §7：manifest 须记录产出该数据集的脚本版本。
SCRIPT_VERSION = "0.1.0"


def derive_sidecar_paths(out: Path) -> tuple[Path, Path, Path]:
    base = out.with_suffix("")  # 去掉 .jsonl
    return out, Path(f"{base}.unsupported.jsonl"), Path(f"{base}.manifest.json")


def build_manifest(dataset: str, split: str, total: int, counts: dict,
                   source_revision: str, command: str = "") -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "script_version": SCRIPT_VERSION,
        "dataset": dataset,
        "split": split,
        "converted_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": source_revision,
        "command": command,
        "counts": {"total": total, **counts},
    }


def _counts(s: Stats) -> dict:
    return {"act": s.act, "plan": s.plan, "unsupported": s.unsupported,
            "empty": s.empty, "empty_after_conversion": s.empty_after_conversion,
            "error": s.error}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="GUI 数据集预处理")
    p.add_argument("--dataset", required=True, choices=["screenagent", "mind2web"])
    p.add_argument("--in", dest="inp", required=True, help="输入目录/文件或 HF 数据集名")
    p.add_argument("--out", required=True, help="输出 .jsonl 路径")
    p.add_argument("--no-prompt", action="store_true", help="不保留 send_prompt")
    args = p.parse_args(argv)

    out, bad, manifest_path = derive_sidecar_paths(Path(args.out))
    revision = "local"
    if args.dataset == "screenagent":
        stats = convert_screenagent(Path(args.inp), out, bad, keep_prompt=not args.no_prompt)
        split = Path(args.inp).name
    else:
        from datasets import load_dataset  # 惰性 import：仅 mind2web 分支需要
        ds = load_dataset(args.inp, split="train") if "/" in args.inp else None
        if ds is None:
            import json as _json
            with open(args.inp, "r", encoding="utf-8") as f:
                rows = _json.load(f)
        else:
            rows = ds
            revision = getattr(ds, "_fingerprint", "local")
        stats = convert_mind2web(rows, out, bad)
        split = "train"

    command = " ".join(sys.argv[1:]) if argv is None else " ".join(argv)
    manifest = build_manifest(args.dataset, split, stats.total, _counts(stats),
                              revision, command)
    write_jsonl(manifest_path, [manifest])
    print(f"done: {stats.total} total, act={stats.act}, plan={stats.plan}, "
          f"unsupported={stats.unsupported}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
