"""PaddleOCR 封装。

- 懒加载单例：首次调用时才初始化模型（加载约需数秒）。
- 输出统一结构：[{text, score, box}]，box 为四点坐标（预处理后图像上的像素）。
- 置信度低于阈值的行被过滤，并记录日志便于排查识别质量问题。

PaddleOCR 3.x API：use_angle_cls 已弃用，改用三个 use_* 开关；
韩语需要 ocr_version="PP-OCRv5" + lang="korean"（v6 不支持韩语）。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import numpy as np

import cv2

from config import OcrConfig

logger = logging.getLogger(__name__)


@dataclass
class OcrLine:
    text: str
    score: float
    box: list[list[int]]  # 四点 [[x,y]...]


class OcrEngine:
    def __init__(self, cfg: OcrConfig):
        self.cfg = cfg
        self._ocr = None  # 懒加载

    def _ensure_model(self):
        if self._ocr is not None:
            return
        from paddleocr import PaddleOCR  # 延迟导入，避免不用 OCR 的测试也拉起 paddle

        logger.info("初始化 PaddleOCR: version=%s lang=%s（首次会自动下载模型）",
                    self.cfg.ocr_version, self.cfg.lang)
        t0 = time.time()
        kwargs: dict = {
            # 聊天文字无旋转/无扭曲，全部关闭以省时间；构造时关闭则模型不加载
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
            "device": "cpu",
        }
        if self.cfg.lang == "korean":
            # paddleocr 3.0.3 的 lang 映射表尚无 korean+PP-OCRv5 组合，显式指定模型：
            # 韩文识别模型同时支持韩/英/数字；检测用 v5 mobile 通用模型
            kwargs.update(
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="korean_PP-OCRv5_mobile_rec",
            )
        else:
            kwargs.update(ocr_version=self.cfg.ocr_version, lang=self.cfg.lang)
        self._ocr = PaddleOCR(**kwargs)
        logger.info("PaddleOCR 初始化完成，耗时 %.1fs", time.time() - t0)

    def recognize(self, img: np.ndarray, dropped_out: list[OcrLine] | None = None) -> list[OcrLine]:
        """对一张图（可为预处理后图像）做 OCR，返回过滤后的行。

        dropped_out：若传入列表，被置信度阈值过滤的行会附到其中（供 --debug 报告）。
        """
        self._ensure_model()
        # 文本检测器要求 3 通道输入；预处理可能输出灰度/二值图，这里统一转 BGR
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        t0 = time.time()
        results = self._ocr.predict(img)
        lines: list[OcrLine] = []
        dropped: list[OcrLine] = []
        total = 0
        for res in results:
            total += len(res["rec_texts"])
            for text, score, poly in zip(res["rec_texts"], res["rec_scores"], res["rec_polys"]):
                if not text or not text.strip():
                    continue
                line = OcrLine(text=text.strip(), score=float(score),
                               box=np.asarray(poly).tolist())
                if line.score < self.cfg.confidence_threshold:
                    dropped.append(line)
                    continue
                lines.append(line)
        if dropped_out is not None:
            dropped_out.extend(dropped)
        logger.info("OCR 完成: 保留 %d 行 / 识别 %d 行（过滤 %d）, 耗时 %.2fs",
                    len(lines), total, len(dropped), time.time() - t0)
        return lines


_engine: OcrEngine | None = None


def get_engine(cfg: OcrConfig) -> OcrEngine:
    """进程内单例；测试中可直接 new OcrEngine 而不走这里。"""
    global _engine
    if _engine is None:
        _engine = OcrEngine(cfg)
    return _engine
