from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from template_element_miner.config import MinerConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="template_element_miner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser("extract-frames", help="Extract frames from videos and normalize images.")
    extract.add_argument("--input", type=Path, default=MinerConfig().paths.input_dir)
    extract.add_argument("--output", type=Path, default=MinerConfig().paths.output_dir)
    extract.add_argument("--fps", type=float, default=MinerConfig().default_fps)

    detect = subparsers.add_parser("detect-candidates", help="Detect reusable visual element candidates.")
    detect.add_argument("--frames", type=Path, default=MinerConfig().paths.frames_dir)
    detect.add_argument("--output", type=Path, default=MinerConfig().paths.output_dir)

    cluster = subparsers.add_parser("cluster", help="Deduplicate and cluster candidates.")
    cluster.add_argument("--candidates", type=Path, default=MinerConfig().paths.output_dir / "candidates.jsonl")
    cluster.add_argument("--output", type=Path, default=MinerConfig().paths.clusters_dir)

    review = subparsers.add_parser("build-review", help="Build the static review page.")
    review.add_argument("--candidates", type=Path, default=MinerConfig().paths.output_dir / "candidates.jsonl")
    review.add_argument("--clusters", type=Path, default=MinerConfig().paths.output_dir / "clusters.json")
    review.add_argument("--output", type=Path, default=MinerConfig().paths.review_dir)

    importer = subparsers.add_parser("import-approved", help="Import approved candidate snippets into an asset library.")
    importer.add_argument("--approved", type=Path, default=MinerConfig().paths.review_dir / "approved_assets.jsonl")
    importer.add_argument("--assets", type=Path, default=MinerConfig().paths.assets_dir)

    run_all = subparsers.add_parser("run-all", help="Run extract, detect, cluster, and review generation.")
    run_all.add_argument("--input", type=Path, default=MinerConfig().paths.input_dir)
    run_all.add_argument("--output", type=Path, default=MinerConfig().paths.output_dir)
    run_all.add_argument("--assets", type=Path, default=MinerConfig().paths.assets_dir)
    run_all.add_argument("--fps", type=float, default=MinerConfig().default_fps)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "extract-frames":
        from template_element_miner.frame_extractor import extract_frames

        records = extract_frames(args.input, args.output, args.fps)
        print(f"Extracted {len(records)} frames into {args.output / 'frames'}")
        return 0

    if args.command == "detect-candidates":
        from template_element_miner.candidate_detector import detect_candidates

        records = detect_candidates(args.frames, args.output)
        print(f"Detected {len(records)} candidates into {args.output / 'candidates'}")
        return 0

    if args.command == "cluster":
        from template_element_miner.cluster import cluster_candidates

        records = cluster_candidates(args.candidates, args.output)
        print(f"Built {len(records)} clusters into {args.output}")
        return 0

    if args.command == "build-review":
        from template_element_miner.review_builder import build_review_page

        index_path = build_review_page(args.candidates, args.clusters, args.output)
        print(f"Review page written to {index_path}")
        return 0

    if args.command == "import-approved":
        from template_element_miner.asset_importer import import_approved_assets

        created = import_approved_assets(args.approved, args.assets)
        print(f"Imported {len(created)} approved assets into {args.assets}")
        return 0

    if args.command == "run-all":
        from template_element_miner.candidate_detector import detect_candidates
        from template_element_miner.cluster import cluster_candidates
        from template_element_miner.frame_extractor import extract_frames
        from template_element_miner.review_builder import build_review_page

        extract_frames(args.input, args.output, args.fps)
        detect_candidates(args.output / "frames", args.output)
        cluster_candidates(args.output / "candidates.jsonl", args.output / "clusters")
        index_path = build_review_page(
            args.output / "candidates.jsonl",
            args.output / "clusters.json",
            args.output / "review",
        )
        print(f"Pipeline complete. Review page: {index_path}")
        print(f"After review, run import-approved --approved {args.output / 'review' / 'approved_assets.jsonl'} --assets {args.assets}")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
