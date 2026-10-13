# PaddlePaddle / PaddleOCR Windows 安装注意事项

目标环境：Windows 10/11 x64，Python 3.12（64 位）。版本锁定见根目录 requirements.txt。

## 1. 安装顺序

1. 安装 Python 3.12（64 位）——安装时勾选 "Add python.exe to PATH"。
2. **先装 Microsoft Visual C++ Redistributable 2015-2022 (x64)**：
   https://aka.ms/vs/17/release/vc_redist.x64.exe
   缺它时 `import paddle` 会直接报 DLL 加载失败（0xc000007b 或 FileNotFoundError）。
3. 创建虚拟环境并安装（在项目根目录）：

   ```powershell
   py -3.12 -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

## 2. 常见坑

- **CPU 版即可**，不要装 paddlepaddle-gpu（驱动/CUDA 坑多且本工具用不到）。
- **AVX 指令集**：paddle 二进制要求 AVX。2011 年后的 CPU 基本都支持；
  老机器报 `Illegal instruction (core dumped)` 即此原因，无解，只能换机器。
- **Python 版本**：只支持 3.8~3.12 的 64 位；3.13+ 会装不上或 import 失败。
- **首次运行联网下载模型**（约 20MB，缓存到 `C:\Users\<你>\.paddlex\official_models\`）。
  离线机器可先在有网的机器上跑一次，把该目录拷过去。
- **杀毒软件**：可能拦截 Python 子进程联网下载或阻止 `.venv` 里的 exe；
  报错莫名时先把项目目录加入白名单再试。
- **pip 超时/慢**：可选镜像源（自行选择、不写入仓库配置）：

  ```powershell
  pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
  ```

## 3. 验证安装

```powershell
.venv\Scripts\python -c "import paddle, paddleocr; print(paddle.__version__, paddleocr.__version__)"
```

预期输出 `3.0.0 3.7.0`（与 requirements.txt 一致）。

## 4. 已知的版本组合问题（Mac 上已踩过）

- paddleocr **3.0.3 与 paddlepaddle 3.0.0 组合会崩**（`PaddlePredictorOption.__init__` 报错），
  已锁定 paddleocr==3.7.0 解决。Windows 上若自行升级 paddleocr，请连 paddlex 一起升级。
- 韩语模型：`korean_PP-OCRv5_mobile_rec`（识别）+ `PP-OCRv5_mobile_det`（检测），
  在代码中显式指定（paddleocr 3.7.0 的 lang 映射仍不含 korean+v5 组合）。
- 文本检测器只接受 3 通道输入，灰度图需先转 BGR（backend/ocr.py 已处理）。

## 5. DPI 与坐标（与 docs/windows-checklist.md 呼应）

- 截图前进程会调用 `SetProcessDpiAwareness(PER_MONITOR_DPI_AWARE)`（platforms/windows/mss_capture.py）。
- `--region` 传入的坐标一律是**物理像素**：125% 缩放下，屏幕上量到的逻辑坐标 × 1.25。
- 验证方法见 windows-checklist.md 第 3 项。
