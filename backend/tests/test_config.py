import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config import load_config


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_config_json_overrides(tmp_path):
    cfg_file = write(tmp_path / "config.json",
                     '{"translate": {"model": "deepseek-v4-pro"}, "ocr": {"confidence_threshold": 0.7}}')
    cfg = load_config(cfg_file)
    assert cfg.translate.model == "deepseek-v4-pro"
    assert cfg.ocr.confidence_threshold == 0.7
    # 未覆盖的项保持默认
    assert cfg.ocr.lang == "korean"


def test_config_missing_file_returns_defaults(tmp_path):
    cfg = load_config(tmp_path / "nope.json")
    assert cfg.translate.model == "deepseek-flash"
    assert cfg.ocr.confidence_threshold == 0.6


def test_dotenv_not_overriding_env(tmp_path, monkeypatch):
    """环境变量优先于 .env；.env 的注释/空行/引号要正确处理。"""
    env_file = write(tmp_path / ".env",
                     '# comment\nDEEPSEEK_API_KEY="from-dotenv"\nOTHER=value\n\n')
    monkeypatch.setenv("DEEPSEEK_API_KEY", "from-env")
    from config import _load_dotenv
    _load_dotenv(env_file)
    assert os.environ["DEEPSEEK_API_KEY"] == "from-env"
    assert os.environ["OTHER"] == "value"


def test_dotenv_loads_when_env_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    env_file = write(tmp_path / ".env", "DEEPSEEK_API_KEY=abc123\n")
    from config import _load_dotenv
    _load_dotenv(env_file)
    assert os.environ["DEEPSEEK_API_KEY"] == "abc123"
