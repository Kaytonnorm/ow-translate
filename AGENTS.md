# AGENTS.md — 项目约束与进度

## 项目

守望先锋聊天框实时翻译工具：截屏聊天框区域 → 预处理 → OCR(韩/英) → 去重 → 术语表 + DeepSeek 翻译 → 透明悬浮窗。

- 开发机：macOS（Apple Silicon，系统 Python 3.14 不可用，用 uv 管理 Python 3.12）。
- 目标运行环境：Windows 10/11。所有 Windows 专属功能必须经手动验证清单确认，**未验证不得写成"已验证"**。

## 硬性约束（最高优先级）

1. 只做「屏幕截图 + OCR」，严禁读取游戏内存、注入进程、hook 游戏、模拟输入。
2. 游戏需运行在无边框窗口模式；悬浮窗不抢焦点、支持鼠标穿透。
3. API key 只从环境变量 `DEEPSEEK_API_KEY` 读取，不得写死在代码/日志/提交中。
   **提交前必须自查**：`git grep -E "sk-[A-Za-z0-9]{20,}" --staged`（暂存内容）无匹配才可提交；
   曾发生 key 误入 .env.example 事故（key 已作废、历史已清除），此后再犯视为严重违规。
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
## 自动执行与审核流程

- GLM 主 agent 负责计划、执行、调用 reviewer 和处理审核结果；不要要求用户转贴审核内容。
- 开始时阅读项目 AGENTS.md 和相关文档，把计划写入 docs/plan.md。
- 通过 Task 工具调用 reviewer 审核计划，并把计划路径、验收标准和当前阶段一并传给 reviewer。
- 计划审核通过后直接继续执行，不等待用户确认。
- 每完成一个阶段，运行该阶段要求的检查，再通过 Task 调用 reviewer 审核 diff。
- reviewer 提出阻塞问题时，GLM 自行修复并重新审核；最多修复重审 3 轮，仍未通过时再报告阻塞原因。
- 所有阶段验收和可运行的检查完成后，汇报完成内容、审核结论、检查结果，以及未能验证的项目。

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

阶段 1 完成（reviewer 第 1 轮：1 项阻塞[密钥流程]已修复——key 须作废轮换[待用户操作]、
悬空对象已 gc 清除[git fsck 确认]、已加提交前自查规则；5 条建议全部落实，测试 22 项全过）。
待 reviewer 复审确认后向用户汇总。

- 环境：.venv（Python 3.12.14），依赖锁定见 requirements.txt。
- 关键事实（Mac 上踩坑后修正）：paddleocr 3.0.3 与 paddlepaddle 3.0.0 不兼容 → 锁 paddleocr==3.7.0；
  korean+v5 组合不在 lang 映射中 → 代码显式指定 korean_PP-OCRv5_mobile_rec + PP-OCRv5_mobile_det；
  检测器只收 3 通道 → ocr.py 内部灰度转 BGR。
- 已完成：config/preprocess/ocr/translate/main、platforms(base+mac+windows)、make_samples、
  18 个单测全过、5 张样例端到端（含翻译）、--region/--debug/缺 key 降级验证。
- 已知问题：韩英混排一行被拆成两行（"힐해줘 please"），阶段 2/3 观察是否影响去重与翻译。

## Windows 验证状态

| 功能 | 状态 |
|---|---|
| Mac 端到端（--image 全链路 + 翻译） | ✅ 已验证（Mac） |
| pytest 22 项 | ✅ 已验证（Mac） |
| --region 实时截屏（Mac 实现） | ✅ 已验证（Mac） |
| platforms/windows 截图 + DPI 物理像素 | ❌ 未验证（待 docs/windows-checklist.md 第 3 项） |
| Windows 依赖安装（VC++ Redist 等） | ❌ 未验证（待清单第 1 项） |
| samples/real/ 真实截图 OCR 准确率报告 | ❌ 未验证（待用户提供截图） |
