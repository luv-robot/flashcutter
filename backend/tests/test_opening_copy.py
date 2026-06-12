from app.config import Settings
from app.schemas import StrongOpeningCopyRequest
from app.services import opening_copy


def test_openai_compatible_suggestions_parse_and_filter(monkeypatch) -> None:
    def fake_request_chat_completion(**kwargs) -> str:
        assert kwargs["base_url"] == "https://copy.example/v1"
        assert kwargs["api_key"] == "sk-test"
        assert kwargs["model"] == "copy-model"
        return """
        {
          "suggestions": [
            {"text": "先看结果：转化更清楚", "angle": "result_first", "risk_level": "low"},
            {"text": "免费领取这个方案", "angle": "pain_first", "risk_level": "manual_review"},
            {"text": "别急着划走，重点在前三秒", "angle": "curiosity", "risk_level": "medium"}
          ]
        }
        """

    monkeypatch.setattr(
        opening_copy, "request_chat_completion", fake_request_chat_completion
    )
    settings = Settings(
        copy_ai_provider="openai_compatible",
        copy_ai_base_url="https://copy.example/v1",
        copy_ai_api_key="sk-test",
        copy_ai_model="copy-model",
    )
    payload = StrongOpeningCopyRequest(
        target_count=2,
        product_name="FlashCutter",
        selling_points=["前三秒更清楚"],
        forbidden_terms=["免费"],
    )

    suggestions, warnings = opening_copy.opening_copy_suggestions(
        payload,
        settings=settings,
        asset_filename="seed-video.mp4",
    )

    assert [suggestion.source for suggestion in suggestions] == [
        "openai_compatible",
        "openai_compatible",
    ]
    assert [suggestion.text for suggestion in suggestions] == [
        "先看结果：转化更清楚",
        "别急着划走，重点在前三秒",
    ]
    assert suggestions[1].risk_level == "medium"
    assert "部分建议因包含禁用词已自动过滤。" in warnings


def test_openai_compatible_missing_key_falls_back_to_rule_based() -> None:
    settings = Settings(
        copy_ai_provider="openai_compatible",
        copy_ai_base_url="https://copy.example/v1",
        copy_ai_model="copy-model",
    )
    payload = StrongOpeningCopyRequest(
        target_count=1,
        product_name="FlashCutter",
        selling_points=["低成本批量扩量"],
    )

    suggestions, warnings = opening_copy.opening_copy_suggestions(
        payload,
        settings=settings,
        asset_filename="seed-video.mp4",
    )

    assert suggestions
    assert suggestions[0].source == "rule_based_fallback"
    assert "未配置 FLASHCUTTER_COPY_AI_API_KEY" in warnings[0]


def test_request_chat_completion_enables_json_mode_for_deepseek(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": '{"suggestions":[]}'}}]}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)

    content = opening_copy.request_chat_completion(
        base_url="https://api.deepseek.com",
        api_key="sk-test",
        model="deepseek-v4-flash",
        timeout_seconds=5,
        messages=[{"role": "user", "content": "Return JSON only."}],
        temperature=0.2,
    )

    assert content == '{"suggestions":[]}'
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert captured["json"]["thinking"] == {"type": "disabled"}
