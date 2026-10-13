"""阶段 1 CLI：图片/屏幕区域 → 预处理 → OCR → DeepSeek 翻译 → 终端输出。

用法示例：
  python main.py --image samples/test_korean.png
  python main.py --image samples/real/xxx.png --debug
  python main.py --region "100,200,800,300" --no-translate
  python main.py --image samples/test_korean.png --no-preprocess

区域坐标一律为物理像素（Windows 下已做 DPI aware，见 platforms/windows/）。
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# 保证 `python backend/main.py` 与 pytest 两种方式都能导入
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2

from config import AppConfig, load_config
from platforms.base import Region

logger = logging.getLogger("ow-translate")


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def save_debug_image(cfg: AppConfig, name: str, img) -> None:
    cfg.debug_dir.mkdir(parents=True, exist_ok=True)
    out = cfg.debug_dir / name
    cv2.imwrite(str(out), img)
    logger.debug("中间图已保存: %s", out)


def run_pipeline(cfg: AppConfig, bgr, args, source_desc: str) -> None:
    """对一张 BGR 图执行 预处理→OCR→翻译 并打印结果。"""
    from ocr import get_engine
    from preprocess import preprocess

    t_total = time.time()

    # ---- 预处理 ----
    pre_cfg = cfg.preprocess
    if args.no_preprocess:
        pre_cfg = type(pre_cfg)(scale=1.0, grayscale=False, contrast_boost=False,
                                adaptive_threshold=False)
    pre = preprocess(bgr, pre_cfg, debug=args.debug)
    if args.debug:
        save_debug_image(cfg, "0_input.png", bgr)
        for name, img in pre.intermediates.items():
            save_debug_image(cfg, f"{name}.png", img)

    # ---- OCR ----
    engine = get_engine(cfg.ocr)
    dropped: list = []
    lines = engine.recognize(pre.image, dropped_out=dropped)
    if args.debug and dropped:
        logger.info("被置信度阈值(%.2f)过滤的行: %s",
                    cfg.ocr.confidence_threshold,
                    [(l.text, round(l.score, 2)) for l in dropped])

    if not lines:
        print("\n未识别到任何文本（可尝试 --debug 查看中间图，或调低 --confidence）。")
        return

    # ---- 翻译（按阅读顺序：自上而下） ----
    lines.sort(key=lambda l: min(p[1] for p in l.box))
    texts = [l.text for l in lines]

    if args.no_translate:
        translations = ["(未翻译)"] * len(texts)
    else:
        from translate import MissingApiKeyError, Translator
        try:
            translator = Translator(cfg.translate, cfg.api_key)
            result = translator.translate(texts)
            translations = result.translations
            logger.info("翻译耗时 %.0fms", result.elapsed_ms)
        except MissingApiKeyError as e:
            logger.error("%s", e)
            translations = ["(未翻译——见上方错误提示)"] * len(texts)

    # ---- 输出 ----
    print(f"\n=== {source_desc} ===")
    for line, tr in zip(lines, translations):
        print(f"[{line.score:.2f}] {line.text}")
        print(f"    → {tr}")
    print(f"共 {len(lines)} 行，总耗时 {time.time() - t_total:.1f}s")


def main() -> int:
    parser = argparse.ArgumentParser(description="守望先锋聊天框 OCR+翻译（阶段 1 CLI）")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path, help="读取本地图片（Mac 开发主路径）")
    source.add_argument("--region", type=Region.parse,
                        help='截取屏幕区域，格式 "x,y,w,h"（物理像素）')
    parser.add_argument("--no-translate", action="store_true", help="只跑 OCR 不调用翻译 API")
    parser.add_argument("--no-preprocess", action="store_true", help="关闭全部预处理")
    parser.add_argument("--confidence", type=float, help="覆盖置信度阈值（默认 0.6）")
    parser.add_argument("--debug", action="store_true", help="保存中间图到 debug/ 并输出调试日志")
    parser.add_argument("-v", "--verbose", action="store_true", help="调试日志")
    args = parser.parse_args()

    setup_logging(args.verbose or args.debug)
    cfg = load_config()
    if args.confidence is not None:
        cfg.ocr.confidence_threshold = args.confidence

    if args.image is not None:
        p = Path(args.image)
        if not p.is_file():
            print(f"文件不存在: {p}", file=sys.stderr)
            return 1
        import numpy as np
        bgr = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
        if bgr is None:
            print(f"无法解码图片: {p}", file=sys.stderr)
            return 1
        # cv2.imdecode + np.fromfile 组合可正确处理含非 ASCII 字符的路径（Windows 中文用户名兼容）
        run_pipeline(cfg, bgr, args, f"图片 {p.name}")
    else:
        region: Region = args.region
        from platforms.mac.mss_capture import get_capture as get_mac
        from platforms.windows.mss_capture import get_capture as get_win
        import platform as py_platform

        cap = get_win() if py_platform.system() == "Windows" else get_mac()
        scale = cap.physical_scale()
        if scale != (1.0, 1.0):
            logger.info("当前 DPI 缩放: %.0f%%（坐标已按物理像素处理）", scale[0] * 100)
        bgr = cap.grab(region)
        run_pipeline(cfg, bgr, args, f"屏幕区域 {region}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
