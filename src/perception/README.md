# perception — 桌面感知模块

屏幕感知的核心：**截图 → 文字识别 + UI 元素检测 → 合并 → 结构化描述**，为下游
任务规划（Agent）提供「看懂屏幕」的能力。

## 数据流

```
截图 RGB ──► UIElementDetector.detect() ──► [UIElement(button/input/icon)]
截图 RGB ──► OCREngine.recognize()       ──► [TextDetection]
                          │
                          ▼
        merge_text_and_elements(texts, elements) ──► [UIElement(text + label 已填充)]
                          │
                          ▼
        describe_elements() / elements_to_dicts() ──► 结构化屏幕描述（喂给模型）
        draw_elements() / draw_detections()       ──► 可视化预览图
```

## 文件说明

| 文件 | 功能 |
| --- | --- |
| [screen.py](screen.py) | 跨平台屏幕截图。`ScreenCapture`（mss / pyautogui 双后端）返回 `Screenshot`（RGB 图像 + 尺寸 + 原点偏移），`to_screen()` 把图像坐标转屏幕绝对坐标 |
| [ocr.py](ocr.py) | 文字识别。`OCREngine` 封装 PaddleOCR / EasyOCR，`recognize()` 返回 `TextDetection` 列表，模型懒加载 |
| [detector.py](detector.py) | UI 元素视觉检测。`UIElementDetector` 用 OpenCV 启发式识别 input（矩形边框长条）、button（矩形边框）、icon（高饱和彩色区域） |
| [detection.py](detection.py) | 数据结构与合并逻辑。`TextDetection` / `UIElement` 数据类，`merge_text_and_elements()` 把 OCR 文字框合并进视觉元素（纯几何、无 cv2 依赖） |
| [describe.py](describe.py) | 结构化屏幕描述。`describe_elements()`（编号文本）与 `elements_to_dicts()`（JSON 字典）把元素列表格式化为下游 Agent 可消费的描述 |
| [visualize.py](visualize.py) | 可视化。`draw_detections()` / `draw_elements()` 用 PIL 在截图上绘制边界框与中文标签 |
| [__init__.py](__init__.py) | 包入口，统一导出上述公共接口 |

## 坐标约定

- `TextDetection.bbox` / `UIElement.bbox` 与 `.center` 使用**图像坐标**（输入图像的
  像素坐标，原点左上角）。
- 全屏截图时图像坐标 = 屏幕绝对坐标；**区域截图**（`Screenshot.left/top` 非 0）时两者不同，
  执行点击前需用 `Screenshot.to_screen(x, y)` 转换。
- `describe.py` 输出的坐标已转换为**屏幕绝对坐标**（内部 +left/top），下游可直接用于点击。

## 快速使用

```python
from src.perception import (
    ScreenCapture, OCREngine, UIElementDetector,
    merge_text_and_elements, describe_elements,
)

shot = ScreenCapture().capture()                       # 截图
texts = OCREngine().recognize(shot.image)              # 文字识别
elements = UIElementDetector().detect(shot.image)      # UI 元素检测
merged = merge_text_and_elements(texts, elements)      # 合并
print(describe_elements(merged, shot.width, shot.height))  # 结构化描述（截图尺寸 + 坐标）
```

一键可视化验证见 [scripts/verify_ui_detect.py](../../scripts/verify_ui_detect.py)。

## 已知局限

- UI 元素检测为第 2 周 OpenCV 启发式粗版：低饱和图标、深色无边框按钮可能检不出，
  网页彩色内容可能误判为 icon。第 6 周将替换为深度学习方案，接口不变。
- 真实深色主题实测（Cursor 等扁平 UI）暴露三处已知误检/漏检：无边框输入框（仅占位文字）
  检不出、代码语法高亮 token 被误判为 icon、低饱和单色图标漏检。根因是「矩形边框 +
  高饱和彩色」两个启发式假设与扁平 UI 设计语言冲突，纯视觉调参无法解决；第 3 周引入
  OCR 文字框融合（用文字区排除 token 误检、用占位文字定位输入框），第 6 周换模型方案。
- OCR 依赖 PaddleOCR（需 `py -3.11` 环境），模型首次加载会下载权重。
