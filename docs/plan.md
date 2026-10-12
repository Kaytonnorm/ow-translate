# 项目总体计划 — 守望先锋聊天框实时翻译工具

状态：v3（已并入用户确认的 8 项修改 + 第 1 轮审核意见），计划审核通过。

## 一、技术选型（已确认）

| 层 | 选型 |
|---|---|
| 桌面端 | Electron + TypeScript + Vue3。**悬浮窗置顶、鼠标穿透、全局快捷键、区域框选全部在 Electron 主进程实现** |
| 后端 | Python 3.12 + FastAPI（阶段 2 引入 server） |
| OCR | PaddleOCR 3.x（当前锁定 3.0.3）+ PaddlePaddle CPU 版 3.0.0 |
| 截图 | mss；Python 侧平台接口只有 ScreenCapture |
| 预处理 | opencv-python-headless |
| 翻译 | DeepSeek API（OpenAI 兼容），模型 ID 从配置读取（默认 `deepseek-flash`），`thinking disabled` + `reasoning_effort low` |
| 去重 | rapidfuzz + dhash 跳帧（阶段 2） |
| 缓存 | 内存 LRU + SQLite（阶段 3），Redis 可选、无则降级 |
| 打包 | PyInstaller 后端 exe → Electron extraResources → electron-builder（阶段 6） |

### 关键 API 事实（已查官方文档确认）

- PaddleOCR 3.x：`PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False, ocr_version="PP-OCRv5", lang="korean")`。`use_angle_cls` 已弃用。
- 韩语模型 `korean_PP-OCRv5_mobile_rec` 同时支持韩文/英文/数字，正好覆盖韩英混合聊天。
- 结果对象：`res["rec_texts"]`（文本）、`res["rec_scores"]`（置信度）、`res["rec_polys"]`（四点框）。内置 `text_rec_score_thresh` 可用。
- DeepSeek 当前模型 ID：`deepseek-flash`、`deepseek-v4-pro`。低延迟参数：`thinking={"type":"disabled"}`、`reasoning_effort="low"`。

## 二、目录结构

```
ow-translate/
├── AGENTS.md
├── docs/{plan.md, windows-checklist.md, paddle-windows-notes.md}
├── backend/
│   ├── main.py            # CLI：--image / --region / --no-translate / --debug
│   ├── config.py          # 配置(JSON + env)，key 仅读 DEEPSEEK_API_KEY
│   ├── preprocess.py      # 放大/灰度/二值化/对比度，各项可开关
│   ├── ocr.py             # PaddleOCR 封装（懒加载单例）
│   ├── translate.py       # DeepSeek 调用（超时/重试/合并请求）
│   ├── pipeline.py        # （阶段 2）实时循环
│   ├── server.py          # （阶段 2）FastAPI WS + HTTP
│   └── tests/
├── platforms/             # 平台相关；命名避开标准库 platform
│   ├── base.py            # ScreenCapture 抽象接口（Python 侧唯一平台接口）
│   ├── mac/               # 仅供开发调试
│   └── windows/           # 正式目标：mss + DPI 物理像素处理
├── tools/make_samples.py  # Pillow 生成韩/英/混合/低对比度测试图 + 连续帧序列
├── samples/               # 生成图；samples/real/ 真实截图（gitignore）
├── desktop/               # （阶段 4）Electron
└── .github/workflows/build-windows.yml  # （阶段 6）
```

## 三、阶段 1 详细计划（当前）

