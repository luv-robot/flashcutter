from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.in_title = False
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self.in_title = True
            return
        if tag.lower() != "meta":
            return
        attr_map = {name.lower(): value for name, value in attrs if value is not None}
        key = attr_map.get("property") or attr_map.get("name")
        content = attr_map.get("content")
        if key and content:
            self.meta[key.lower()] = unescape(content.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            value = data.strip()
            if value:
                self.title_parts.append(value)


def importable_metadata_for_url(url: str) -> dict:
    parsed = urlparse(url)
    source_site = parsed.netloc.replace("www.", "")
    fallback_title = fallback_title_for_url(url)
    notes: list[str] = []

    try:
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                )
            },
        )
        with urlopen(request, timeout=10) as response:
            raw = response.read(512_000)
            content_type = response.headers.get("content-type", "")
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        notes.append(f"自动抓取失败：{exc}")
        return fallback_metadata(url, source_site, fallback_title, notes)

    if "html" not in content_type.lower():
        notes.append(f"页面不是 HTML：{content_type or 'unknown content type'}")
        return fallback_metadata(url, source_site, fallback_title, notes)

    html = raw.decode("utf-8", errors="ignore")
    parser = MetadataParser()
    parser.feed(html)
    title = (
        parser.meta.get("og:title")
        or parser.meta.get("twitter:title")
        or " ".join(parser.title_parts).strip()
        or fallback_title
    )
    description = parser.meta.get("og:description") or parser.meta.get("description")
    image_url = parser.meta.get("og:image") or parser.meta.get("twitter:image")

    if "__tst_status" in html or "EO_Bot_Ssid" in html:
        notes.append("目标页面返回反爬校验脚本，未取得可用素材元信息。")
    if image_url:
        notes.append("仅记录远程预览图 URL；未下载图片文件，需确认授权后才能作为生产素材。")

    return {
        "source_url": url,
        "source_site": source_site,
        "title": title[:255],
        "description": description,
        "image_url": image_url,
        "rights_status": "reference_only",
        "component_type": infer_component_type(f"{title} {description or ''}"),
        "industry": infer_industry(f"{title} {description or ''}"),
        "style_tags": infer_style_tags(f"{title} {description or ''}"),
        "layout_json": default_layout_notes(f"{title} {description or ''}"),
        "notes": "\n".join(notes) if notes else "自动导入为版式参考。未下载图片，需权利确认后才能转为可生产组件。",
        "is_active": True,
    }


def fallback_metadata(url: str, source_site: str, title: str, notes: list[str]) -> dict:
    return {
        "source_url": url,
        "source_site": source_site,
        "title": title[:255],
        "description": None,
        "image_url": None,
        "rights_status": "reference_only",
        "component_type": "layout_reference",
        "industry": None,
        "style_tags": [],
        "layout_json": default_layout_notes(title),
        "notes": "\n".join(notes),
        "is_active": True,
    }


def fallback_title_for_url(url: str) -> str:
    parsed = urlparse(url)
    slug = parsed.path.strip("/") or parsed.netloc
    return f"{parsed.netloc} {slug}".strip()


def infer_component_type(text: str) -> str:
    lower = text.lower()
    rules = [
        ("price_tag", ["价格", "到手价", "price", "¥", "$"]),
        ("coupon_strip", ["券", "优惠", "coupon"]),
        ("product_card", ["产品", "商品", "电商", "详情", "product"]),
        ("cta_panel", ["购买", "下单", "立即", "shop", "buy"]),
        ("poster_layout", ["海报", "poster"]),
        ("headline_block", ["标题", "headline"]),
    ]
    for component_type, keywords in rules:
        if any(keyword in lower for keyword in keywords):
            return component_type
    return "layout_reference"


def infer_industry(text: str) -> str | None:
    lower = text.lower()
    rules = [
        ("beauty", ["美妆", "护肤", "口红", "香水", "beauty"]),
        ("food", ["食品", "饮料", "餐饮", "food", "drink"]),
        ("fashion", ["服饰", "鞋", "穿搭", "fashion"]),
        ("electronics", ["数码", "手机", "耳机", "家电", "electronics"]),
        ("pet", ["宠物", "猫", "狗", "pet"]),
    ]
    for industry, keywords in rules:
        if any(keyword in lower for keyword in keywords):
            return industry
    return None


def infer_style_tags(text: str) -> list[str]:
    lower = text.lower()
    tags: list[str] = []
    candidates = {
        "ecommerce": ["电商", "商品", "购买"],
        "poster": ["海报", "poster"],
        "bold": ["大字", "强", "bold"],
        "clean": ["简洁", "clean"],
        "promo": ["促销", "优惠", "券"],
        "social": ["小红书", "抖音", "ugc"],
    }
    for tag, keywords in candidates.items():
        if any(keyword in lower for keyword in keywords):
            tags.append(tag)
    return tags


def default_layout_notes(text: str) -> dict:
    return {
        "extractable_components": [
            "headline_block",
            "product_visual_area",
            "benefit_points",
            "cta_panel",
        ],
        "operator_use": "作为模板组件灵感和结构拆解，不直接作为生产素材。",
        "raw_hint": text[:300],
    }
