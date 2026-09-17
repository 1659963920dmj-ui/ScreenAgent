# CLAUDE.md

本文件为 Claude Code（及后续 AI 编程助手会话）提供项目上下文与协作规范。改动代码前请先阅读本文件。

## 项目简介

**基于多模态大模型的桌面 GUI 智能体（Desktop GUI Agent）**：一个能「看懂屏幕、操作电脑」的智能体原型。用户用自然语言下达指令，智能体通过「屏幕感知 → 任务规划 → 动作执行 → 结果反馈」的闭环，在真实桌面环境（Windows / macOS / Linux）上完成打开应用、浏览搜索、操作文件、发送消息等任务。

这是一个 8 周（2 个月）的实习项目，目标不仅是做出可运行的 Demo，还要覆盖多模态感知、任务规划、工具调用、模型微调、系统评估等完整算法能力，最终沉淀为求职作品集（代码仓库 + 技术报告 + 演示视频）。

核心技术参考：UI-TARS、Claude Computer Use、ScreenAgent。

## 技术栈

| 类别 | 组件 |
| --- | --- |
| 语言 / 框架 | Python 3.11.9（用 `py -3.11` 调用），PyTorch 2.12.1+cu126 |
| 屏幕截图 | PyAutoGUI、mss（高性能截图） |
| UI 元素识别 | OpenCV、PaddleOCR、EasyOCR |
| 鼠标键盘控制 | PyAutoGUI、pynput |
| Agent 框架 | LangChain、LlamaIndex |
| 多模态大模型 | Qwen-VL-Chat、GLM-4V-9B、Llama 3.2 Vision 11B |
| 模型部署 | Transformers（vLLM 仅 Linux/WSL2，Windows 原生不可用） |
| 参数高效微调 | PEFT（LoRA）、Accelerate、bitsandbytes（4/8 bit 量化） |
| 数据 | Hugging Face Datasets、Pandas |
| 可视化 | Matplotlib、Seaborn |
| 版本控制 | Git + GitHub |

## 系统架构与数据流

```
用户指令(自然语言)
      │
      ▼
┌─────────────┐   ┌──────────────┐   ┌─────────────┐   ┌──────────────┐
│  任务规划     │◄──│  多模态大模型  │──►│  屏幕感知     │──►│  动作执行     │
│ (Agent 框架) │   │ (Qwen-VL 等) │   │ 截图+OCR+定位 │   │ 鼠标键盘控制  │
└──────┬──────┘   └──────────────┘   └──────┬──────┘   └──────┬──────┘
       │                                    │                 │
       └─────────────► 结果反馈 ◄────────────┴─────────────────┘
```

- **感知模块**：截图 → OCR 文字识别 → UI 元素坐标定位与边界框 → 生成结构化屏幕描述喂给模型。
- **规划模块**：Agent 框架接收「用户指令 + 当前屏幕状态」，产出下一步动作（action + 坐标 + 参数）。
- **控制模块**：将动作翻译为底层鼠标键盘操作（点击、输入、滚动、拖拽）。
- **模型层**：可切换本地部署（Transformers）与 API 调用，第 5 周后加入 LoRA 微调权重。

## 建议的目录结构

项目当前为空仓库，建议按如下结构组织（可随开发推进调整）：

```
ScreenAgent/
├── CLAUDE.md                 # 本文件
├── README.md                 # 项目说明（第 8 周完善）
├── 项目大纲.md
├── docs/
│   ├── PRD.md                # 产品需求文档
│   ├── 调研报告/              # 第 1 周交付物
│   └── 评估报告/              # 第 5/7 周交付物
├── requirements.txt          # Python 依赖
├── configs/                  # 模型、Agent、微调的配置文件
├── src/
│   ├── perception/           # 屏幕截图 + UI 元素识别 + 坐标定位
│   ├── control/              # 鼠标键盘控制封装
│   ├── agent/                # Agent 框架、任务规划、提示词模板
│   ├── llm/                  # 大模型加载与调用（本地 + API）
│   ├── finetune/             # 数据构建 + LoRA 微调脚本
│   └── eval/                 # 任务测试集、指标统计、可视化
├── scripts/                  # 数据预处理、一键运行脚本
├── tests/                    # 单元测试（对应第 2 周交付物）
├── notebooks/                # 实验性 notebook
├── data/                     # 数据集（加入 .gitignore）
└── models/                   # 模型权重（加入 .gitignore）
```

