import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from platforms.base import Region


def test_region_parse():
    r = Region.parse("100, 200, 800, 300")
    assert (r.x, r.y, r.w, r.h) == (100, 200, 800, 300)


def test_region_parse_rejects_bad_input():
    for bad in ["100,200,800", "a,b,c,d", "100,200,-5,300", ""]:
        with pytest.raises(ValueError):
            Region.parse(bad)


def test_region_str_roundtrip():
    r = Region(10, 20, 30, 40)
    assert Region.parse(str(r)) == r
