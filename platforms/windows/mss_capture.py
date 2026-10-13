"""Windows 截图实现（正式交付目标）。

**未在 Windows 实机验证**（开发机为 macOS），须按 docs/windows-checklist.md 阶段 1 清单
逐项验证后方可视为可用。代码要点：

1. DPI：必须在任何截图前调用 SetProcessDpiAwareness(PER_MONITOR_DPI_AWARE)，
   否则 125%/150% 缩放下系统会对坐标做虚拟化，截图区域错位。
2. 坐标：mss 使用虚拟屏幕坐标（支持多显示器、负坐标），DPI aware 后即为物理像素。
3. 不读取任何游戏进程内存，仅 GDI 屏幕拷贝，无反作弊风险。
"""
from __future__ import annotations

import ctypes
import logging
import sys

import numpy as np

from ..base import Region

logger = logging.getLogger(__name__)

_dpi_done = False


def _ensure_dpi_aware() -> None:
    """进程级 DPI aware；必须在首次 mss.grab 之前调用（幂等）。"""
    global _dpi_done
    if _dpi_done:
        return
    if sys.platform != "win32":
        _dpi_done = True
        return
    try:
        # Win 8.1+：shcore.SetProcessDpiAwareness(2) = PER_MONITOR_DPI_AWARE
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        logger.info("DPI aware: SetProcessDpiAwareness(PER_MONITOR_DPI_AWARE)")
    except (AttributeError, OSError):
        # Win 7/8 及 shcore 缺失时的降级
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            logger.info("DPI aware: SetProcessDPIAware(系统级降级)")
        except (AttributeError, OSError) as e:
            logger.warning("设置 DPI aware 失败，缩放屏上坐标可能偏移: %s", e)
    _dpi_done = True


class WindowsScreenCapture:
    def __init__(self):
        _ensure_dpi_aware()

    def grab(self, region: Region) -> np.ndarray:
        import mss  # 延迟导入，Mac 上跑测试/CLI 时不需要

        _ensure_dpi_aware()
        with mss.mss() as sct:
            shot = sct.grab({
                "left": region.x, "top": region.y,
                "width": region.w, "height": region.h,
            })
            arr = np.frombuffer(shot.bgra, dtype=np.uint8)
            arr = arr.reshape((shot.height, shot.width, 4))[:, :, :3]
            actual = (shot.width, shot.height)
        if actual != (region.w, region.h):
            # 实际抓到的分辨率与请求不符 → 多半是 DPI 虚拟化未生效或区域越界，记日志便于排查
            logger.warning(
                "截图尺寸与请求不符: 请求 %dx%d, 实际 %dx%d——"
                "请检查 DPI 缩放设置与区域坐标（清单: DPI 缩放验证项）",
                region.w, region.h, *actual,
            )
        return arr.copy()

    def physical_scale(self) -> tuple[float, float]:
        """主显示器缩放因子，如 150% → (1.5, 1.5)。用于诊断日志，不参与坐标计算。"""
        if sys.platform != "win32":
            return (1.0, 1.0)
        try:
            dpi = ctypes.windll.user32.GetDpiForSystem()  # Win 10 1607+
        except AttributeError:
            dc = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, 88)  # LOGPIXELSX
            ctypes.windll.user32.ReleaseDC(0, dc)
        factor = dpi / 96.0
        return (factor, factor)


def get_capture() -> WindowsScreenCapture:
    return WindowsScreenCapture()
