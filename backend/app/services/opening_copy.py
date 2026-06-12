from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, List, Optional

from app.config import Settings
from app.schemas import OpeningCopySuggestion, StrongOpeningCopyRequest


DEFAULT_MAX_COPY_LENGTH = 36
OPENAI_COMPATIBLE_PROVIDERS = {"openai", "openai_compatible"}
ALLOWED_MODEL_ANGLES = {
    "result_first",
    "pain_first",
    "proof_demo",
    "curiosity",
    "product_focus",
    "pattern_break",
    "custom",
}
ALLOWED_RISK_LEVELS = {"low", "medium", "manual_review"}


def opening_copy_suggestions(
    payload: StrongOpeningCopyRequest,
    *,
    settings: Settings,
    asset_filename: Optional[str] = None,
) -> tuple[List[OpeningCopySuggestion], List[str]]:
    warnings: List[str] = []
    provider = settings.copy_ai_provider or "rule_based"
    candidates: List[dict] = []
    if provider == "rule_based":
        candidates = rule_based_candidates(payload, asset_filename=asset_filename)
    elif provider in OPENAI_COMPATIBLE_PROVIDERS:
        model_candidates, model_warnings = openai_compatible_candidates(
            payload,
            settings=settings,
            asset_filename=asset_filename,
            provider=provider,
        )
        warnings.extend(model_warnings)
        candidates.extend(model_candidates)
        if len(candidates) < payload.target_count:
            warnings.append("在线模型建议不足，已用本地规则版文案补齐。")
            candidates.extend(
                {
                    **candidate,
                    "source": "rule_based_fallback",
                }
                for candidate in rule_based_candidates(
                    payload, asset_filename=asset_filename
                )
            )
    else:
        warnings.append(
            f"不支持的 FLASHCUTTER_COPY_AI_PROVIDER={provider}，已使用本地规则版文案建议。"
        )
        candidates = [
            {
                **candidate,
                "source": "rule_based_fallback",
            }
            for candidate in rule_based_candidates(payload, asset_filename=asset_filename)
        ]

    forbidden_terms = normalize_terms(payload.forbidden_terms)
    filtered = [
        candidate
        for candidate in candidates
        if not contains_forbidden_term(candidate["text"], forbidden_terms)
    ]
    if forbidden_terms and len(filtered) < len(candidates):
        warnings.append("部分建议因包含禁用词已自动过滤。")

    suggestions: List[OpeningCopySuggestion] = []
    seen: set[str] = set()
    for candidate in filtered:
        text = trim_copy(candidate["text"], DEFAULT_MAX_COPY_LENGTH)
        if not text or text in seen:
            continue
        seen.add(text)
        suggestions.append(
            OpeningCopySuggestion(
                id=suggestion_id(text),
                text=text,
                angle=candidate["angle"],
                source=candidate.get("source") or "rule_based",
                risk_level=candidate.get("risk_level", "low"),
                length_level="short" if len(text) <= 18 else "medium",
            )
        )
        if len(suggestions) >= payload.target_count:
            break

    if len(suggestions) < payload.target_count:
        warnings.append(
            f"只生成了 {len(suggestions)} 条可用开场文字；可补充更多卖点或放宽禁用词。"
        )
    return suggestions, warnings


def openai_compatible_candidates(
    payload: StrongOpeningCopyRequest,
    *,
    settings: Settings,
    asset_filename: Optional[str],
    provider: str,
) -> tuple[List[dict], List[str]]:
    warnings: List[str] = []
    if not settings.copy_ai_api_key:
        return [], ["未配置 FLASHCUTTER_COPY_AI_API_KEY，已使用本地规则版文案建议。"]
    if not settings.copy_ai_model:
        return [], ["未配置 FLASHCUTTER_COPY_AI_MODEL，已使用本地规则版文案建议。"]
    base_url = settings.copy_ai_base_url
    if not base_url and provider == "openai":
        base_url = "https://api.openai.com/v1"
    if not base_url:
        return [], ["未配置 FLASHCUTTER_COPY_AI_BASE_URL，已使用本地规则版文案建议。"]

    try:
        raw_content = request_chat_completion(
            base_url=base_url,
            api_key=settings.copy_ai_api_key,
            model=settings.copy_ai_model,
            timeout_seconds=settings.copy_ai_timeout_seconds,
            messages=build_copy_model_messages(payload, asset_filename=asset_filename),
            temperature=0.85 if payload.intensity == "aggressive" else 0.68,
        )
        candidates = parse_model_candidates(raw_content, source=provider)
    except Exception as exc:  # pragma: no cover - exact client errors vary by provider.
        return [], [f"在线文案模型调用失败：{exc}；已使用本地规则版文案建议。"]

    if not candidates:
        warnings.append("在线模型没有返回可用开场文字，已使用本地规则版文案建议。")
    return candidates, warnings


