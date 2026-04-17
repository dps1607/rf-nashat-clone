"""BACKLOG #57 — ActiveCampaign email ingester.

Pulls email messages from ActiveCampaign v3 REST API since 2022, runs each
through the Haiku classifier (ingester.classify) to filter out operational/
transactional content, extracts plain text via blog_loader's HTML helper,
chunks + scrubs + dedups via the existing shared pipeline, and upserts into
the local Chroma collection.

Parallel ingester pattern (matches blog_loader.py). Different source
(AC REST vs WP REST), same sink (rf_published_content). Reuses:
  - blog_loader.extract_plain_text_from_html → HTML cleaning
  - ingester.loaders.types.chunk_with_locators → scrub Layer B + chunking
  - ingester.loaders.drive_loader_v3._compute_content_hash + _check_dedup
  - ingester.loaders._drive_common.assert_local_chroma_path
  - ingester.classify.is_operational → marketing-vs-operational filter

Chunk-ID namespace: email-ac:<account_host>:<message_id>:<chunk_index:04d>

CLI:
  ./venv/bin/python -m ingester.ac_email_loader \\
      --library rf_published_content --limit 10       # dry-run (default)
  ./venv/bin/python -m ingester.ac_email_loader \\
      --library rf_published_content --limit 1 --commit  # actual Chroma write
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env", override=True)

log = logging.getLogger(__name__)

SOURCE_PIPELINE = "ac_email_loader"
V3_CATEGORY = "ac_email"
EXTRACTION_METHOD = "ac_messages_api"

EMBEDDING_PRICE_PER_1M_TOKENS_USD = 0.13
APPROX_CHARS_PER_TOKEN = 4

DATE_FLOOR = "2022-01-01"  # Only ingest messages created >= this date

REST_PAGE_SIZE = 100
REST_DELAY_SECONDS = 0.3  # between pages + between detail calls

AC_API_URL = (os.environ.get("AC_API_URL") or "").rstrip("/")
AC_API_KEY = os.environ.get("AC_API_KEY") or ""


# -----------------------------------------------------------------------------
# Redaction for any error / log output that might touch env values
# -----------------------------------------------------------------------------
_SECRETS = sorted(
    [
        (AC_API_KEY, "<REDACTED-AC-KEY>"),
        (AC_API_URL, "<REDACTED-AC-URL>"),
        (urlparse(AC_API_URL).hostname.split(".")[0] if urlparse(AC_API_URL).hostname else "", "<REDACTED-ACCOUNT>"),
    ],
    key=lambda x: -len(x[0] or ""),
)
_SECRETS = [(s, p) for s, p in _SECRETS if s]


def _redact(obj) -> str:
    s = str(obj)
    for secret, placeholder in _SECRETS:
        s = s.replace(secret, placeholder)
    return s


# -----------------------------------------------------------------------------
# AC REST client
# -----------------------------------------------------------------------------
class ActiveCampaignClient:
    """Thin wrapper around api/3/messages endpoints with cdate filter + pagination."""

    def __init__(self, base_url: str, api_key: str, delay_seconds: float = REST_DELAY_SECONDS):
        import requests  # lazy import
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.delay = delay_seconds
        self.session = requests.Session()
        self.session.headers.update({
            "Api-Token": api_key,
            "Accept": "application/json",
        })

    @property
    def host(self) -> str:
        h = urlparse(self.base_url).hostname
        return h.split(".")[0] if h else "unknown"  # account subdomain

    def _get(self, path: str, params: Optional[dict] = None):
        url = f"{self.base_url}/api/3{path}"
        r = self.session.get(url, params=params or {}, timeout=30)
        if r.status_code >= 400:
            raise RuntimeError(
                f"AC API {r.status_code} on /api/3{path}: "
                f"{_redact(r.text[:200])}"
            )
        return r.json()

    def count_messages_since(self, date_floor: str) -> int:
        """Return total message count matching the cdate filter."""
        data = self._get("/messages", params={
            "limit": 1,
            "filters[cdate_gt]": date_floor,
        })
        meta = data.get("meta", {})
        return int(meta.get("total", 0))

    def iter_messages(self, date_floor: str, limit: Optional[int] = None) -> Iterable[dict]:
        """Paginate through messages since date_floor, yielding full detail dicts.

        List endpoint returns metadata; detail endpoint adds 'html' body. We
        fetch detail per-message since html is the core content we need.
        """
        offset = 0
        yielded = 0
        while True:
            list_data = self._get("/messages", params={
                "limit": REST_PAGE_SIZE,
                "offset": offset,
                "filters[cdate_gt]": date_floor,
                "orders[cdate]": "ASC",
            })
            messages = list_data.get("messages") or []
            if not messages:
                return
            for m in messages:
                mid = m.get("id")
                if not mid:
                    continue
                try:
                    detail_data = self._get(f"/messages/{mid}")
                    detail = detail_data.get("message") or {}
                    # Merge list + detail (detail has more fields including html)
                    merged = {**m, **detail}
                    yield merged
                    yielded += 1
                    if limit is not None and yielded >= limit:
                        return
                except Exception as e:  # noqa: BLE001
                    log.warning(f"detail fetch failed for message {mid}: {_redact(str(e))}")
                    continue
                if self.delay:
                    time.sleep(self.delay)
            offset += len(messages)
            if len(messages) < REST_PAGE_SIZE:
                return


# -----------------------------------------------------------------------------
# Metadata + chunk ID helpers
# -----------------------------------------------------------------------------
def build_ac_chunk_id(account_host: str, message_id: str, chunk_index: int) -> str:
    """Deterministic chunk ID for AC email chunks."""
    return f"email-ac:{account_host}:{message_id}:{chunk_index:04d}"


def message_to_file_record(message: dict) -> dict:
    """Virtual file_record mirroring v3 shape for downstream helpers."""
    html_body = message.get("html") or ""
    subject = (message.get("subject") or "").strip()
    pseudo_md5 = hashlib.md5(html_body.encode("utf-8")).hexdigest()
    return {
        "id": str(message.get("id", "")),
        "name": subject or f"ac-message-{message.get('id')}",
        "mime_type": "text/html",
        "modified_time": message.get("mdate") or "",
        "size": len(html_body),
        "web_view_link": "",  # AC messages don't have a public URL
        "md5_checksum": pseudo_md5,
        "display_subject": subject,
    }


def build_ac_metadata(
    *,
    chunk: dict,
    message: dict,
    library: str,
    run_id: str,
    ingest_ts: str,
    content_hash: str,
    account_host: str,
) -> dict:
    """Chroma metadata for one AC email chunk. Scalar values only."""
    file_rec = message_to_file_record(message)
    return {
        # Sequence
        "chunk_index": chunk["chunk_index"],
        "word_count": chunk["word_count"],
        "name_replacements": chunk.get("name_replacements", 0),
        # Provenance
        "source_pipeline": SOURCE_PIPELINE,
        "source_collection": library,
        "library_name": library,
        "source_drive_slug": "ac-email",
        "source_drive_id": account_host,
        "source_folder_id": "ac-messages",
        "source_folder_path": "ActiveCampaign / Messages",
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
        # s19 backfill + v3 category
        "extraction_method": EXTRACTION_METHOD,
        "content_hash": content_hash,
        "v3_category": V3_CATEGORY,
        "v3_extraction_method": EXTRACTION_METHOD,
        "source_unit_label": "email",
        # Locator / timestamp unused
        "display_locator": chunk.get("display_locator") or "",
        "display_timestamp": chunk.get("display_timestamp") or "",
        # Display fields
        "display_source": file_rec["display_subject"] or f"AC message {file_rec['id']}",
        "display_subheading": "",
        "display_speaker": "",
        "display_date": message.get("cdate") or "",
        "display_topics": "",
        # AC-specific extras
        "ac_message_id": str(message.get("id", "")),
        "ac_subject": file_rec["display_subject"],
        "ac_from_name": message.get("fromname") or "",
        "ac_from_email": message.get("fromemail") or "",
        "ac_reply_to": message.get("reply2") or "",
        "ac_created_at": message.get("cdate") or "",
        "ac_modified_at": message.get("mdate") or "",
        "ac_preheader": message.get("preheader_text") or "",
    }


# -----------------------------------------------------------------------------
# Run entry point
# -----------------------------------------------------------------------------
def _make_run_id() -> str:
    return uuid.uuid4().hex[:16]


def _utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_embedding_function():
    from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set — embedding function cannot be built")
    return OpenAIEmbeddingFunction(api_key=api_key, model_name="text-embedding-3-large")


def run(args: argparse.Namespace) -> int:
    from ingester.blog_loader import extract_plain_text_from_html
    from ingester.classify import classify
    from ingester.loaders._drive_common import assert_local_chroma_path
    from ingester.loaders.drive_loader_v3 import _compute_content_hash, _check_dedup
    from ingester.loaders.types import chunk_with_locators

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if not AC_API_URL or not AC_API_KEY:
        sys.exit("ERROR: AC_API_URL / AC_API_KEY not set in .env")

    chroma_path = assert_local_chroma_path()
    run_id = _make_run_id()
    ingest_ts = _utc_now_iso()

    library = args.library
    limit = args.limit
    commit = args.commit
    date_floor = args.since

    mode = "COMMIT" if commit else "DRY-RUN"
    print("=" * 70)
    print(f"ac_email_loader — {mode}")
    print("=" * 70)
    print(f"  AC base:      <redacted>")  # never echo the URL
    print(f"  library:      {library}")
    print(f"  date floor:   {date_floor}")
    print(f"  limit:        {limit if limit is not None else '(all)'}")
    print(f"  chroma_path:  {chroma_path}")
    print(f"  run_id:       {run_id}")
    print()

    # Fetch messages
    client = ActiveCampaignClient(AC_API_URL, AC_API_KEY)
    total = client.count_messages_since(date_floor)
    print(f"  messages available in AC since {date_floor}: {total}")

    # Per-message: fetch detail, classify, extract, chunk
    kept: list[dict] = []
    skipped_operational: list[dict] = []
    skipped_other: list[dict] = []
    classify_cost = 0.0
    classify_calls = 0
    total_chars_for_embedding = 0

    for msg in client.iter_messages(date_floor, limit=limit):
        subject = (msg.get("subject") or "").strip()
        html_body = msg.get("html") or ""
        plain = extract_plain_text_from_html(html_body)

        if not plain or len(plain) < 50:
            skipped_other.append({
                "message_id": str(msg.get("id", "")),
                "subject": subject[:80],
                "reason": "empty or too-short body",
                "plain_len": len(plain),
            })
            continue

        # Classifier: skip operational
        body_preview = plain[:500]
        verdict = classify(subject=subject, body_preview=body_preview)
        classify_calls += 1
        if not verdict.cached:
            classify_cost += verdict.cost_usd

        if verdict.is_operational:
            skipped_operational.append({
                "message_id": str(msg.get("id", "")),
                "subject": subject[:80],
                "verdict": verdict.verdict,
                "from_email": msg.get("fromemail") or "",
            })
            continue

        # Keep this message — chunk it
        chunks = chunk_with_locators(plain)
        content_hash = _compute_content_hash(plain)
        kept.append({
            "message": msg,
            "chunks": chunks,
            "content_hash": content_hash,
            "subject": subject,
            "plain_len": len(plain),
            "verdict": verdict.verdict,
        })
        for chunk in chunks:
            total_chars_for_embedding += len(chunk["text"])

    # Summary
    est_tokens = total_chars_for_embedding // APPROX_CHARS_PER_TOKEN
    est_embed_cost = est_tokens / 1_000_000 * EMBEDDING_PRICE_PER_1M_TOKENS_USD
    total_chunks_planned = sum(len(k["chunks"]) for k in kept)

    print()
    print("=" * 70)
    print("Classification + extraction summary")
    print("=" * 70)
    print(f"  messages fetched:           {classify_calls}")
    print(f"  kept (marketing/unclear):   {len(kept)}")
    print(f"  skipped (operational):      {len(skipped_operational)}")
    print(f"  skipped (empty/short body): {len(skipped_other)}")
    print(f"  total chunks from kept:     {total_chunks_planned}")
    print(f"  est embed tokens:           {est_tokens:,}")
    print(f"  est embed cost:             ${est_embed_cost:.6f}")
    print(f"  classifier spent this run:  ${classify_cost:.6f}  "
          f"(cached hits = $0)")
    print()

    if skipped_operational:
        print("  skipped OPERATIONAL (classifier verdict):")
        for s in skipped_operational[:15]:
            print(f"    - msg={s['message_id']:>6}  from={(s['from_email'] or '(?)')[:30]:<30}  subj={s['subject']}")
        if len(skipped_operational) > 15:
            print(f"    ... and {len(skipped_operational) - 15} more")
        print()

    if kept:
        print(f"  kept emails (first 15):")
        for k in kept[:15]:
            m = k["message"]
            print(f"    - msg={m.get('id'):>6}  chunks={len(k['chunks']):>2}  plain_chars={k['plain_len']:>5}  "
                  f"subj={k['subject'][:60]}")
        if len(kept) > 15:
            print(f"    ... and {len(kept) - 15} more")
        print()

    # Write run record
    run_record = {
        "run_id": run_id,
        "pipeline": SOURCE_PIPELINE,
        "mode": mode,
        "ingest_timestamp_utc": ingest_ts,
        "library": library,
        "date_floor": date_floor,
        "limit": limit,
        "total_available_in_source": total,
        "messages_fetched": classify_calls,
        "messages_kept": len(kept),
        "skipped_operational_count": len(skipped_operational),
        "skipped_other_count": len(skipped_other),
        "total_chunks_planned": total_chunks_planned,
        "estimated_embed_tokens": est_tokens,
        "estimated_embed_cost_usd": round(est_embed_cost, 6),
        "classifier_cost_usd": round(classify_cost, 6),
        "skipped_operational": skipped_operational,
        "skipped_other": skipped_other,
        "kept_preview": [
            {
                "message_id": str(k["message"].get("id", "")),
                "subject": k["subject"][:100],
                "chunks": len(k["chunks"]),
                "plain_chars": k["plain_len"],
                "content_hash": k["content_hash"],
                "cdate": k["message"].get("cdate"),
            } for k in kept
        ],
    }
    ingest_runs_dir = Path.cwd() / "data" / "ingest_runs"
    ingest_runs_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if commit else ".dry_run"
    record_path = ingest_runs_dir / f"{run_id}{suffix}.json"
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(run_record, f, indent=2)
    print(f"  run record: {record_path}")

    if not commit:
        print("\n  [DRY-RUN] No Chroma writes. Re-run with --commit to perform.")
        return 0

    if not kept:
        print("\n  (no kept messages to commit)")
        return 0

    # Build chunks for upsert
    import chromadb
    chroma_client = chromadb.PersistentClient(path=str(chroma_path))
    ef = _get_embedding_function()
    dst = chroma_client.get_or_create_collection(name=library, embedding_function=ef)

    # Stage-2 dedup against target
    all_upserts = []
    dup_skips = []
    for k in kept:
        fid = str(k["message"].get("id", ""))
        existing = _check_dedup(dst, content_hash=k["content_hash"], current_file_id=fid)
        if existing:
            dup_skips.append({"ac_message_id": fid, "existing_file_id": existing,
                               "subject": k["subject"][:60]})
            continue
        for chunk in k["chunks"]:
            meta = build_ac_metadata(
                chunk=chunk, message=k["message"], library=library,
                run_id=run_id, ingest_ts=ingest_ts,
                content_hash=k["content_hash"],
                account_host=client.host,
            )
            cid = build_ac_chunk_id(client.host, fid, chunk["chunk_index"])
            all_upserts.append({
                "id": cid, "text": chunk["text"], "metadata": meta,
            })

    if dup_skips:
        print(f"  stage-2 dedup skips: {len(dup_skips)}")
        for d in dup_skips[:5]:
            print(f"    - ac_message_id={d['ac_message_id']} matches {d['existing_file_id']}  subj={d['subject']}")

    if not all_upserts:
        print("  (nothing to upsert after dedup)")
        return 0

    print(f"\n  upserting {len(all_upserts)} chunks into {library}...")
    ids = [u["id"] for u in all_upserts]
    documents = [u["text"] for u in all_upserts]
    metadatas = [u["metadata"] for u in all_upserts]
    dst.upsert(ids=ids, documents=documents, metadatas=metadatas)
    print(f"  upsert complete. {library} now has {dst.count()} chunks.")

    # Audit log append
    audit_path = Path.cwd() / "data" / "audit.jsonl"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_entry = {
        "ts": ingest_ts, "event": "ac_email_loader_commit",
        "run_id": run_id, "library": library,
        "chunks_written": len(all_upserts),
        "messages_kept": len(kept),
        "skipped_operational": len(skipped_operational),
        "estimated_embed_cost_usd": round(est_embed_cost, 6),
        "classifier_cost_usd": round(classify_cost, 6),
    }
    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(audit_entry) + "\n")
    print(f"  audit entry appended to {audit_path}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--library", required=True, help="Target Chroma collection name")
    parser.add_argument("--limit", type=int, default=None, help="Max messages to process")
    parser.add_argument("--since", default=DATE_FLOOR,
                        help=f"cdate floor for AC message filter (default: {DATE_FLOOR})")
    parser.add_argument("--commit", action="store_true", help="Perform writes. Default is dry-run.")
    args = parser.parse_args()
    try:
        return run(args)
    except KeyboardInterrupt:
        print("\ninterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
