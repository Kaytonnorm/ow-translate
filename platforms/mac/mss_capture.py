"""macOS 截图实现——仅供开发调试，不是交付目标。

mss 在 macOS 上返回的即物理像素（Retina 下为 2x），
无需 DPI aware 调用；实现接口保持与 Windows 一致。
"""
from __future__ import annotations

import logging

import mss
import numpy as np

from ..base import Region

logger = logging.getLogger(__name__)


class MacScreenCapture:
    def grab(self, region: Region) -> np.ndarray:
        with mss.mss() as sct:
            shot = sct.grab({
                "left": region.x, "top": region.y,
                "width": region.w, "height": region.h,
            })
            # mss 输出 BGRA → 取 BGR 三通道
            arr = np.frombuffer(shot.bgra, dtype=np.uint8)
            arr = arr.reshape((shot.height, shot.width, 4))[:, :, :3]
            return arr.copy()

    def physical_scale(self) -> tuple[float, float]:
        # macOS：mss 直接返回物理像素，缩放因子不影响坐标；用主屏逻辑/物理宽比仅供参考
        with mss.mss() as sct:
            m = sct.monitors[0]
            logical = m.get("width", 0)
            return (1.0, 1.0) if not logical else (1.0, 1.0)


def get_capture() -> MacScreenCapture:
    return MacScreenCapture()
