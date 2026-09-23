# 数据预处理（`scripts/preprocess/`）

把公开 GUI 数据集规范成**两种明确的样本 schema**（按 `source` 分流），供第 4 周端到端集成与第 5 周 LoRA 微调消费。

详细的数据格式分析（字段表、动作空间对照、转换与隔离规则）见 `docs/report/数据格式分析.md`。

## 目录

| 文件 | 职责 |
| --- | --- |
| `common.py` | `SCHEMA_VERSION`、`parse_actions`、`convert_action_sequence`、键名别名与白名单、`validate_coords`、`write_jsonl` |
| `convert_screenagent.py` | ScreenAgent session → §3.1 schema（`convert_screenagent`、`Stats`） |
| `convert_mind2web.py` | Mind2Web rows → §3.2 schema（`convert_mind2web`） |
| `cli.py` | argparse 入口（`main`、`build_manifest`、`derive_sidecar_paths`） |

## 数据下载

### ScreenAgent（桌面 GUI，与项目最契合）

```bash
git clone https://github.com/niuzaisheng/ScreenAgent
# 数据位于仓库 data/ScreenAgent/ 下，按 session 组织：
#   <image_root>/<session_id>/images/*.jpg            逐时间步截图
#   <image_root>/<session_id>/<step>_translate.json   每步标注（动作序列在 LLM_response_editer 里）
```

`--in` 传 `image_root`（如 `data/raw/ScreenAgent/train`），脚本会遍历其下每个 session 目录。
`*_neg_plan.json` 负样本本期忽略。

### Mind2Web（网页 GUI，用于任务规划）

```bash
# 数据集名走 HuggingFace（--in 含 "/" 即按 HF 名处理）
py -3.11 -c "from datasets import load_dataset; print(load_dataset('osunlp/Mind2Web', split='train'))"
```

- 仓库：`osunlp/Mind2Web`，`train` split 共 1009 条；test 分 Cross Task / Website / Domain。
- **默认无截图、无屏幕坐标**，动作基于浏览器 DOM（`backend_node_id`）。
- 截图需另下载 `raw_dump`（约 6.74GB），本期不下载。

## CLI 用法

所有命令必须用 `py -3.11 -m scripts.preprocess.cli` 形式（直接 `py scripts/preprocess/cli.py` 会因绝对 import 报 `ModuleNotFoundError`）。裸 `python` 指向 3.14，本项目不可用。

### ScreenAgent

```bash
py -3.11 -m scripts.preprocess.cli --dataset screenagent \
    --in data/raw/ScreenAgent/train \
    --out data/processed/screenagent.jsonl
```

`--no-prompt` 可关闭样本中 `prompt` 字段（不保留原始 `send_prompt`）；默认保留。

### Mind2Web

```bash
# 从 HuggingFace 直接拉取（--in 含 "/" 按 HF 数据集名处理）
py -3.11 -m scripts.preprocess.cli --dataset mind2web \
    --in osunlp/Mind2Web \
    --out data/processed/mind2web.jsonl

# 或从本地 JSON 读取（--in 指向一个 JSON 数组文件）
# 注意：--in 含 "/" 会被当成 HF 数据集名，本地路径请用反斜杠写法或直接放在当前目录
py -3.11 -m scripts.preprocess.cli --dataset mind2web \
    --in "data\raw\mind2web_train.json" \
    --out data/processed/mind2web.jsonl
```

CLI 结束会打印一行统计，例如：

```
done: 20 total, act=0, plan=0, unsupported=0
```

## 输出：三路文件

附属文件一律从 `--out` 派生（避免多数据集同名覆盖）。设 `--out` 为 `<base>.jsonl`：

| 文件 | 内容 |
| --- | --- |
| `<base>.jsonl` | 主数据，每行一个样本 |
| `<base>.unsupported.jsonl` | 隔离记录，每行含 `id` / `status` / `reason` |
| `<base>.manifest.json` | 单行 JSON，记录本次转换的可复现信息 |

### 主数据 schema（`schema_version = "1.0"`）

统一约定：输出为 JSONL，每行一个样本，均带 `schema_version`；执行动作的 `type` 用 `ActionType.value`（小写）；路径一律 `/` 分隔。

**ScreenAgent（`source="screenagent"`，一条记录 = 一个原始标注文件 = 一个时间步）**

```json
{
  "schema_version": "1.0",
  "id": "screenagent/<session_id>/<timestamp>",
  "source": "screenagent",
  "sample_kind": "act",
  "task": "上网查找冯诺依曼的相关资料",
  "session_id": "02ea503d419c440cbda9e42263706d6a",
  "step_index": "2023-12-20_19-33-28-140419",
  "screenshot": "02ea503d419c440cbda9e42263706d6a/images/2023-12-20_19-33-28-140419.jpg",
  "image_width": 1024,
  "image_height": 768,
  "prompt": "<原始 send_prompt>",
  "actions": [
    {"type": "click", "x": 487, "y": 193},
    {"type": "type", "text": "冯诺依曼"}
  ]
}
```

