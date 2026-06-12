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
