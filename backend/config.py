"""配置加载。

优先级：命令行参数 > 环境变量 > 配置文件(config.json) > 内置默认值。
API key 只从环境变量 DEEPSEEK_API_KEY 读取，任何情况下不落盘、不打印。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"


@dataclass
class PreprocessConfig:
    scale: float = 2.5            # 放大倍数，2~3 倍通常对小字号聊天最有效
    grayscale: bool = True
    contrast_boost: bool = True   # CLAHE 对比度增强
    adaptive_threshold: bool = False  # 自适应二值化；对深底浅字聊天框一般不需要，默认关


@dataclass
class OcrConfig:
    confidence_threshold: float = 0.6  # 低于此值的行被过滤
    # 韩语需 PP-OCRv5（v6 不支持 korean），korean 模型同时支持韩/英/数字
    lang: str = "korean"
    ocr_version: str = "PP-OCRv5"


@dataclass
class TranslateConfig:
    # 模型 ID 从配置读取；可在 config.json 中覆盖（如 deepseek-v4-pro）
    model: str = "deepseek-flash"
    base_url: str = "https://api.deepseek.com"
    target_language: str = "简体中文"
    timeout_seconds: float = 8.0
    max_retries: int = 2
    # 低延迟：关闭思考、推理强度最低
    disable_thinking: bool = True


@dataclass
class AppConfig:
    preprocess: PreprocessConfig = field(default_factory=PreprocessConfig)
    ocr: OcrConfig = field(default_factory=OcrConfig)
    translate: TranslateConfig = field(default_factory=TranslateConfig)
    debug_dir: Path = PROJECT_ROOT / "debug"
    config_path: Path = DEFAULT_CONFIG_PATH

    @property
    def api_key(self) -> str | None:
        """只从环境变量读取，不在配置文件中存储。"""
        return os.environ.get("DEEPSEEK_API_KEY") or None


def _load_dotenv(path: Path) -> None:
    """极简 .env 加载（不引入 python-dotenv）：只处理 KEY=VALUE 行，
    不覆盖已存在的环境变量；注释与空行跳过。文件不存在时静默跳过。"""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(path: Path | None = None) -> AppConfig:
    """加载配置文件（若存在）并叠加环境变量。文件不存在时返回默认值。"""
    _load_dotenv(PROJECT_ROOT / ".env")  # 环境变量优先于 .env
    cfg = AppConfig()
    cfg.config_path = path or DEFAULT_CONFIG_PATH
    p = Path(cfg.config_path)
    if p.is_file():
        data = json.loads(p.read_text(encoding="utf-8"))
        for section in ("preprocess", "ocr", "translate"):
            if section in data and isinstance(data[section], dict):
                getattr(cfg, section).__dict__.update(
                    {k: v for k, v in data[section].items() if k in asdict(getattr(cfg, section))}
                )
    if cfg.debug_dir and not cfg.debug_dir.is_absolute():
        cfg.debug_dir = PROJECT_ROOT / cfg.debug_dir
    return cfg
