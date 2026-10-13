import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config import OcrConfig
from ocr import OcrEngine, get_engine


def fake_predict_result(texts, scores, polys):
    res = MagicMock()
    res.__getitem__.side_effect = lambda k: {
        "rec_texts": texts, "rec_scores": np.array(scores), "rec_polys": polys,
    }[k]
    res.__iter__ = lambda s: iter([texts])
    return res


def patch_engine(monkeypatch, texts, scores, polys):
    """构造一个绕过真实 paddle 的 OcrEngine：_ensure_model 注入 mock。"""
    cfg = OcrConfig(confidence_threshold=0.6)
    engine = OcrEngine(cfg)
    mock_ocr = MagicMock()
    mock_ocr.predict.return_value = [fake_predict_result(texts, scores, polys)]
    engine._ocr = mock_ocr
    return engine


POLYS = [[[0, 0], [10, 0], [10, 10], [0, 10]]]


def test_filters_low_confidence():
    engine = patch_engine(None, ["안녕", "hello"], [0.95, 0.5], POLYS * 2)
    dropped = []
    lines = engine.recognize(np.zeros((10, 10, 3), dtype=np.uint8), dropped_out=dropped)
    assert [l.text for l in lines] == ["안녕"]
    assert [l.text for l in dropped] == ["hello"]


def test_skips_empty_text():
    engine = patch_engine(None, ["", "  ", "ok"], [0.9, 0.9, 0.9], POLYS * 3)
    lines = engine.recognize(np.zeros((10, 10, 3), dtype=np.uint8))
    assert [l.text for l in lines] == ["ok"]


def test_gray_input_converted_to_3ch():
    """灰度图应被转成 3 通道再送模型（检测器要求）。"""
    engine = patch_engine(None, ["x"], [0.9], POLYS)
    engine.recognize(np.zeros((10, 10), dtype=np.uint8))
    sent = engine._ocr.predict.call_args[0][0]
    assert sent.ndim == 3


def test_lazy_singleton():
    cfg = OcrConfig()
    e1 = get_engine(cfg)
    e2 = get_engine(cfg)
    assert e1 is e2
