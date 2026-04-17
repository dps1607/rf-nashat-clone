"""BACKLOG #56 — WordPress blog loader (first non-Drive ingestion pipeline).

Pulls published blog posts from a WordPress site via the wp-json REST API,
extracts plain text from the rendered HTML, chunks + scrubs + dedups via
the existing shared helpers, and upserts into a local Chroma collection.

Architectural note (s28-extended): this is a parallel ingester to
`drive_loader_v3.py`. Different source (WP REST), same sink (Chroma via
OpenAIEmbeddingFunction text-embedding-3-large). Reuses the following from
ingester/:
  - chunk_with_locators (ingester.loaders.types)   → scrub + locator deriv
  - _compute_content_hash (ingester.loaders.drive_loader_v3) → stage-2 dedup
  - _check_dedup                                   → stage-2 dedup enforce
  - assert_local_chroma_path                       → no-Railway guard
  - OpenAIEmbeddingFunction(text-embedding-3-large) → embedding parity

Invariants for cross-collection consistency:
  - Embeddings are computed by the same function used for every other
    chunk in rf_published_content / rf_reference_library / rf_coaching_*.
    That guarantees query-time similarity is comparable.
  - Scrub Layer B runs automatically via chunk_with_locators. Any future
    former-collaborator refs in blog text will be scrubbed without any
    blog-specific code.
  - Chunk IDs use the `wp:` prefix to disambiguate from `drive:` IDs.
    Build format: wp:<site_host>:<wp_post_id>:<chunk_index:04d>

CLI:
  ./venv/bin/python -m ingester.blog_loader \\
      --site https://drnashatlatib.com \\
      --library rf_published_content \\
      --limit 1                         # dry-run (default), 1 post
  ./venv/bin/python -m ingester.blog_loader \\
      --site https://drnashatlatib.com \\
      --library rf_published_content \\
      --limit 1 --commit                # actual Chroma write, 1 post
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import html as _html
import json
import logging
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Optional

from dotenv import load_dotenv

log = logging.getLogger(__name__)

# --- Constants shared with v3 for downstream consistency --------------------

SOURCE_PIPELINE = "blog_loader"
V3_CATEGORY = "wp_post"
EXTRACTION_METHOD = "wp_rest"

# Matches v3 constants for embedding cost math
EMBEDDING_PRICE_PER_1M_TOKENS_USD = 0.13
APPROX_CHARS_PER_TOKEN = 4

# WP REST throttling (free self-hosted WP behind Cloudflare)
REST_PAGE_SIZE = 100
REST_DELAY_SECONDS = 0.5  # between pages
REST_USER_AGENT = "Mozilla/5.0 (Compatible; RF-Ingester/0.1)"

# ----------------------------------------------------------------------------
# HTML → plain text extraction
# ----------------------------------------------------------------------------

# Shortcode pattern: [tag attr="..."]...[/tag] and self-closing [tag ...]
_SHORTCODE_BLOCK = re.compile(
    r"\[(?P<tag>[a-zA-Z][a-zA-Z0-9_\-]*)[^\]]*\](.*?)\[/\1\]",
    re.DOTALL,
)
_SHORTCODE_INLINE = re.compile(r"\[/?[a-zA-Z][a-zA-Z0-9_\-]*[^\]]*\]")

# Collapse runs of 3+ newlines to 2
_MULTI_NEWLINE = re.compile(r"\n{3,}")


def extract_plain_text_from_html(html_content: str) -> str:
    """Convert rendered blog HTML to plain text ready for chunking.

    Pipeline:
      1. BeautifulSoup parse → strip script/style/iframe/comment nodes
      2. Replace <img alt="..."> with alt text (or drop if no alt)
      3. Get visible text with paragraph breaks preserved
      4. Strip WordPress shortcodes while preserving inner content
      5. Decode HTML entities (soup does this automatically in get_text)
      6. Collapse excess whitespace

    Returns an empty string for empty/blank input — chunker handles that.
    """
    if not html_content:
        return ""
    from bs4 import BeautifulSoup, Comment  # lazy import

    soup = BeautifulSoup(html_content, "html.parser")

    # Drop noisy elements entirely
    for tag in soup(["script", "style", "iframe", "noscript"]):
        tag.decompose()

    # Drop HTML comments
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()

    # Replace images with alt text (if any)
    for img in soup.find_all("img"):
        alt = img.get("alt", "").strip()
        if alt:
            img.replace_with(alt)
        else:
            img.decompose()

    # Convert <br> to newlines for cleaner text
    for br in soup.find_all("br"):
        br.replace_with("\n")

    # get_text with newline separators between block elements
    text = soup.get_text(separator="\n")

    # Strip shortcodes: first block form with content, then inline
    text = _SHORTCODE_BLOCK.sub(lambda m: m.group(2), text)
    text = _SHORTCODE_INLINE.sub("", text)

    # Decode any lingering entities the parser didn't catch
    text = _html.unescape(text)

    # Normalize whitespace — trim line whitespace, collapse multi-newlines
    lines = [ln.strip() for ln in text.splitlines()]
    text = "\n".join(lines)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    # Trim outer whitespace
    return text.strip()


def _strip_html_for_title(html_title: str) -> str:
    """Extract plain text from a title HTML snippet (no paragraph semantics)."""
    if not html_title:
        return ""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_title, "html.parser")
    # Single line of text, whitespace normalized
    text = soup.get_text(separator=" ")
    text = _html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ----------------------------------------------------------------------------
# Post → file_record (virtual, matches v3 file_record shape)
# ----------------------------------------------------------------------------

def post_to_file_record(post: dict) -> dict:
    """Construct the file_record virtual for a WP post.

    Mirrors the shape built in drive_loader_v3._process_file so downstream
    helpers (build_metadata_base, dedup, content_hash) can operate uniformly.
    """
    rendered = (post.get("content") or {}).get("rendered") or ""
    title_raw = (post.get("title") or {}).get("rendered") or ""
    display_title = _strip_html_for_title(title_raw)
    # Stable pseudo-md5 over rendered HTML — enables stage-1 dedup even
    # without Drive's md5Checksum. Uses md5 hex digest (32 chars) to keep
    # the same field width as Drive values.
    pseudo_md5 = hashlib.md5(rendered.encode("utf-8")).hexdigest()
    return {
        "id": str(post.get("id", "")),
        "name": post.get("slug", "") or str(post.get("id", "")),
        "mime_type": "text/html",
        "modified_time": post.get("modified", "") or "",
        "size": len(rendered),
        "web_view_link": post.get("link", "") or "",
        "md5_checksum": pseudo_md5,
        "display_title": display_title,
    }


# ----------------------------------------------------------------------------
# Chunk ID — separate namespace from drive:... IDs
# ----------------------------------------------------------------------------

def build_blog_chunk_id(site_host: str, post_id: int, chunk_index: int) -> str:
    """Deterministic, collision-proof chunk ID for blog chunks.

    Format: wp:<site_host>:<post_id>:<chunk_index 0-padded to 4>
    Example: wp:drnashatlatib.com:18885:0000
    """
    return f"wp:{site_host}:{post_id}:{chunk_index:04d}"


# ----------------------------------------------------------------------------
# Metadata — mirrors v3's build_metadata_base + blog-specific extras
# ----------------------------------------------------------------------------

def build_blog_metadata(
    *,
    chunk: dict,
    post: dict,
    library: str,
    run_id: str,
    ingest_ts: str,
    content_hash: str,
    category_names: dict,
    tag_names: dict,
    author_names: dict,
) -> dict:
    """Construct full metadata dict for one blog chunk.

    Chroma only accepts scalar metadata values (str/int/float/bool). Lists
    are joined to comma-separated strings here.
    """
    file_rec = post_to_file_record(post)

    # Resolve taxonomy IDs to names
    cat_ids = post.get("categories", []) or []
    tag_ids = post.get("tags", []) or []
    cats_resolved = ", ".join(sorted(category_names.get(cid, "") for cid in cat_ids if category_names.get(cid, "")))
    tags_resolved = ", ".join(sorted(tag_names.get(tid, "") for tid in tag_ids if tag_names.get(tid, "")))
    author_id = post.get("author", 0)
    author_resolved = author_names.get(author_id, "") or ""

    return {
        # Sequence + sizing
        "chunk_index": chunk["chunk_index"],
        "word_count": chunk["word_count"],
        # Scrub observability
        "name_replacements": chunk.get("name_replacements", 0),
        # Provenance
        "source_pipeline": SOURCE_PIPELINE,
        "source_collection": library,
        "library_name": library,
        "source_drive_slug": "wp-blog",            # virtual — WP source, not Drive
        "source_drive_id": file_rec["web_view_link"].split("/")[2] if file_rec["web_view_link"] else "",
        "source_folder_id": "blog",
        "source_folder_path": "Website Blog",
        "source_file_id": file_rec["id"],
        "source_file_name": file_rec["name"],
        "source_file_mime": file_rec["mime_type"],
        "source_file_modified_time": file_rec["modified_time"],
        "source_file_size_bytes": file_rec["size"],
        "source_web_view_link": file_rec["web_view_link"],
        "source_file_md5": file_rec["md5_checksum"],
        # Run identity
        "ingest_run_id": run_id,
        "ingest_timestamp_utc": ingest_ts,
        # s19 backfill fields
        "extraction_method": EXTRACTION_METHOD,
        "content_hash": content_hash,
        # v3 category convention
        "v3_category": V3_CATEGORY,
        "v3_extraction_method": EXTRACTION_METHOD,
        "source_unit_label": "post",
        # Locator / timestamp (unused for blogs)
        "display_locator": chunk.get("display_locator") or "",
        "display_timestamp": chunk.get("display_timestamp") or "",
        # Display fields
        "display_source": file_rec["display_title"] or file_rec["name"],
        "display_subheading": cats_resolved,
        "display_speaker": "",
        "display_date": post.get("date", "") or "",
        "display_topics": tags_resolved,
        # WP-specific extras
        "wp_post_id": int(post.get("id", 0)),
        "wp_slug": post.get("slug", "") or "",
        "wp_canonical_url": file_rec["web_view_link"],
        "wp_categories": cats_resolved,
        "wp_tags": tags_resolved,
        "wp_author": author_resolved,
    }


# ----------------------------------------------------------------------------
# WP REST API client
# ----------------------------------------------------------------------------

class WordPressRestClient:
    """Thin wrapper around wp-json/wp/v2 endpoints for posts + taxonomies."""

    def __init__(self, site_url: str, session=None, delay_seconds: float = REST_DELAY_SECONDS):
        import requests  # lazy import
        self.site_url = site_url.rstrip("/")
        self.delay = delay_seconds
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": REST_USER_AGENT})

    @property
    def host(self) -> str:
        from urllib.parse import urlparse
        return urlparse(self.site_url).netloc

    def _get(self, path: str, params: Optional[dict] = None) -> tuple[Any, dict]:
        url = f"{self.site_url}/wp-json/wp/v2/{path.lstrip('/')}"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json(), dict(resp.headers)

    def count_posts(self) -> int:
        _, headers = self._get("posts", {"per_page": 1})
        return int(headers.get("x-wp-total", "0"))

    def iter_posts(self, limit: Optional[int] = None) -> Iterable[dict]:
        page = 1
        yielded = 0
        while True:
            params = {
                "per_page": REST_PAGE_SIZE,
                "page": page,
                # Tell WP we want everything including content; no _fields filter
                # so we get content.rendered + everything else
            }
            posts, headers = self._get("posts", params)
            if not posts:
                return
            for p in posts:
                yield p
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            total_pages = int(headers.get("x-wp-totalpages", "1"))
            if page >= total_pages:
                return
            page += 1
            if self.delay:
                time.sleep(self.delay)

    def fetch_taxonomy_names(self, taxonomy: str, ids: list[int]) -> dict:
        """Batch-resolve taxonomy IDs to names. `taxonomy` is 'categories' or 'tags'."""
        if not ids:
            return {}
        # WP REST supports ?include=<csv> for efficient batch fetch
        include_csv = ",".join(str(i) for i in sorted(set(ids)))
        data, _ = self._get(taxonomy, {"per_page": 100, "include": include_csv})
        return {t["id"]: t.get("name", "") for t in data}

    def fetch_author_names(self, ids: list[int]) -> dict:
        if not ids:
            return {}
        include_csv = ",".join(str(i) for i in sorted(set(ids)))
        try:
            data, _ = self._get("users", {"per_page": 100, "include": include_csv})
            return {u["id"]: u.get("name", "") for u in data}
        except Exception:
            # Many WP installs restrict /users to logged-in roles. Swallow and
            # leave author names empty; post content still ingests.
            return {}


# ----------------------------------------------------------------------------
# Run entry point
# ----------------------------------------------------------------------------

def _make_run_id() -> str:
    return uuid.uuid4().hex[:16]


def _utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_chroma_client(chroma_path: Path):
    import chromadb
    return chromadb.PersistentClient(path=str(chroma_path))


def _get_embedding_function():
    """Match v3's commit-path embedding function exactly for cross-collection parity."""
    from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set — embedding function cannot be built")
    return OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name="text-embedding-3-large",
    )