- `sample_kind`：`"act"`（执行动作）或 `"plan"`（规划）。
- `screenshot`：相对 `--in`（image_root）的完整路径，含 `session_id` 前缀。
- `prompt`：原始 `send_prompt`，`--no-prompt` 时不输出。
- `actions`：同一观察截图下的有序动作数组。执行动作字段对齐 `src/control/actions.py` 的 `Action.validate()`：

  | type | 必填字段 |
  | --- | --- |
  | `move` / `click` / `double_click` / `right_click` | `x`、`y`（int） |
  | `scroll` | `scroll_amount`（int，正向上负向下） |
  | `drag` | `x`、`y`（起点）、`x2`、`y2`（终点） |
  | `type` | `text`（str） |
  | `press` | `key`（str） |
  | `hotkey` | `keys`（非空 str 列表） |
  | `plan` | `text`（str，规划文本，不构造 `Action`） |

**Mind2Web（`source="mind2web"`，轻量规划样本）**

```json
{
  "schema_version": "1.0",
  "id": "mind2web/<annotation_id>",
  "source": "mind2web",
  "task": "Find the cheapest laptop...",
  "steps": [
    {"action_uid": "xxx", "op": "CLICK", "value": null, "repr": "CLICK [button] Search"}
  ]
}
```

`steps[].op` ∈ {CLICK, TYPE, SELECT}；`repr` 取自 `action_reprs` 对应项；`value` 取自 `operation.value`；`action_uid` 保留用于溯源。

### 隔离文件（`<base>.unsupported.jsonl`）

每行一个被隔离的样本，含 `id` / `status` / `reason`。`status` 取值：

| status | 含义 |
| --- | --- |
| `error` | 记录/元数据缺陷：读不出、JSON 解析失败、字段缺失、视频尺寸非法或与截图实际尺寸不符 |
| `empty` | 原始动作数组为空 |
| `empty_after_conversion` | 原始动作非空，但转换后为空（如仅含 `WaitAction` / `EvaluateSubTaskAction`） |
| `unsupported` | 动作存在但无法用于训练：转换不支持（如中键点击、非左键拖拽、修饰键按住期间出现鼠标操作、样本结束未释放修饰键、键盘键名不在白名单），或坐标越界 |

ScreenAgent 的动作序列转换是**全有或全无**的：任一动作触发 unsupported，整个样本隔离，不产出「语义已改变的残余序列」。例如 `Ctrl down → click → Ctrl up` 整条隔离，而不是删掉 down/up 后变成普通点击。

Mind2Web 的隔离规则：`action_reprs` 与 `actions` 长度不一致 → 隔离（不按较短列表截断，避免错配或丢失收尾步骤）；`op` 不在 CLICK/TYPE/SELECT → 隔离。

### manifest（`<base>.manifest.json`）

```json
{"schema_version": "1.0", "script_version": "0.1.0", "dataset": "screenagent",
 "split": "train", "converted_at": "<ISO8601 UTC>", "source_revision": "local",
 "command": "--dataset screenagent --in ... --out ...",
 "counts": {"total": 20, "act": 14, "plan": 4, "unsupported": 2, "empty": 0,
            "empty_after_conversion": 0, "error": 0}}
```

- `source_revision`：ScreenAgent 记 git commit hash（本期为 `"local"`）；Mind2Web 走 HF 时记数据集 fingerprint。
- `counts`：`total` 为处理总数，其余为各分流计数。
- 确定性约定：主数据与隔离数据按固定顺序写出，同一输入重复运行逐字节一致；manifest 中仅 `converted_at`（运行时间戳）为易变字段。
- ScreenAgent **按 `session_id` 划分**训练/验证（同一 session 的样本不跨 split，避免同一轨迹相邻截图泄漏）。本期默认全部进 train，不生成验证集。

## 已知限制

- **Mind2Web 无坐标、无截图**：动作基于浏览器 DOM，本 schema 只保留「操作类型 + 目标描述」，不能直接用于坐标级执行训练；适合任务规划/子任务拆解。截图还原不在本期范围。
- **隔离率**：ScreenAgent 中无法可靠还原的动作（中键、非左键拖拽、修饰键与鼠标混用等）整条隔离而非近似，因此执行训练集保真但覆盖略窄。
- **`*_neg_plan.json` 负样本**本期忽略。
- **Mind2Web `--in` 的路径判别**：靠「字符串里是否含 `/`」区分 HF 数据集名与本地文件，因此本地路径不能用正斜杠写法（用反斜杠，或直接把文件放当前目录）。
- **`docs/`、`tests/`、`data/`、`models/` 被 `.gitignore` 排除**：只有 `scripts/preprocess/` 入库。

## 开发

```bash
# 单元测试（纯逻辑，无需图形桌面，CI 可跑）
py -3.11 -m pytest tests/test_preprocess.py -q
```
