from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.routes import router as api_router
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models import Template
from app.schemas import HealthResponse
from app.services.storage import ensure_storage_dirs
from app.services.task_queue import task_queue


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    ensure_storage_dirs()
    init_db()
    seed_builtin_template()
    task_queue.start()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.environment,
    )


def seed_builtin_template() -> None:
    with SessionLocal() as db:
        templates = [
            {
                "name": settings.default_template_name,
                "description": "Visible 9:16 hook with original text area covered and replaced.",
                "json_spec": {
                    "type": "concat",
                    "creative_goal": {
                        "title": "Text replacement hook",
                        "audience": "cold traffic",
                        "tone": "direct-response",
                        "selling_points": ["new offer copy", "visible format change"],
                    },
                    "editing": {
                        "cut_style": "fixed_interval",
                        "clip_duration_seconds": 2.0,
                        "target_duration_seconds": 6.0,
                        "max_clip_count": 3,
                        "pacing": "fast",
                        "keep_original_order": True,
                    },
                    "delivery": {
                        "aspect_ratio": "9:16",
                        "width": 1080,
                        "height": 1920,
                        "fps": 30.0,
                        "format": "mp4",
                        "fit": "cover",
                    },
                    "transformations": {
                        "brightness": 0.06,
                        "contrast": 1.22,
                        "saturation": 1.28,
                        "playback_speed": 1.12,
                        "volume": 0.9,
                        "cover_regions": [
                            {
                                "x": 70,
                                "y": 1420,
                                "width": 940,
                                "height": 260,
                                "color": "black@0.86",
                            }
                        ],
                        "text_overlays": [
                            {
                                "text": "NEW HOOK: TRY THIS TODAY",
                                "x": 92,
                                "y": 1465,
                                "font_size": 58,
                                "font_color": "white",
                                "box_color": "black@0.0",
                                "box_padding": 0,
                            }
                        ],
                    },
                    "review_notes": "Check that the old lower-third text is covered and the new hook is readable.",
                },
            },
            {
                "name": "source_original_cutdown",
                "description": "Full-frame cutdown with a visible bottom replacement banner.",
                "json_spec": {
                    "type": "concat",
                    "creative_goal": {
                        "title": "Full frame offer banner",
                        "audience": "warm traffic",
                        "selling_points": ["readable offer", "full source framing"],
                        "tone": "clear",
                    },
                    "editing": {
                        "cut_style": "fixed_interval",
                        "clip_duration_seconds": 2.5,
                        "target_duration_seconds": 7.5,
                        "max_clip_count": 3,
                        "pacing": "medium",
                        "keep_original_order": True,
                    },
                    "delivery": {
                        "aspect_ratio": "source",
                        "width": 1280,
                        "height": 720,
                        "fps": 30.0,
                        "format": "mp4",
                        "fit": "contain",
                    },
                    "transformations": {
                        "contrast": 1.18,
                        "saturation": 1.2,
                        "cover_regions": [
                            {
                                "x": 0,
                                "y": 570,
                                "width": 1280,
                                "height": 150,
                                "color": "black@0.84",
                            }
                        ],
                        "text_overlays": [
                            {
                                "text": "LIMITED TEST OFFER",
                                "x": 60,
                                "y": 606,
                                "font_size": 54,
                                "font_color": "white",
                                "box_color": "black@0.0",
                                "box_padding": 0,
                            }
                        ],
                    },
                    "review_notes": "Use when the original framing matters but old captions need replacement.",
                },
            },
            {
                "name": "vertical_fast_hook",
                "description": "Aggressive 9:16 hook with top headline and faster pacing.",
                "json_spec": {
                    "type": "concat",
                    "creative_goal": {
                        "title": "Fast headline hook",
                        "audience": "cold traffic",
                        "selling_points": ["opening visual hook", "headline overlay"],
                        "tone": "direct-response",
                    },
                    "editing": {
                        "cut_style": "fixed_interval",
                        "clip_duration_seconds": 1.8,
                        "target_duration_seconds": 5.4,
                        "max_clip_count": 3,
                        "pacing": "fast",
                        "keep_original_order": True,
                    },
                    "delivery": {
                        "aspect_ratio": "9:16",
                        "width": 1080,
                        "height": 1920,
                        "fps": 30.0,
                        "format": "mp4",
                        "fit": "cover",
                    },
                    "transformations": {
                        "brightness": 0.08,
                        "contrast": 1.3,
                        "saturation": 1.35,
                        "playback_speed": 1.18,
                        "volume": 1.0,
                        "cover_regions": [
                            {
                                "x": 48,
                                "y": 82,
                                "width": 984,
                                "height": 180,
                                "color": "black@0.72",
                            }
                        ],
                        "text_overlays": [
                            {
                                "text": "STOP SCROLLING",
                                "x": 76,
                                "y": 118,
                                "font_size": 74,
                                "font_color": "white",
                                "box_color": "black@0.0",
                                "box_padding": 0,
                            }
                        ],
                    },
                    "review_notes": "Check subject crop, headline readability, and faster hook pacing.",
                },
            },
            {
                "name": "creative_recut_vertical",
                "description": "High-contrast 9:16 variant with a bottom proof banner.",
                "json_spec": {
                    "type": "concat",
                    "creative_goal": {
                        "title": "Proof banner vertical",
                        "audience": "cold traffic",
                        "selling_points": ["human-shot proof", "visible proof banner"],
                        "tone": "direct-response",
                    },
                    "editing": {
                        "cut_style": "fixed_interval",
                        "clip_duration_seconds": 2.0,
                        "target_duration_seconds": 8.0,
                        "max_clip_count": 4,
                        "pacing": "fast",
                        "keep_original_order": True,
                    },
                    "delivery": {
                        "aspect_ratio": "9:16",
                        "width": 1080,
                        "height": 1920,
                        "fps": 30.0,
                        "format": "mp4",
                        "fit": "cover",
                    },
                    "transformations": {
                        "brightness": 0.04,
                        "contrast": 1.32,
                        "saturation": 1.38,
                        "playback_speed": 1.1,
                        "volume": 0.92,
                        "cover_regions": [
                            {
                                "x": 60,
                                "y": 1500,
                                "width": 960,
                                "height": 220,
                                "color": "black@0.78",
                            }
                        ],
                        "text_overlays": [
                            {
                                "text": "REAL FOOTAGE. NEW OFFER.",
                                "x": 88,
                                "y": 1550,
                                "font_size": 56,
                                "font_color": "white",
                                "box_color": "black@0.0",
                                "box_padding": 0,
                            }
                        ],
                    },
                    "review_notes": "Confirm the recut changes are intentional and rights-cleared.",
                },
            },
            {
                "name": "muted_visual_caption_test",
                "description": "Muted visual-first cut with a large center caption.",
                "json_spec": {
                    "type": "concat",
                    "creative_goal": {
                        "title": "Muted caption test",
                        "audience": "sound-off viewers",
                        "selling_points": ["sound-off message", "large caption"],
                        "tone": "direct",
                    },
                    "editing": {
                        "cut_style": "fixed_interval",
                        "clip_duration_seconds": 2.0,
                        "target_duration_seconds": 6.0,
                        "max_clip_count": 3,
                        "pacing": "fast",
                        "keep_original_order": True,
                    },
                    "delivery": {
                        "aspect_ratio": "9:16",
                        "width": 1080,
                        "height": 1920,
                        "fps": 30.0,
                        "format": "mp4",
                        "fit": "cover",
                    },
                    "transformations": {
                        "brightness": -0.04,
                        "contrast": 1.24,
                        "saturation": 0.85,
                        "mute_audio": True,
                        "cover_regions": [
                            {
                                "x": 80,
                                "y": 820,
                                "width": 920,
                                "height": 260,
                                "color": "black@0.68",
                            }
                        ],
                        "text_overlays": [
                            {
                                "text": "WATCH THE RESULT",
                                "x": 118,
                                "y": 890,
                                "font_size": 70,
                                "font_color": "white",
                                "box_color": "black@0.0",
                                "box_padding": 0,
                            }
                        ],
                    },
                    "review_notes": "Sound is removed; judge whether the large caption carries the message.",
                },
            },
            {
                "name": "safe_area_text_replace",
                "description": "Contain-fit vertical version that preserves source frame and replaces bottom text.",
                "json_spec": {
                    "type": "concat",
                    "creative_goal": {
                        "title": "Safe area replacement",
                        "audience": "platform adaptation",
                        "selling_points": ["no crop", "caption replacement"],
                        "tone": "clear",
                    },
                    "editing": {
                        "cut_style": "fixed_interval",
                        "clip_duration_seconds": 3.0,
                        "target_duration_seconds": 9.0,
                        "max_clip_count": 3,
                        "pacing": "medium",
                        "keep_original_order": True,
                    },
                    "delivery": {
                        "aspect_ratio": "9:16",
                        "width": 1080,
                        "height": 1920,
                        "fps": 30.0,
                        "format": "mp4",
                        "fit": "contain",
                    },
                    "transformations": {
                        "contrast": 1.16,
                        "saturation": 1.18,
                        "cover_regions": [
                            {
                                "x": 60,
                                "y": 1620,
                                "width": 960,
                                "height": 190,
                                "color": "black@0.86",
                            }
                        ],
                        "text_overlays": [
                            {
                                "text": "UPDATED CAPTION AREA",
                                "x": 92,
                                "y": 1662,
                                "font_size": 54,
                                "font_color": "white",
                                "box_color": "black@0.0",
                                "box_padding": 0,
                            }
                        ],
                    },
                    "review_notes": "Use for sources where cropping would cut off product or people.",
                },
            },
            {
                "name": "hook_cta_demo",
                "description": "Visible variant demo: intro hook card + bottom subtitle bar + outro CTA card.",
                "json_spec": {
                    "type": "concat",
                    "creative_goal": {
                        "title": "钩子卡 / 字幕条 / CTA 卡演示",
                        "audience": "广告 A/B 测试",
                        "selling_points": ["开头钩子明显", "结尾 CTA 清晰", "字幕全程可见"],
                        "tone": "direct-response",
                    },
                    "editing": {
                        "cut_style": "fixed_interval",
                        "clip_duration_seconds": 3.0,
                        "target_duration_seconds": 9.0,
                        "max_clip_count": 3,
                        "pacing": "fast",
                        "keep_original_order": True,
                    },
                    "delivery": {
                        "aspect_ratio": "9:16",
                        "width": 1080,
                        "height": 1920,
                        "fps": 30.0,
                        "format": "mp4",
                        "fit": "contain",
                        "safe_area_top": 0,
                        "safe_area_bottom": 0,
                    },
                    "intro_card": {
                        "enabled": True,
                        "text": "3 秒看懂",
                        "subtitle": "亲测 30 天 · 真实记录",
                        "duration_seconds": 1.2,
                        "background_color": "0x111111",
                        "font_color": "white",
                        "font_size": 110,
                        "subtitle_font_size": 48,
                    },
                    "subtitle_bar": {
                        "enabled": True,
                        "text": "真实记录 · 30 天亲测",
                        "position": "bottom",
                        "font_size": 56,
                        "font_color": "white",
                        "bar_color": "black@0.7",
                        "bar_height": 160,
                    },
                    "outro_card": {
                        "enabled": True,
                        "text": "点击购买",
                        "subtitle": "限时优惠 立即领取",
                        "duration_seconds": 1.4,
                        "background_color": "0xCC3333",
                        "font_color": "white",
                        "font_size": 130,
                        "subtitle_font_size": 48,
                    },
                    "transformations": {},
                    "review_notes": "Compare with other variants for hook clarity, CTA strength, and subtitle readability.",
                },
            },
        ]
        for template in templates:
            existing = db.query(Template).filter(Template.name == template["name"]).first()
            if existing is None:
                db.add(
                    Template(
                        name=template["name"],
                        description=template["description"],
                        version=1,
                        json_spec=template["json_spec"],
                        is_builtin=True,
                    )
                )
                continue
            if existing.is_builtin:
                existing.description = template["description"]
                existing.version = max(existing.version, 2)
                existing.json_spec = template["json_spec"]
        db.commit()
