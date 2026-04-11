"""
Ingester CLI entry point.

Usage:
    python3 -m ingester.main inventory --program fksp
    python3 -m ingester.main inventory --program fksp --output /path/to/report.json
    python3 -m ingester.main inventory --all

Session 1 only implements `inventory`. Later sessions add `pilot`, `ingest`,
`status`, and `verify` subcommands per the master build plan.

The inventory subcommand:
  1. Walks the specified program's Drive folder tree
  2. Classifies every file by ingestion pipeline
  3. Aggregates counts and total bytes per pipeline type
  4. Estimates LLM costs for a full ingestion run
  5. Writes a JSON report AND prints a human-readable summary

It does NOT download any file content. It only reads Drive metadata.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import config
from .drive_client import DriveClient, DriveFile

# ---------------------------------------------------------------------------
# Cost model
#
# These are order-of-magnitude estimates. They are used ONLY for presenting
# a budget to Daniel before any real ingestion run. Verify against current
# provider pricing in the Google Cloud console / OpenAI dashboard / Anthropic
# console before kicking off a full program.
#
# All costs are in USD.
# ---------------------------------------------------------------------------

# Gemini 2.5 Flash (vision enrichment)
#   Per slide keyframe or PDF page:
#     ~250 input tokens for the image + ~200 prompt tokens + ~400 output tokens
#   At ~$0.075 / 1M input, ~$0.30 / 1M output:
#     input:  450 * 0.075 / 1e6 = $0.0000338
#     output: 400 * 0.30  / 1e6 = $0.00012
#   Total: ~$0.00015 per visual asset
COST_PER_VISION_CALL = 0.00015

# OpenAI text-embedding-3-large
#   ~400 tokens per chunk, $0.13 / 1M tokens
#   Total: ~$0.000052 per chunk
COST_PER_EMBEDDING = 0.000052

# Claude Haiku context-aware chunk wrapping
#   ~500 in + 200 out per chunk
#   Using Haiku 4.5 pricing (~$0.80 input / $4 output per 1M at time of writing)
#     input:  500 * 0.80 / 1e6 = $0.0004
#     output: 200 * 4.00 / 1e6 = $0.0008
#   Total: ~$0.0012 per chunk
COST_PER_HAIKU_CHUNK_WRAP = 0.0012

# Rough assumptions for converting asset counts into chunk counts
AVG_SLIDES_PER_VIDEO = 40
AVG_PAGES_PER_PDF = 10
AVG_CHUNKS_PER_IMAGE = 1


# ---------------------------------------------------------------------------
# Inventory aggregation
# ---------------------------------------------------------------------------

def _bucket() -> dict:
    """An empty aggregation bucket for one pipeline category."""
    return {"count": 0, "total_bytes": 0, "files": []}


def aggregate(files: list[DriveFile]) -> dict:
    """
    Group a list of DriveFile records by pipeline and compute totals.

    Returns a dict shaped like:
      {
        "video":        {"count": N, "total_bytes": N, "files": [...]},
        "pdf":          {"count": N, "total_bytes": N, "files": [...]},
        "image":        {...},
        "google_doc":   {...},
        "google_slides":{...},
        "skip":         {...},
        "folder":       {"count": N, "total_bytes": 0, "files": []},
      }
    """
    buckets: dict[str, dict] = {}
    for f in files:
        b = buckets.setdefault(f.pipeline, _bucket())
        b["count"] += 1
        if f.size:
            b["total_bytes"] += f.size
        # Keep the full record for the JSON report, but strip `parents`
        # since it's noisy and not needed downstream
        rec = f.to_dict()
        rec.pop("parents", None)
        b["files"].append(rec)
    # Ensure all expected keys exist even with zero count
    for key in ("video", "pdf", "image", "google_doc", "google_slides", "skip", "folder"):
        buckets.setdefault(key, _bucket())
    return buckets


def estimate_cost(buckets: dict) -> dict:
    """
    Estimate LLM costs for ingesting the inventory.

    This is deliberately conservative-ish: videos assume 40 slides each, PDFs
    assume 10 pages each. The real numbers will be known after the pilot.
    """
    video_count = buckets["video"]["count"]
    pdf_count = buckets["pdf"]["count"]
    image_count = buckets["image"]["count"]

    # Visual chunks (per-slide for videos, per-page for PDFs, one per image)
    slide_chunks = video_count * AVG_SLIDES_PER_VIDEO
    page_chunks = pdf_count * AVG_PAGES_PER_PDF
    image_chunks = image_count * AVG_CHUNKS_PER_IMAGE
    total_visual = slide_chunks + page_chunks + image_chunks

    vision_cost = total_visual * COST_PER_VISION_CALL
    embedding_cost = total_visual * COST_PER_EMBEDDING
    haiku_cost = total_visual * COST_PER_HAIKU_CHUNK_WRAP
    total = vision_cost + embedding_cost + haiku_cost

    return {
        "assumptions": {
            "avg_slides_per_video": AVG_SLIDES_PER_VIDEO,
            "avg_pages_per_pdf": AVG_PAGES_PER_PDF,
            "avg_chunks_per_image": AVG_CHUNKS_PER_IMAGE,
        },
        "projected_chunks": {
            "from_videos": slide_chunks,
            "from_pdfs": page_chunks,
            "from_images": image_chunks,
            "total": total_visual,
        },
        "cost_usd": {
            "gemini_vision": round(vision_cost, 4),
            "openai_embeddings": round(embedding_cost, 4),
            "haiku_context_wrap": round(haiku_cost, 4),
            "total": round(total, 4),
        },
    }


# ---------------------------------------------------------------------------
# Human-readable reporting
# ---------------------------------------------------------------------------

def _fmt_bytes(n: int) -> str:
    """Format a byte count like '1.2 GB'."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def print_summary(program_slug: str, buckets: dict, cost: dict) -> None:
    """Print a nice human-readable summary to stdout."""
    prog = config.PROGRAMS[program_slug]
    print()
    print("=" * 70)
    print(f"INVENTORY: {prog['name']} ({program_slug})")
    print(f"Drive folder: {prog['drive_folder_id']}")
    print("=" * 70)
    print()
    print(f"{'Pipeline':<18}{'Count':>10}{'Total size':>20}")
    print("-" * 48)
    order = ("video", "pdf", "image", "google_doc", "google_slides", "skip", "folder")
    for key in order:
        b = buckets.get(key, _bucket())
        size_str = _fmt_bytes(b["total_bytes"]) if b["total_bytes"] else "—"
        print(f"{key:<18}{b['count']:>10}{size_str:>20}")
    print()
    print("Projected chunks (for cost estimation):")
    pc = cost["projected_chunks"]
    print(f"  from videos: {pc['from_videos']:>6}  "
          f"(videos x {cost['assumptions']['avg_slides_per_video']} slides)")
    print(f"  from PDFs:   {pc['from_pdfs']:>6}  "
          f"(PDFs x {cost['assumptions']['avg_pages_per_pdf']} pages)")
    print(f"  from images: {pc['from_images']:>6}")
    print(f"  total:       {pc['total']:>6}")
    print()
    print("Estimated ingestion cost (USD):")
    c = cost["cost_usd"]
    print(f"  Gemini vision calls:  ${c['gemini_vision']:>8.4f}")
    print(f"  OpenAI embeddings:    ${c['openai_embeddings']:>8.4f}")
    print(f"  Haiku context wrap:   ${c['haiku_context_wrap']:>8.4f}")
    print(f"  TOTAL:                ${c['total']:>8.4f}")
    print()
    print("Note: these numbers assume ~40 slides/video and ~10 pages/PDF.")
    print("Actuals will be refined after the Session 2 pilot.")
    print()


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_inventory(args: argparse.Namespace) -> int:
    """Run the inventory subcommand."""
    if args.program not in config.PROGRAMS:
        print(f"ERROR: unknown program '{args.program}'. "
              f"Choices: {', '.join(config.PROGRAMS.keys())}", file=sys.stderr)
        return 2

    prog = config.PROGRAMS[args.program]
    folder_id = prog["drive_folder_id"]

    print(f"[inventory] starting walk of {prog['name']} ({args.program})")
    print(f"[inventory] root folder id: {folder_id}")

    try:
        client = DriveClient()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(f"[inventory] service account: {client.service_account_email}")

    files: list[DriveFile] = []
    folder_count = 0
    file_count = 0
    try:
        for rec in client.walk(folder_id):
            files.append(rec)
            if rec.pipeline == "folder":
                folder_count += 1
            else:
                file_count += 1
            # Light progress indicator every 25 items
            if (folder_count + file_count) % 25 == 0:
                print(f"[inventory] ... {folder_count} folders, {file_count} files so far")
    except RuntimeError as e:
        print(f"ERROR during walk: {e}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Common causes:", file=sys.stderr)
        print("  - Service account not shared on the folder (share as Viewer)", file=sys.stderr)
        print("  - Wrong folder ID in ingester/config.py", file=sys.stderr)
        print("  - Drive API not enabled on the GCP project", file=sys.stderr)
        return 1

    print(f"[inventory] walk complete: {folder_count} folders, {file_count} files")

    buckets = aggregate(files)
    cost = estimate_cost(buckets)

    report = {
        "program": args.program,
        "program_name": prog["name"],
        "drive_folder_id": folder_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "service_account": client.service_account_email,
        "totals": {
            "folders": folder_count,
            "files": file_count,
        },
        "by_pipeline": buckets,
        "cost_estimate": cost,
    }

    # Decide where to write the report
    if args.output:
        output_path = Path(args.output)
    else:
        # Local dev default: write next to the repo so we can `cat` it
        output_path = Path(f"inventory_{args.program}.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))
    print(f"[inventory] report written: {output_path}")

    print_summary(args.program, buckets, cost)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ingester",
        description="Reimagined Fertility content ingester",
    )
    sub = p.add_subparsers(dest="command", required=True)

    inv = sub.add_parser(
        "inventory",
        help="Walk a program's Drive folder and produce an inventory + cost estimate",
    )
    inv.add_argument(
        "--program",
        required=True,
        choices=list(config.PROGRAMS.keys()),
        help="Which program to inventory",
    )
    inv.add_argument(
        "--output",
        default=None,
        help="Path to write the JSON report (default: ./inventory_<program>.json)",
    )
    inv.set_defaults(func=cmd_inventory)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
