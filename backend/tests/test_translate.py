import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config import TranslateConfig
from translate import FAIL_PREFIX, MissingApiKeyError, Translator, _extract_json_array


def make_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def ok_handler(captured=None):
    def handler(request):
        if captured is not None:
            captured.update(json.loads(request.content))
        arr = [{"id": i, "translation": f"译{i}"} for i in range(3)]
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "```json\n"
                                      + json.dumps(arr, ensure_ascii=False) + "\n```"}}]})
    return handler


def test_missing_key_raises_before_request():
    tr = Translator(TranslateConfig(), None)
    with pytest.raises(MissingApiKeyError):
        tr.translate(["hi"])
    # 空文本列表不触发 key 检查也不发请求
    assert tr.translate([]).translations == []


def test_merged_request_body_and_parse():
    captured: dict = {}
    tr = Translator(TranslateConfig(), "fake", client=make_client(ok_handler(captured)))
    result = tr.translate(["a", "b", "c"])
    assert result.translations == ["译0", "译1", "译2"]
    body = captured
    assert body["model"] == TranslateConfig().model
    # 低延迟参数
    assert body["thinking"] == {"type": "disabled"}
    assert body["reasoning_effort"] == "low"
    # 三条文本合并进同一次请求
    user_msg = body["messages"][1]["content"]
    assert "0. a" in user_msg and "2. c" in user_msg


def test_retry_exhaustion_returns_fail_placeholder():
    calls = {"n": 0}

    def fail_handler(request):
        calls["n"] += 1
        return httpx.Response(500)

    tr = Translator(TranslateConfig(max_retries=2), "fake",
                    client=make_client(fail_handler))
    result = tr.translate(["x", "y"])
    assert calls["n"] == 3  # 1 次原始 + 2 次重试
    assert all(t.startswith(FAIL_PREFIX) for t in result.translations)
    assert len(result.translations) == 2


def test_retry_recovers_on_second_attempt():
    calls = {"n": 0}

    def flaky_handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("timeout")
        return ok_handler()(request)

    tr = Translator(TranslateConfig(max_retries=2), "fake",
                    client=make_client(flaky_handler))
    result = tr.translate(["a", "b", "c"])
    assert result.translations == ["译0", "译1", "译2"]


def test_missing_id_in_response_marked_failed():
    def partial_handler(request):
        arr = [{"id": 0, "translation": "好"}, {"id": 2, "translation": "冲"}]
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(arr, ensure_ascii=False)}}]})

    tr = Translator(TranslateConfig(), "fake", client=make_client(partial_handler))
    result = tr.translate(["a", "b", "c"])
    assert result.translations[0] == "好"
    assert result.translations[1].startswith(FAIL_PREFIX)
    assert result.translations[2] == "冲"


def test_extract_json_array_tolerates_noise():
    assert _extract_json_array('前言 [{"id":0,"translation":"x"}] 后记') == [
        {"id": 0, "translation": "x"}]
    with pytest.raises(ValueError):
        _extract_json_array("完全不是 JSON")