1. **环境**：uv + Python 3.12.14 venv；requirements.txt 锁定 Mac/Windows 同版本（paddlepaddle==3.0.0、paddleocr==3.0.3、opencv-python-headless、pillow、rapidfuzz、httpx、pytest）。镜像源不写入配置，仅文档可选项。
2. **samples**：`tools/make_samples.py` 生成 5 张静态图（`test_korean.png`、`test_english.png`、`test_mixed.png`、`test_slang.png`、`test_low_contrast.png`）+ 1 组连续帧序列 `test_seq_*.png`（阶段 2 用）。字体做缺失回退。
3. **preprocess.py**：`PreprocessConfig(scale=2.5, grayscale, adaptive_threshold, contrast_boost)`，每项可开关，`--debug` 保存中间图到 `debug/`（gitignore）。
4. **ocr.py**：懒加载单例；输出 `[{text, score, box}]`；置信度 < 阈值（默认 0.6，可配）过滤并记日志。
5. **translate.py**：DeepSeek `/chat/completions`（OpenAI 兼容）；多条消息合并一次请求，**要求模型返回带编号的 JSON 数组，按编号对应原文**；超时 8s、最多 2 次重试、失败给 `[翻译失败: 原因]`；key 仅环境变量。
6. **platforms/base.py**：`ScreenCapture` 协议（grab(region)、physical_scale()）；`platforms/mac/mss_capture.py` 开发用实现；**阶段 1 完整实现 `platforms/windows/mss_capture.py`**（mss + 初始化时调用 SetProcessDpiAwareness，保证 125%/150% 缩放下 grab 输入/输出均为物理像素），代码写好但在用户实机跑完清单前，AGENTS.md 验证表中一律标注「未验证（待实机清单）」。
7. **main.py**：`--image`（Mac 全链路验收）、`--region "x,y,w,h"`（物理像素，经 ScreenCapture 截屏后走同一管线）、`--no-translate`、`--debug`。不做 select_region（阶段 5 由 Electron 实现）。
8. **测试**（pytest，Mac/Windows 均可跑）：preprocess 开关行为、OCR 输出结构与阈值过滤（mock paddle）、translate 请求构造与编号 JSON 解析（mock httpx，不触网）；补充：缺少 `DEEPSEEK_API_KEY` 时在发请求前即报明确错误；重试 2 次后仍失败返回 `[翻译失败: 原因]`。
9. **文档**：windows-checklist.md（阶段 1 部分 + 预置阶段 4 悬浮窗高置顶层级验证项）、paddle-windows-notes.md（CPU 版、VC++ Redist、AVX、模型下载、DPI 物理像素——SetProcessDpiAwareness 在 platforms/windows/ 初始化时调用）、.gitignore、.env.example、AGENTS.md 维护。**.gitignore 就位后先提交基线文档，再让用户放 samples/real/ 真实截图**，避免真实截图被误 add。
10. **真实截图验收**：用户将真实游戏聊天截图放入 `samples/real/`（gitignore），运行后报告 OCR 准确率与典型错误。

### 阶段 1 验收标准

- Mac：`python main.py --image samples/test_korean.png` 输出原文+置信度+中文译文。
- Mac：`samples/real/` 真实截图 OCR 准确率报告。
- Windows（手动清单）：实时截取屏幕区域识别成功；125%/150% 缩放下坐标为物理像素且正确。**注：Windows 项在用户实机执行清单并回传结果前，状态为「未验证」，不得视为已验收。**

## 四、后续阶段简述

- **阶段 2**：实时循环（默认 1s）、dhash 跳帧、规范化+rapidfuzz(85) 去重（NFC、去空白、统一大小写）、连续帧回放验收、FastAPI WS 推送骨架。
- **阶段 3**：glossary.json（原词/译文/语言/备注）命中注入、内存 LRU + SQLite 缓存、合并翻译落地、缓存命中统计。
- **阶段 4**：Electron 悬浮窗（透明/置顶(screen-saver 级别)/穿透/编辑模式拖动缩放）、最近 N 条淡出、全局快捷键、Mac 预览 UI；Windows 清单验证无边框全屏游戏上方可见性。
- **阶段 5**：Electron 设置页（可视化框选、间隔、阈值、API、样式）、术语表管理、配置持久化。
- **阶段 6**：性能统计、GitHub Actions（windows-latest）PyInstaller + electron-builder 出包、README 完整化（含反作弊风险说明）。

## 五、Windows 安装注意事项（详见 docs/paddle-windows-notes.md）

- CPU 版 paddlepaddle；先装 VC++ Redistributable 2015-2022；需 AVX 指令集；Python 3.8~3.12 64 位（用 3.12）。
- 首次运行联网下载模型（~20MB）；杀软可能拦截，清单含白名单说明；镜像源仅作为文档可选项。

## 六、风险与待定

- PyInstaller 打包 paddleocr 体积大（~1GB）且偶有隐藏 import 问题：阶段 6 处理，保留源码模式降级路径。
- PP-OCRv5 韩语 mobile 模型对游戏小字号/描边字的准确率未知，依赖 samples/real/ 报告评估，必要时调整预处理或换 server 模型。
