# AGENTS.md — 项目约束与进度

## 项目

守望先锋聊天框实时翻译工具：截屏聊天框区域 → 预处理 → OCR(韩/英) → 去重 → 术语表 + DeepSeek 翻译 → 透明悬浮窗。

- 开发机：macOS（Apple Silicon，系统 Python 3.14 不可用，用 uv 管理 Python 3.12）。
- 目标运行环境：Windows 10/11。所有 Windows 专属功能必须经手动验证清单确认，**未验证不得写成"已验证"**。

## 硬性约束（最高优先级）

1. 只做「屏幕截图 + OCR」，严禁读取游戏内存、注入进程、hook 游戏、模拟输入。
2. 游戏需运行在无边框窗口模式；悬浮窗不抢焦点、支持鼠标穿透。
3. API key 只从环境变量 `DEEPSEEK_API_KEY` 读取，不得写死在代码/日志/提交中。
4. 路径一律 pathlib，不硬编码盘符或反斜杠；文本文件 UTF-8 + LF。
5. 核心逻辑平台无关，能在 Mac 上用 `--image` 完整跑通；平台相关代码隔离在 `platforms/`。
6. 不引入不必要的大型框架或重型依赖。
7. 用户确认前不跨阶段开发。

## 技术决策记录（已确认）

- 桌面端 Electron + TypeScript + Vue3（悬浮窗/托盘/快捷键/框选全在 Electron 主进程）；后端 Python 3.12 + FastAPI。
- Python 侧平台接口**只保留 ScreenCapture**；置顶/穿透/快捷键/框选均由 Electron 实现。
- PaddleOCR 3.x 新 API：`use_angle_cls` 已弃用，改用 `use_doc_orientation_classify/use_doc_unwarping/use_textline_orientation=False`；韩语用 `ocr_version="PP-OCRv5"` + `lang="korean"`（v6 不支持韩语）；结果字段 `rec_texts/rec_scores/rec_polys`。
- DeepSeek：OpenAI 兼容格式，模型 ID 从配置读取（当前默认 `deepseek-flash`）；低延迟：`thinking={"type":"disabled"}` + `reasoning_effort="low"`；多条消息合并为一次请求，要求返回带编号 JSON 数组按编号对应。
- 翻译合并、悬浮窗 Electron 原生穿透方案：已获用户确认。
- 镜像源不硬编码，只在文档中作为可选项。
- 阶段 1 不做 select_region.py；只支持 `--region` 手动传坐标，框选功能阶段 5 在 Electron 中实现。

## 目录结构

```
ow-translate/
├── AGENTS.md            # 本文件（持续维护）
├── docs/plan.md         # 总体计划（经 reviewer 审核后冻结，阶段推进时更新）
├── docs/windows-checklist.md
├── docs/paddle-windows-notes.md
├── backend/             # Python 核心逻辑（平台无关）
│   ├── main.py          # CLI 入口
│   ├── config.py / preprocess.py / ocr.py / translate.py
│   └── tests/
├── platforms/           # 平台相关（注意：不叫 platform，避免遮蔽标准库）
│   ├── base.py          # ScreenCapture 抽象接口
│   ├── mac/  windows/
├── tools/make_samples.py
├── samples/             # 测试图；samples/real/ 放真实截图（gitignore）
└── .opencode/agents/reviewer.md
```

## 常用命令

```bash
# 环境（Mac，uv）
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt

# 阶段 1 验收
.venv/bin/python backend/main.py --image samples/test_korean.png
.venv/bin/python backend/main.py --image samples/real/xxx.png --debug
.venv/bin/python backend/main.py --region "100,200,800,300"

# 测试
.venv/bin/python -m pytest backend/tests -q
```

## 审核流程（必须遵守）

1. 制定计划后，写入 docs/plan.md，然后调用 reviewer 子 agent 审核计划。
   根据意见修改计划，最多迭代 2 轮，仍有分歧时停下来问用户。
2. 用户确认计划后才开始编码。
3. 每个阶段完成后，运行测试，然后调用 reviewer 审核本阶段改动。
4. 审核结果为"需修改"时，修复所有阻塞项后再次审核，最多 3 轮。
5. 审核通过后，汇总给用户：做了什么、审核意见、剩余风险。

## 当前进度

- 阶段 1 进行中。
- docs/plan.md v3：已按 reviewer 意见修正（Windows 截屏实现纳入阶段 1、样例图命名、DPI aware 归属、translate 缺 key 测试、基线提交），计划已通过审核，开始编码。
- 环境：.venv (Python 3.12.14) 已创建；依赖安装后台进行中（paddlepaddle 3.0.0 + paddleocr 3.0.3 等）。

## Windows 验证状态

| 功能 | 状态 |
|---|---|
| （尚无可验证功能，随阶段推进更新） | — |
