from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Optional
import json
import os

from template_element_miner.config import ASSET_CATEGORIES
from template_element_miner.schemas import read_jsonl, write_json


def build_review_page(candidates_path: Path, clusters_path: Path, output_dir: Path) -> Path:
    candidates_path = Path(candidates_path)
    clusters_path = Path(clusters_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = read_jsonl(candidates_path)
    clusters = json.loads(clusters_path.read_text(encoding="utf-8")) if clusters_path.exists() else []
    cluster_by_id = {cluster["cluster_id"]: cluster for cluster in clusters}
    manifest = {
        "candidate_count": len(candidates),
        "cluster_count": len(clusters),
        "categories": ASSET_CATEGORIES,
        "candidates_path": str(candidates_path),
        "clusters_path": str(clusters_path),
    }
    write_json(output_dir / "review_manifest.json", manifest)
    approved_path = output_dir / "approved_assets.jsonl"
    if not approved_path.exists():
        approved_path.write_text("", encoding="utf-8")
    _write_example_approval(output_dir / "approved_assets.example.jsonl", candidates[:1])

    html = _render_html(candidates, cluster_by_id, output_dir)
    index_path = output_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path


def _write_example_approval(path: Path, candidates: list[dict[str, Any]]) -> None:
    if not candidates:
        path.write_text("", encoding="utf-8")
        return
    snippet = _approval_snippet(candidates[0], "unknown")
    path.write_text(json.dumps(snippet, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _render_html(candidates: list[dict[str, Any]], cluster_by_id: dict[str, Any], output_dir: Path) -> str:
    category_options = "".join(f"<option value='{escape(category)}'>{escape(category)}</option>" for category in ASSET_CATEGORIES)
    cards = "\n".join(_render_card(candidate, cluster_by_id, output_dir, category_options) for candidate in candidates)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Template Element Miner Review</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f6f8; color: #172033; }}
    header {{ position: sticky; top: 0; z-index: 1; padding: 16px 24px; background: #ffffff; border-bottom: 1px solid #d8deea; }}
    h1 {{ margin: 0 0 4px; font-size: 22px; }}
    .hint {{ color: #61708a; font-size: 13px; }}
    main {{ padding: 20px; display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }}
    article {{ background: #ffffff; border: 1px solid #dce2ee; border-radius: 8px; overflow: hidden; }}
    .media {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: #dce2ee; }}
    .media img {{ width: 100%; height: 190px; object-fit: contain; background: #f9fafc; display: block; }}
    .body {{ padding: 14px; }}
    .meta {{ display: grid; grid-template-columns: 110px 1fr; gap: 6px 10px; font-size: 13px; }}
    .meta span:nth-child(odd) {{ color: #66748d; }}
    textarea {{ box-sizing: border-box; width: 100%; min-height: 150px; margin-top: 10px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }}
    select, button {{ height: 32px; margin-top: 10px; }}
    a {{ color: #2457d6; }}
  </style>
</head>
<body>
  <header>
    <h1>Template Element Miner Review</h1>
    <div class="hint">Pick a category, copy useful JSON snippets into approved_assets.jsonl, then run import-approved.</div>
  </header>
  <main>
    {cards}
  </main>
  <script>
    function refreshSnippet(id) {{
      const select = document.querySelector(`[data-category-for="${{id}}"]`);
      const textarea = document.querySelector(`[data-snippet-for="${{id}}"]`);
      const payload = JSON.parse(textarea.dataset.base);
      payload.asset_type = select.value;
      textarea.value = JSON.stringify(payload);
    }}
    document.querySelectorAll("[data-category-for]").forEach((select) => {{
      select.addEventListener("change", () => refreshSnippet(select.dataset.categoryFor));
    }});
  </script>
</body>
</html>
"""


def _render_card(
    candidate: dict[str, Any],
    cluster_by_id: dict[str, Any],
    output_dir: Path,
    category_options: str,
) -> str:
    candidate_id = str(candidate["candidate_id"])
    cluster_id = str(candidate.get("cluster_id") or "")
    cluster = cluster_by_id.get(cluster_id)
    contact_sheet = cluster.get("contact_sheet_path") if cluster else ""
    snippet = _approval_snippet(candidate, "unknown")
    snippet_json = json.dumps(snippet, ensure_ascii=False, sort_keys=True)
    crop_src = _relative_url(candidate.get("crop_path", ""), output_dir)
    debug_src = _relative_url(candidate.get("debug_path", ""), output_dir)
    contact_href = _relative_url(contact_sheet, output_dir) if contact_sheet else ""
    contact_link = f"<a href='{escape(contact_href)}'>contact sheet</a>" if contact_href else ""
    return f"""<article>
  <div class="media">
    <img src="{escape(crop_src)}" alt="{escape(candidate_id)} crop">
    <img src="{escape(debug_src)}" alt="{escape(candidate_id)} source bbox">
  </div>
  <div class="body">
    <div class="meta">
      <span>ID</span><strong>{escape(candidate_id)}</strong>
      <span>Detector</span><span>{escape(str(candidate.get("detector", "")))}</span>
      <span>Score</span><span>{escape(str(candidate.get("score", "")))}</span>
      <span>Type hint</span><span>{escape(str(candidate.get("type_hint", "")))}</span>
      <span>Cluster</span><span>{escape(cluster_id)} {contact_link}</span>
      <span>Source</span><span>{escape(str(candidate.get("source_file", "")))}</span>
    </div>
    <select data-category-for="{escape(candidate_id)}">{category_options}</select>
    <textarea data-snippet-for="{escape(candidate_id)}" data-base="{escape(snippet_json)}">{escape(snippet_json)}</textarea>
  </div>
</article>"""


def _approval_snippet(candidate: dict[str, Any], asset_type: str) -> dict[str, Any]:
    return {
        "approved": True,
        "asset_type": asset_type,
        "subtype": "unknown",
        "license_status": "needs_review",
        **candidate,
    }


def _relative_url(path_value: Optional[str], output_dir: Path) -> str:
    if not path_value:
        return ""
    path = Path(path_value)
    try:
        return os.path.relpath(path, output_dir)
    except ValueError:
        return str(path)
