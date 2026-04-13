#!/usr/bin/env python3
"""
Session 12 — build image/OCR side-by-side review page.

Reuses v2 loader helpers (export_html, walk_html_in_order, resolve_image_bytes)
to pull embedded images from the 3 image-heavy Supplement Info docs, hashes
each against the existing OCR cache, and writes an HTML viewer.

No Gemini calls. No Chroma writes. Cache-only. $0.
"""
import hashlib
import html as html_lib
import json
import os
from pathlib import Path

from ingester.drive_client import DriveClient
from ingester.loaders.drive_loader_v2 import (
    export_html,
    walk_html_in_order,
    resolve_image_bytes,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "data" / "image_samples"
CACHE_DIR = REPO_ROOT / "data" / "image_ocr_cache"
FOLDER_ID = "1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_cache_entry(sha: str) -> dict | None:
    path = CACHE_DIR / f"{sha}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUTPUT_DIR.glob("*.png"):
        old.unlink()
    for old in OUTPUT_DIR.glob("*.jpg"):
        old.unlink()

    client = DriveClient()

    # List the pilot folder
    files = list(client.list_children(FOLDER_ID))
    doc_files = [
        f for f in files
        if f.get("mimeType") == "application/vnd.google-apps.document"
    ]
    print(f"Found {len(doc_files)} Google Docs in pilot folder")

    rows = []  # each row: {doc_name, img_index, sha, ocr_entry, local_png_path}

    for doc in doc_files:
        doc_name = doc["name"]
        doc_id = doc["id"]
        print(f"\n=== {doc_name} ===")
        try:
            html_bytes = export_html(client, doc_id)
        except Exception as e:
            print(f"  export failed: {e}")
            continue

        stream = walk_html_in_order(html_bytes)
        img_nodes = [n for n in stream if n["kind"] == "image"]
        print(f"  {len(img_nodes)} image nodes in HTML stream")

        doc_slug = "".join(c if c.isalnum() else "_" for c in doc_name)[:40]

        for img_idx, node in enumerate(img_nodes, 1):
            src = node.get("src", "")
            try:
                img_bytes, mime = resolve_image_bytes(client, src)
            except Exception as e:
                print(f"  img {img_idx}: resolve failed: {e}")
                continue

            sha = sha256_bytes(img_bytes)
            ext = "png" if "png" in mime else ("jpg" if "jpeg" in mime else "bin")
            local_name = f"{doc_slug}__img{img_idx:02d}__{sha[:8]}.{ext}"
            local_path = OUTPUT_DIR / local_name
            local_path.write_bytes(img_bytes)

            cache_entry = load_cache_entry(sha)
            rows.append({
                "doc_name": doc_name,
                "img_index": img_idx,
                "sha": sha,
                "local_filename": local_name,
                "mime": mime,
                "byte_size": len(img_bytes),
                "cache_entry": cache_entry,
            })
            status = "CACHED" if cache_entry else "NO CACHE"
            print(f"  img {img_idx}: sha={sha[:12]} {len(img_bytes)}B [{status}]")

    print(f"\nTotal images extracted: {len(rows)}")
    print(f"With cache hits:        {sum(1 for r in rows if r['cache_entry'])}")
    print(f"Unique SHAs:            {len({r['sha'] for r in rows})}")

    build_html(rows)
    return 0


HTML_HEAD = """<!doctype html>
<html><head><meta charset="utf-8">
<title>Session 12 — OCR Image Review</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; color: #222; }
  h1 { color: #142A40; }
  .summary { background: #fff; padding: 16px 20px; border-left: 4px solid #142A40; margin-bottom: 24px; }
  .doc-header { background: #142A40; color: #fff; padding: 12px 20px; margin-top: 32px; font-size: 18px; font-weight: 600; }
  .row { display: flex; background: #fff; margin-bottom: 16px; border: 1px solid #ddd; }
  .img-col { flex: 0 0 45%; padding: 16px; border-right: 1px solid #eee; display: flex; align-items: center; justify-content: center; background: #fafafa; }
  .img-col img { max-width: 100%; max-height: 600px; object-fit: contain; border: 1px solid #ccc; }
  .txt-col { flex: 1; padding: 16px 20px; }
  .meta { font-size: 12px; color: #888; margin-bottom: 8px; font-family: monospace; }
  .meta .decorative { color: #b00; font-weight: 600; }
  .meta .ok { color: #0a0; font-weight: 600; }
  pre.ocr { white-space: pre-wrap; font-family: "SF Mono", Monaco, monospace; font-size: 12px; background: #f8f8f8; padding: 12px; border: 1px solid #eee; max-height: 600px; overflow-y: auto; }
  .no-cache { color: #b00; font-style: italic; }
  .flag-christina { background: #fff3cd; border-left: 4px solid #f0ad4e; padding: 8px 12px; margin-top: 8px; font-size: 12px; }
</style>
</head><body>
<h1>Session 12 — OCR Image Review</h1>
<div class="summary">
  <strong>Purpose:</strong> visually verify Gemini OCR against source images before the v2 guard fix lands.<br>
  <strong>Scope:</strong> all images embedded in Supplement Info Google Docs.<br>
  <strong>Cost:</strong> $0 (cache-only, no new Gemini calls).<br>
  <strong>Flagged rows</strong> — look for the yellow "Dr. Christina detected" boxes. These are the cases where the name-scrub rule will activate.
</div>
"""


def build_html(rows: list[dict]) -> None:
    parts = [HTML_HEAD]

    # Group by doc
    by_doc: dict[str, list[dict]] = {}
    for r in rows:
        by_doc.setdefault(r["doc_name"], []).append(r)

    for doc_name, doc_rows in by_doc.items():
        parts.append(f'<div class="doc-header">{html_lib.escape(doc_name)} — {len(doc_rows)} images</div>')
        for r in doc_rows:
            cache = r["cache_entry"]
            parts.append('<div class="row">')
            parts.append(f'  <div class="img-col"><img src="{r["local_filename"]}" alt="img {r["img_index"]}"></div>')
            parts.append('  <div class="txt-col">')

            meta_bits = [
                f'#{r["img_index"]}',
                f'sha={r["sha"][:12]}',
                f'{r["byte_size"]}B',
                f'{r["mime"]}',
            ]
            if cache:
                if cache.get("is_decorative"):
                    meta_bits.append('<span class="decorative">DECORATIVE</span>')
                else:
                    txt = cache.get("ocr_text", "") or ""
                    meta_bits.append(f'<span class="ok">{len(txt.split())} words</span>')
                meta_bits.append(f'prompt={cache.get("prompt_version", "?")}')
            else:
                meta_bits.append('<span class="no-cache">NO CACHE ENTRY</span>')

            parts.append(f'    <div class="meta">{" · ".join(meta_bits)}</div>')

            if cache:
                if cache.get("is_decorative"):
                    parts.append('    <pre class="ocr"><em>(decorative — no text to OCR)</em></pre>')
                else:
                    ocr_text = cache.get("ocr_text", "") or ""
                    escaped = html_lib.escape(ocr_text)
                    parts.append(f'    <pre class="ocr">{escaped}</pre>')
                    # Flag Christina/Chris/Massinople hits
                    low = ocr_text.lower()
                    if any(t in low for t in ["christina", "massinople", "dr. chris", "dr chris"]):
                        parts.append('    <div class="flag-christina">⚠ Name-scrub rule will activate on this row</div>')
            else:
                parts.append('    <pre class="ocr"><em>(no cache entry — this image was not OCR\'d in session 11)</em></pre>')

            parts.append('  </div>')
            parts.append('</div>')

    parts.append('</body></html>')

    index = OUTPUT_DIR / "index.html"
    index.write_text("\n".join(parts))
    print(f"\nWrote viewer: {index}")
    print(f"Open with: open '{index}'")


if __name__ == "__main__":
    raise SystemExit(main())