def request_chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout_seconds: float,
    messages: List[dict],
    temperature: float,
) -> str:
    import httpx

    request_body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 1400,
        "response_format": {"type": "json_object"},
    }
    if "deepseek." in base_url.lower() or "deepseek.com" in base_url.lower():
        request_body["thinking"] = {"type": "disabled"}

    response = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=request_body,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("model response has no choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("model response has no text content")
    return content


def build_copy_model_messages(
    payload: StrongOpeningCopyRequest, *, asset_filename: Optional[str]
) -> List[dict]:
    language_note = "Chinese, concise ad-operator wording" if payload.language != "en" else "English, concise ad-operator wording"
    requested_count = min(max(payload.target_count + 8, payload.target_count), 120)
    context = {
        "task": "Generate strong opening text overlays for the first 3 seconds of a short-video ad.",
        "language": language_note,
        "count": requested_count,
        "max_text_length": DEFAULT_MAX_COPY_LENGTH,
        "intensity": payload.intensity,
        "product_name": normalize_text(payload.product_name),
        "selling_points": normalize_terms(payload.selling_points),
        "audience": normalize_text(payload.audience),
        "forbidden_terms": normalize_terms(payload.forbidden_terms),
        "operator_notes": normalize_text(payload.user_notes),
        "source_asset_filename": asset_filename or "",
        "allowed_angles": sorted(ALLOWED_MODEL_ANGLES),
        "risk_levels": sorted(ALLOWED_RISK_LEVELS),
    }
    return [
        {
            "role": "system",
            "content": (
                "You write short, rights-safe opening copy for real human-shot short-video ads. "
                "Do not claim guaranteed results, do not invent facts, and do not mention bypassing platform detection. "
                "Return JSON only. The schema is: "
                '{"suggestions":[{"text":"...", "angle":"result_first|pain_first|proof_demo|curiosity|product_focus|pattern_break|custom", "risk_level":"low|medium|manual_review"}]}.'
            ),
        },
        {
            "role": "user",
            "content": json.dumps(context, ensure_ascii=False),
        },
    ]


def parse_model_candidates(content: str, *, source: str) -> List[dict]:
    parsed = parse_json_payload(content)
    raw_items: Any
    if isinstance(parsed, dict):
        raw_items = parsed.get("suggestions", [])
    else:
        raw_items = parsed
    if not isinstance(raw_items, list):
        return []

    candidates: List[dict] = []
    for item in raw_items:
        if isinstance(item, str):
            text = item
            angle = "custom"
            risk_level = "manual_review"
        elif isinstance(item, dict):
            text = str(item.get("text") or "")
            angle = normalize_model_choice(item.get("angle"), ALLOWED_MODEL_ANGLES, "custom")
            risk_level = normalize_model_choice(
                item.get("risk_level"), ALLOWED_RISK_LEVELS, "manual_review"
            )
        else:
            continue
        text = trim_copy(text, DEFAULT_MAX_COPY_LENGTH)
        if not text:
            continue
        candidates.append(
            {
                "text": text,
                "angle": angle,
                "risk_level": risk_level,
                "source": source,
            }
        )
    return candidates


def parse_json_payload(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        stripped = content.strip()
        object_start = stripped.find("{")
        object_end = stripped.rfind("}")
        if object_start != -1 and object_end > object_start:
            return json.loads(stripped[object_start : object_end + 1])
        array_start = stripped.find("[")
        array_end = stripped.rfind("]")
        if array_start != -1 and array_end > array_start:
            return json.loads(stripped[array_start : array_end + 1])
        raise


def normalize_model_choice(value: Any, allowed: set[str], fallback: str) -> str:
    normalized = normalize_text(str(value or "")).lower()
    return normalized if normalized in allowed else fallback


def rule_based_candidates(
    payload: StrongOpeningCopyRequest, *, asset_filename: Optional[str]
) -> List[dict]:
    language = payload.language
    product = normalized_product(payload.product_name, language)
    points = normalize_terms(payload.selling_points) or default_points(language)
    audience = normalize_text(payload.audience)
    asset_hint = filename_hint(asset_filename)

    angle_order = angles_for_intensity(payload.intensity)
    candidates: List[dict] = []
    for point_index, point in enumerate(points):
        for angle in angle_order:
            candidates.extend(
                templates_for_angle(
                    angle=angle,
                    product=product,
                    point=point,
                    audience=audience,
                    asset_hint=asset_hint,
                    language=language,
                    point_index=point_index,
                    intensity=payload.intensity,
                )
            )
    return candidates


def templates_for_angle(
    *,
    angle: str,
    product: str,
    point: str,
    audience: str,
    asset_hint: str,
    language: str,
    point_index: int,
    intensity: str,
) -> List[dict]:
    risk = "medium" if intensity == "aggressive" else "low"
    if language == "en":
        templates = {
            "result_first": [
                f"Watch {product} solve {point}",
                f"The {point} moment comes first",
            ],
            "pain_first": [
                f"Still stuck on {point}?",
                f"This is where {point} changes",
            ],
            "proof_demo": [
                f"Real demo: {point}",
                f"See {point} in action",
            ],
            "curiosity": [
                f"Do not skip this {product} detail",
                f"The key detail is in 3 seconds",
            ],
            "product_focus": [
                f"Start with {product}",
                f"{product}: show the useful part first",
            ],
            "pattern_break": [
                f"Stop showing {asset_hint or product} too late",
                f"Move the hook before the explanation",
            ],
        }
    else:
        templates = {
            "result_first": [
                f"先看结果：{point}",
                f"{product}的差别，前3秒看清",
                f"别先讲功能，先看{point}",
            ],
            "pain_first": [
                f"还在被{point}卡住？",
                f"问题不是不会用，是没看到这里",
                f"这个痛点，先用画面说清楚",
            ],
            "proof_demo": [
                f"{point}，直接看演示",
                f"这不是介绍，是实拍证明",
                f"先给证据，再讲{product}",
            ],
            "curiosity": [
                f"别急着划走，关键在这里",
                f"这3秒决定你要不要继续看",
                f"很多人忽略了这个细节",
            ],
            "product_focus": [
                f"{product}先露出，卖点才清楚",
                f"先看到{product}，再看怎么用",
                f"{product}的重点动作在这里",
            ],
            "pattern_break": [
                f"别把重点放到最后",
                f"开头太慢？先把{point}放前面",
                f"先别解释，直接上画面",
            ],
        }
    selected = templates.get(angle, [])
    return [
        {
            "text": text,
            "angle": angle,
            "risk_level": risk if angle == "pattern_break" else "low",
        }
        for text in rotate(selected, point_index)
    ]


def angles_for_intensity(intensity: str) -> List[str]:
    if intensity == "conservative":
        return ["result_first", "proof_demo", "product_focus", "curiosity"]
    if intensity == "aggressive":
        return [
            "result_first",
            "pattern_break",
            "pain_first",
            "curiosity",
            "proof_demo",
            "product_focus",
        ]
    return [
        "result_first",
        "pain_first",
        "proof_demo",
        "curiosity",
        "product_focus",
    ]


def default_points(language: str) -> List[str]:
    if language == "en":
        return ["the useful part", "the real result", "the first step"]
    return ["核心卖点", "使用效果", "关键步骤", "产品细节"]


def normalized_product(value: Optional[str], language: str) -> str:
    text = normalize_text(value)
    if text:
        return text
    return "this product" if language == "en" else "这个产品"


def normalize_terms(values: Iterable[str]) -> List[str]:
    return [term for term in (normalize_text(value) for value in values) if term]


def normalize_text(value: Optional[str]) -> str:
    return " ".join(str(value or "").strip().split())


def filename_hint(asset_filename: Optional[str]) -> str:
    if not asset_filename:
        return ""
    return normalize_text(asset_filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " "))


def contains_forbidden_term(text: str, forbidden_terms: List[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in forbidden_terms)


def trim_copy(text: str, max_length: int) -> str:
    compact = normalize_text(text)
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 1].rstrip("，,。.!！?？ ") + "…"


def suggestion_id(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def rotate(values: List[str], offset: int) -> List[str]:
    if not values:
        return []
    amount = offset % len(values)
    return [*values[amount:], *values[:amount]]