def run(args: argparse.Namespace) -> int:
    from ingester.loaders._drive_common import assert_local_chroma_path
    from ingester.loaders.drive_loader_v3 import _compute_content_hash, _check_dedup
    from ingester.loaders.types import chunk_with_locators

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # ------------------------------------------------------------------
    # 1. Guards + environment
    # ------------------------------------------------------------------
    chroma_path = assert_local_chroma_path()
    run_id = _make_run_id()
    ingest_ts = _utc_now_iso()

    site_url = args.site.rstrip("/")
    library = args.library
    limit = args.limit
    commit = args.commit

    mode = "COMMIT" if commit else "DRY-RUN"
    print("=" * 70)
    print(f"blog_loader — {mode}")
    print("=" * 70)
    print(f"  site:        {site_url}")
    print(f"  library:     {library}")
    print(f"  limit:       {limit if limit is not None else '(all)'}")
    print(f"  chroma_path: {chroma_path}")
    print(f"  run_id:      {run_id}")

    # ------------------------------------------------------------------
    # 2. Fetch posts + taxonomies
    # ------------------------------------------------------------------
    client = WordPressRestClient(site_url)
    total_available = client.count_posts()
    print(f"\n  posts available on site: {total_available}")

    posts = list(client.iter_posts(limit=limit))
    print(f"  posts fetched this run:  {len(posts)}")
    if not posts:
        print("  no posts to process. exiting.")
        return 0

    # Resolve taxonomies in bulk
    cat_ids_all: list[int] = []
    tag_ids_all: list[int] = []
    author_ids_all: list[int] = []
    for p in posts:
        cat_ids_all.extend(p.get("categories", []) or [])
        tag_ids_all.extend(p.get("tags", []) or [])
        author_ids_all.append(p.get("author", 0))
    print("  resolving taxonomy names...")
    category_names = client.fetch_taxonomy_names("categories", cat_ids_all)
    tag_names = client.fetch_taxonomy_names("tags", tag_ids_all)
    author_names = client.fetch_author_names(author_ids_all)
    print(f"    categories: {len(category_names)}  tags: {len(tag_names)}  authors: {len(author_names)}")

    # ------------------------------------------------------------------
    # 3. Per-post extraction + chunk assembly (no writes yet)
    # ------------------------------------------------------------------
    all_chunks_to_write: list[dict] = []
    per_post_summary: list[dict] = []
    total_chars_for_embedding = 0

    for post in posts:
        rendered_html = (post.get("content") or {}).get("rendered") or ""
        plain_text = extract_plain_text_from_html(rendered_html)
        chunks = chunk_with_locators(plain_text)
        content_hash = _compute_content_hash(plain_text)
        file_rec = post_to_file_record(post)

        per_post_summary.append({
            "wp_post_id": post.get("id"),
            "slug": post.get("slug"),
            "display_title": file_rec["display_title"],
            "plain_text_chars": len(plain_text),
            "chunk_count": len(chunks),
            "content_hash": content_hash,
            "modified": post.get("modified"),
        })

        for chunk in chunks:
            meta = build_blog_metadata(
                chunk=chunk, post=post, library=library,
                run_id=run_id, ingest_ts=ingest_ts, content_hash=content_hash,
                category_names=category_names, tag_names=tag_names,
                author_names=author_names,
            )
            cid = build_blog_chunk_id(client.host, post["id"], chunk["chunk_index"])
            all_chunks_to_write.append({
                "id": cid,
                "text": chunk["text"],
                "metadata": meta,
                "library": library,
                "file_id_for_dedup": file_rec["id"],
                "content_hash_for_dedup": content_hash,
            })
            total_chars_for_embedding += len(chunk["text"])

    # ------------------------------------------------------------------
    # 4. Cost estimate + stage-2 dedup preview
    # ------------------------------------------------------------------
    est_tokens = total_chars_for_embedding // APPROX_CHARS_PER_TOKEN
    est_cost = est_tokens / 1_000_000 * EMBEDDING_PRICE_PER_1M_TOKENS_USD

    print("\n" + "=" * 70)
    print("Run summary")
    print("=" * 70)
    print(f"  posts processed:    {len(posts)}")
    print(f"  total chunks:       {len(all_chunks_to_write)}")
    print(f"  total chars:        {total_chars_for_embedding:,}")
    print(f"  est embed tokens:   {est_tokens:,}")
    print(f"  est embed cost:     ${est_cost:.6f}  "
          f"(text-embedding-3-large @ ${EMBEDDING_PRICE_PER_1M_TOKENS_USD}/1M tokens)")
    print()
    print("  per-post breakdown:")
    for s in per_post_summary:
        print(f"    post {s['wp_post_id']:>6}  chunks={s['chunk_count']:>2}  "
              f"chars={s['plain_text_chars']:>5}  slug={s['slug']!r}")

    # Stage-2 dedup check against the target collection (only if it exists)
    ef = None
    dst = None
    dup_skip_files: dict[str, str] = {}
    if commit:
        ef = _get_embedding_function()
        chroma_client = _get_chroma_client(chroma_path)
        dst = chroma_client.get_or_create_collection(
            name=library, embedding_function=ef
        )
        # Per-file dedup check (content_hash is per-file-level, not per-chunk)
        checked_files = set()
        for ch in all_chunks_to_write:
            fid = ch["file_id_for_dedup"]
            if fid in checked_files:
                continue
            checked_files.add(fid)
            existing = _check_dedup(
                dst, content_hash=ch["content_hash_for_dedup"], current_file_id=fid,
            )
            if existing:
                dup_skip_files[fid] = existing
        if dup_skip_files:
            print(f"\n  stage-2 dedup skips: {len(dup_skip_files)} files match existing chunks")
            for fid, existing in dup_skip_files.items():
                print(f"    - wp_post_id={fid} matches existing file_id={existing}")
            all_chunks_to_write = [c for c in all_chunks_to_write if c["file_id_for_dedup"] not in dup_skip_files]
            print(f"  total chunks after dedup: {len(all_chunks_to_write)}")

    # ------------------------------------------------------------------
    # 5. Commit (or stop at dry-run)
    # ------------------------------------------------------------------
    run_record = {
        "run_id": run_id,
        "pipeline": SOURCE_PIPELINE,
        "mode": mode,
        "ingest_timestamp_utc": ingest_ts,
        "site_url": site_url,
        "library": library,
        "limit": limit,
        "posts_processed": len(posts),
        "total_chunks_before_dedup": len(all_chunks_to_write) + sum(
            1 for c in [] if c["file_id_for_dedup"] in dup_skip_files  # dup count
        ),
        "total_chunks_to_write": len(all_chunks_to_write),
        "stage2_dedup_skips": list(dup_skip_files.keys()),
        "estimated_embed_tokens": est_tokens,
        "estimated_embed_cost_usd": round(est_cost, 6),
        "per_post": per_post_summary,
    }

    # Write run record
    ingest_runs_dir = Path(REPO_ROOT if False else ".") / "data" / "ingest_runs"
    ingest_runs_dir = Path.cwd() / "data" / "ingest_runs"
    ingest_runs_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if commit else ".dry_run"
    record_path = ingest_runs_dir / f"{run_id}{suffix}.json"
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(run_record, f, indent=2)
    print(f"\n  run record: {record_path}")

    if not commit:
        print("\n  [DRY-RUN] No Chroma writes. Re-run with --commit to perform.")
        return 0

    # Commit path
    print(f"\n  writing {len(all_chunks_to_write)} chunks to {library}...")
    if not all_chunks_to_write:
        print("  (no chunks to write — all deduped)")
        return 0

    # Batch upsert — Chroma's OpenAIEmbeddingFunction embeds in chunks of 100
    # internally, but we still pass the full list in one call.
    ids = [c["id"] for c in all_chunks_to_write]
    documents = [c["text"] for c in all_chunks_to_write]
    metadatas = [c["metadata"] for c in all_chunks_to_write]
    dst.upsert(ids=ids, documents=documents, metadatas=metadatas)
    print(f"  upsert complete. {library} now has {dst.count()} chunks.")

    # Append to audit log
    audit_path = Path.cwd() / "data" / "audit.jsonl"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_entry = {
        "ts": ingest_ts,
        "event": "blog_loader_commit",
        "run_id": run_id,
        "library": library,
        "chunks_written": len(all_chunks_to_write),
        "posts_processed": len(posts),
        "estimated_cost_usd": round(est_cost, 6),
    }
    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(audit_entry) + "\n")
    print(f"  audit entry appended to {audit_path}")

    return 0


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--site", required=True, help="Base URL of the WordPress site")
    parser.add_argument("--library", required=True, help="Target Chroma collection name")
    parser.add_argument("--limit", type=int, default=None, help="Max posts to process")
    parser.add_argument("--commit", action="store_true", help="Perform writes. Default is dry-run.")
    args = parser.parse_args()

    try:
        return run(args)
    except KeyboardInterrupt:
        print("\ninterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