## 开发规范

- **环境**：Python 3.11.9（系统已装，**不使用虚拟环境**，依赖装在 3.11 的用户 site-packages）；用 `requirements.txt` 或 `pyproject.toml` 锁定依赖。
- **Python 调用约定**：系统 PATH 里裸 `python` 指向 Python 3.14（该环境依赖不全、paddle 无法安装），**本项目一律用 `py -3.11` 前缀**（pip 用 `py -3.11 -m pip ...`），不要用裸 `python`。
- **GPU**：本地 NVIDIA GeForce RTX 4060 Laptop GPU（8GB 显存）；无 GPU 时模型推理/微调回退到 Google Colab 或 CPU。
- **代码风格**：遵循 PEP 8；模块化拆分，感知、控制、Agent、模型层各自独立，通过清晰的接口（类/函数）解耦，避免在单一脚本里堆叠逻辑。
- **配置与密钥分离**：API Key、模型路径等敏感/环境相关配置放进 `configs/` 或环境变量，不硬编码、不入库。
- **测试**：每个核心模块配单元测试（第 2 周起），改动后先跑对应测试再提交。
- **日志**：统一使用 Python `logging`（第 6 周加入任务执行状态监控与日志）。

## 常用命令

```bash
# 安装依赖
py -3.11 -m pip install -r requirements.txt

# 运行单元测试
py -3.11 -m pytest tests/

# 运行端到端 Demo（第 4 周起，需有图形桌面环境）
py -3.11 -m src.agent.run --task "打开浏览器并搜索 ScreenAgent"

# 数据预处理（第 3 周）
py -3.11 scripts/preprocess.py --dataset screenagent

# LoRA 微调（第 5 周）
py -3.11 src/finetune/train_lora.py --config configs/lora.yaml
```

## 关键约束与注意事项

- **Python 版本**：用 3.11.9，不要用 3.14（paddlepaddle / PaddleOCR 在 3.14 无 wheel，无法安装；3.11 是深度学习生态最稳定的版本）。3.11 为 Microsoft Store 版，`Scripts` 目录不在 PATH，个别 CLI 工具（torchrun、accelerate 等）需用 `py -3.11 -m` 方式调用。
- **GUI 自动化需要真实图形桌面**：PyAutoGUI / mss / pynput 在无头环境（CI、无显示器、部分容器）下会失败。开发与测试需在带桌面的本机环境进行，CI 只跑不涉及真实屏幕的纯逻辑测试。
- **坐标与分辨率敏感**：屏幕坐标受分辨率和缩放（DPI）影响，跨分辨率适配是核心难点之一（第 2、7 周重点），控制与感知需统一坐标系约定。
- **模型体积与显存**：8GB 显存下，Qwen-VL-Chat 7B 需 4bit 量化推理；GLM-4V-9B / Llama 3.2 Vision 11B 推理勉强、LoRA 微调基本不可行——微调建议选 Qwen2-VL-2B/3B 级别小模型，大模型走 API 兜底。
- **跨平台差异**：Windows / macOS / Linux 的键位、剪贴板、权限模型不同，控制模块需做平台抽象（第 2 周起）。
- **安全边界**：GUI 智能体会真实操作桌面，测试时避免误触敏感应用/数据，动作执行层建议保留「确认/日志」机制，便于排查与回滚。

## 8 周开发节奏（速览）

1. **W1** 技术调研 + 环境搭建 → 调研报告、环境配置文档
2. **W2** 感知与控制模块 → 模块代码 + 单元测试
3. **W3** 公开数据集 + Agent 框架 → 预处理脚本 + 框架代码
4. **W4** 端到端集成 → 系统原型 v1.0 + 基础任务测试
5. **W5** LoRA 微调 → 微调权重 + 效果对比报告
6. **W6** 鲁棒性优化 → 系统 v2.0 + 鲁棒性测试
7. **W7** 全面评估 → 评估报告 + 可视化
8. **W8** 总结与作品集 → 代码仓库 + 技术报告 + 演示视频

完整交付物明细见 [项目大纲.md](项目大纲.md)。
