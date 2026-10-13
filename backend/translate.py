"""DeepSeek 翻译（OpenAI 兼容 /chat/completions）。

设计要点：
- 多条消息合并为一次请求：prompt 要求模型返回带编号的 JSON 数组，按编号对应原文。
- 低延迟：thinking 关闭 + reasoning_effort=low（模型 ID 从配置读取）。
- 超时（默认 8s）、最多重试 2 次；失败时该条原文的译文为 "[翻译失败: 原因]"。
- API key 只从环境变量读取；缺失时在发请求前就报错，不发注定失败的请求。
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass

import httpx

from config import TranslateConfig

logger = logging.getLogger(__name__)

FAIL_PREFIX = "[翻译失败"

SYSTEM_PROMPT = (
    "你是 FPS 游戏《守望先锋》队内聊天翻译器。输入是 OCR 识别出的聊天消息（编号列表），"
    "可能是韩语或英语，夹杂游戏黑话（如韩语 궁=大招、힐=治疗，英语 ult=大招、gg 等）。"
    "要求：译文简短口语化；游戏术语和玩家惯用语按社区习惯翻译；"
    "不确定的黑话保留原文并用括号标注；OCR 造成的乱码若无法理解，译文写 [无法识别]。"
    "只输出 JSON，不要输出任何其他内容："
    '[{"id": <编号>, "translation": "<译文>"}]，编号必须与输入一一对应。'
)

# 缺少 key 时的专用异常，便于调用方与网络失败区分
class MissingApiKeyError(RuntimeError):
    pass


@dataclass
class TranslateResult:
    translations: list[str]   # 与输入 texts 一一对应
    elapsed_ms: float


def _extract_json_array(content: str) -> list[dict]:
    """从模型回复中提取 JSON 数组；容忍 markdown 代码块包裹。"""
    text = content.strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"回复中未找到 JSON 数组: {content[:120]!r}")
    arr = json.loads(text[start:end + 1])
    if not isinstance(arr, list):
        raise ValueError("JSON 不是数组")
    return arr


class Translator:
    def __init__(self, cfg: TranslateConfig, api_key: str | None,
                 client: httpx.Client | None = None):
        self.cfg = cfg
        self._api_key = api_key
        # client 可注入（测试用）；生产环境按需创建
        self._client = client or httpx.Client(timeout=cfg.timeout_seconds)

    def _request_body(self, texts: list[str]) -> dict:
        numbered = "\n".join(f'{i}. {t}' for i, t in enumerate(texts))
        body: dict = {
            "model": self.cfg.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",
                 "content": f"目标语言：{self.cfg.target_language}\n待翻译消息：\n{numbered}"},
            ],
            "stream": False,
        }
        if self.cfg.disable_thinking:
            body["thinking"] = {"type": "disabled"}
            body["reasoning_effort"] = "low"
        return body

    def _parse_response(self, data: dict, n: int) -> list[str]:
        content = data["choices"][0]["message"]["content"]
        arr = _extract_json_array(content)
        by_id: dict[int, str] = {}
        for item in arr:
            if isinstance(item, dict) and "id" in item and "translation" in item:
                try:
                    by_id[int(item["id"])] = str(item["translation"])
                except (TypeError, ValueError):
                    continue
        # 编号缺失/非法的条目按失败处理，但不影响其他条目
        return [by_id.get(i, f"{FAIL_PREFIX}: 模型未返回第 {i} 条译文]") for i in range(n)]

    def translate(self, texts: list[str]) -> TranslateResult:
        """翻译一批文本（合并为一次请求）。返回与 texts 等长的译文列表。"""
        t0 = time.time()
        if not texts:
            return TranslateResult(translations=[], elapsed_ms=0.0)
        if not self._api_key:
            # 在发请求前就失败，给出明确指引
            raise MissingApiKeyError(
                "未设置 DEEPSEEK_API_KEY 环境变量；请复制 .env.example 为 .env 并填入 key，"
                "或在 shell 中 export。可用 --no-translate 先测试 OCR 链路。"
            )

        body = self._request_body(texts)
        headers = {"Authorization": f"Bearer {self._api_key}"}
        url = f"{self.cfg.base_url.rstrip('/')}/chat/completions"

        last_err: Exception | None = None
        # 最多 max_retries 次重试 → 总共最多 1 + max_retries 次
        for attempt in range(1 + self.cfg.max_retries):
            try:
                resp = self._client.post(url, json=body, headers=headers)
                resp.raise_for_status()
                translations = self._parse_response(resp.json(), len(texts))
                return TranslateResult(translations=translations,
                                       elapsed_ms=(time.time() - t0) * 1000)
            except (httpx.HTTPError, ValueError, KeyError, IndexError) as e:
                last_err = e
                logger.warning("翻译请求失败（第 %d/%d 次尝试）: %s",
                               attempt + 1, self.cfg.max_retries + 1, e)
                if attempt < self.cfg.max_retries:
                    time.sleep(0.5 * (attempt + 1))  # 简单退避

        fail = f"{FAIL_PREFIX}: {last_err}]"
        logger.error("翻译最终失败: %s", last_err)
        return TranslateResult(translations=[fail] * len(texts),
                               elapsed_ms=(time.time() - t0) * 1000)
