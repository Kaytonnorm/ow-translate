import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config import PreprocessConfig
from preprocess import preprocess


def make_img(h=40, w=300):
    rng = np.random.default_rng(42)
    return rng.integers(0, 255, (h, w, 3), dtype=np.uint8)


def test_all_off_returns_original():
    cfg = PreprocessConfig(scale=1.0, grayscale=False, contrast_boost=False)
    img = make_img()
    result = preprocess(img, cfg)
    assert result.image.shape == img.shape
    assert result.intermediates == {}


def test_grayscale_output_2d():
    cfg = PreprocessConfig(scale=1.0, grayscale=True, contrast_boost=False)
    result = preprocess(make_img(), cfg, debug=True)
    assert result.image.ndim == 2
    assert "1_grayscale" in result.intermediates


def test_scale_changes_size():
    cfg = PreprocessConfig(scale=2.5, grayscale=False, contrast_boost=False)
    result = preprocess(make_img(40, 300), cfg)
    assert result.image.shape == (100, 750, 3)


def test_threshold_output_binary():
    cfg = PreprocessConfig(adaptive_threshold=True)
    result = preprocess(make_img(), cfg)
    assert result.image.ndim == 2
    # 自适应二值化后只有 0/255 两类像素值
    assert set(np.unique(result.image)) <= {0, 255}


def test_debug_intermediates_recorded():
    cfg = PreprocessConfig()  # 全开
    result = preprocess(make_img(), cfg, debug=True)
    assert list(result.intermediates) == ["1_grayscale", "2_scaled", "3_clahe"]
