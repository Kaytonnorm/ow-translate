"""平台抽象接口（Python 侧唯一平台接口）。

按已确认的架构决策：置顶/鼠标穿透/全局快捷键/区域框选都在 Electron 主进程实现，
Python 侧只负责「屏幕截图」。所有坐标一律为**物理像素**（虚拟屏幕坐标系），
DPI 缩放的换算在各平台实现内部完成，上层逻辑不感知缩放比例。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass
class Region:
    """物理像素矩形。x/y 为虚拟屏幕坐标（支持多显示器、负坐标）。"""
    x: int
    y: int
    w: int
    h: int

    def __str__(self) -> str:
        return f"{self.x},{self.y},{self.w},{self.h}"

    @classmethod
    def parse(cls, s: str) -> "Region":
        """解析 "x,y,w,h" 格式字符串。"""
        parts = s.split(",")
        if len(parts) != 4:
            raise ValueError(f'区域格式应为 "x,y,w,h"，收到: {s!r}')
        x, y, w, h = (int(p.strip()) for p in parts)
        if w <= 0 or h <= 0:
            raise ValueError(f"宽高必须为正数: {s!r}")
        return cls(x=x, y=y, w=w, h=h)


class ScreenCapture(Protocol):
    """屏幕截图接口。实现方负责 DPI aware 初始化与物理像素保证。"""

    def grab(self, region: Region) -> np.ndarray:
        """截取指定区域，返回 BGR numpy 数组（物理像素分辨率）。"""
        ...

    def physical_scale(self) -> tuple[float, float]:
        """主显示器 DPI 缩放因子（如 125% → (1.25, 1.25)）。仅用于诊断日志。"""
        ...
