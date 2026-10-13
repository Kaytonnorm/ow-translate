"""图像预处理：放大、灰度、对比度增强（CLAHE）、自适应二值化。

所有开关由 PreprocessConfig 控制，任何一项都可以单独关闭。
--debug 时调用方可通过 PreprocessResult.intermediates 拿到每一步中间图。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from config import PreprocessConfig


@dataclass
class PreprocessResult:
    image: np.ndarray                      # 最终送 OCR 的图像
    intermediates: dict[str, np.ndarray] = field(default_factory=dict)


def preprocess(img: np.ndarray, cfg: PreprocessConfig, debug: bool = False) -> PreprocessResult:
    """按配置依次执行预处理。输入输出均为 numpy 数组（BGR 或灰度）。"""
    steps: dict[str, np.ndarray] = {}
    out = img

    if cfg.grayscale:
        out = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
        if debug:
            steps["1_grayscale"] = out.copy()

    if cfg.scale and cfg.scale != 1.0:
        # INTER_CUBIC 对放大后的小文字边缘更友好
        h, w = out.shape[:2]
        out = cv2.resize(out, (int(w * cfg.scale), int(h * cfg.scale)), interpolation=cv2.INTER_CUBIC)
        if debug:
            steps["2_scaled"] = out.copy()

    if cfg.contrast_boost:
        # CLAHE：局部自适应对比度，适合聊天框半透明底
        if out.ndim == 3:
            lab = cv2.cvtColor(out, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            out = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
        else:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            out = clahe.apply(out)
        if debug:
            steps["3_clahe"] = out.copy()

    if cfg.adaptive_threshold:
        if out.ndim == 3:
            out = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
        # BLOCK_SIZE 必须为奇数
        out = cv2.adaptiveThreshold(
            out, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
        )
        if debug:
            steps["4_threshold"] = out.copy()

    return PreprocessResult(image=out, intermediates=steps)
