"""Cheap LLM content classifier for ingestion pipelines.

Single-purpose helper. Given a piece of source content (subject + body preview),
decides whether it's marketing/educational (ingest) or operational/transactional
(skip). Used by ac_email_loader, future ghl_email_loader, future ig_post_loader,
incremental blog_loader, etc.

Design principles:
  - One function, one decision: is_operational(subject, body_preview) -> bool
  - Uses Haiku (cheap; ~$0.0003 per classification) for binary filtering
  - Short prompt, short response — classifier is not meant to nuance
  - Caches verdicts by content hash → same content, same verdict, $0 on re-runs
  - Falls safe: if the classifier errors, default to "not operational"
    (let content through, so false-negative on infra failures is recoverable
    by re-running after a fix)

Cache location: data/classifier_cache.jsonl (append-only, one JSON object per line).
Grep-auditable, rebuildable, survives session restart.

Usage:
    from ingester.classify import is_operational
    if is_operational(subject="Your appointment tomorrow", body="Reminder..."):
        skip_this_item()
    else:
        ingest_this_item()
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# override=True — see s28-extended HANDOVER on shell-env-conflict diagnosis
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

log = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "classifier_cache.jsonl"
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

# Haiku 4.5 — current cheapest Claude model; ~$1/$5 per M tokens.
# For a binary classification prompt (~800 in, ~50 out), ~$0.0008 per call.
MODEL = "claude-haiku-4-5"

# Max body chars we send to classifier (keep input token cost predictable).
# 500 chars ≈ 125 tokens; enough for classifier to read the first few sentences.
MAX_BODY_CHARS = 500

CLASSIFY_PROMPT_TEMPLATE = """\
You are classifying a piece of Reimagined Fertility content.

The company publishes EDUCATIONAL and MARKETING content about fertility, nutrition, \
hormones, coaching — material that teaches readers or sells programs. This content \
should be INGESTED into a RAG system for client-facing agents to retrieve.

The company also sends OPERATIONAL and TRANSACTIONAL content: appointment reminders, \
order receipts, program onboarding logistics (e.g., "your FKSP kickoff call is tomorrow"), \
password resets, billing notices, unsubscribe confirmations, welcome-to-the-program \
delivery emails. This content should NOT be ingested — it would pollute retrieval \
with per-client, per-event noise.

Content to classify:
SUBJECT: {subject}
BODY PREVIEW: {body_preview}

Respond with ONLY one word, no explanation:
  MARKETING — if the content teaches or sells
  OPERATIONAL — if the content is transactional, delivery, or administrative
  UNCLEAR — only if the content genuinely could go either way and you cannot tell

One word. No punctuation. No explanation."""


@dataclass
class ClassifyResult:
    verdict: str            # "MARKETING" | "OPERATIONAL" | "UNCLEAR" | "ERROR"
    is_operational: bool    # True if verdict == "OPERATIONAL"
    cached: bool
    model: str
    cost_usd: float = 0.0
    error: str = ""


def _make_cache_key(subject: str, body_preview: str) -> str:
    """Stable cache key over (model, prompt_version, subject, body_preview)."""
    content = f"{MODEL}|v1|{subject or ''}|{body_preview or ''}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _load_cache() -> dict:
    """Load cache into a dict. Called on first use, then cached in-process."""
    cache: dict = {}
    if not CACHE_PATH.exists():
        return cache
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    cache[rec["key"]] = rec
                except (json.JSONDecodeError, KeyError):
                    continue
    except Exception as e:  # noqa: BLE001
        log.warning(f"classifier cache read failed: {e}; starting empty")
    return cache


_CACHE: Optional[dict] = None


def _cache() -> dict:
    global _CACHE
    if _CACHE is None:
        _CACHE = _load_cache()
    return _CACHE


def _append_cache(record: dict) -> None:
    """Append one classification to disk + in-memory cache."""
    _cache()[record["key"]] = record
    try:
        with open(CACHE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:  # noqa: BLE001
        log.warning(f"classifier cache write failed: {e}")


def classify(subject: str, body_preview: str) -> ClassifyResult:
    """Return the classification verdict for one piece of content.

    Uses the on-disk cache if available; otherwise calls Haiku.

    Body preview is truncated to MAX_BODY_CHARS before sending.
    """
    subject = (subject or "").strip()
    body = (body_preview or "").strip()
    if len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS] + "..."

    key = _make_cache_key(subject, body)
    cache = _cache()
    if key in cache:
        rec = cache[key]
        verdict = rec.get("verdict", "UNCLEAR")
        return ClassifyResult(
            verdict=verdict,
            is_operational=(verdict == "OPERATIONAL"),
            cached=True,
            model=rec.get("model", MODEL),
            cost_usd=0.0,
        )

    # Cache miss — call Haiku
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # Fall safe: no classifier available, return UNCLEAR (ingester treats
        # non-OPERATIONAL as ingestable, so content passes through uncensored)
        return ClassifyResult(
            verdict="ERROR",
            is_operational=False,
            cached=False,
            model=MODEL,
            error="ANTHROPIC_API_KEY not set",
        )

    import anthropic  # lazy import
    client = anthropic.Anthropic(api_key=api_key)
    prompt = CLASSIFY_PROMPT_TEMPLATE.format(subject=subject or "(no subject)", body_preview=body or "(no body)")

    start = time.perf_counter()
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=8,  # 1 word response, hard cap
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:  # noqa: BLE001
        elapsed = time.perf_counter() - start
        log.warning(f"classifier Haiku call failed after {elapsed:.1f}s: {e}")
        return ClassifyResult(
            verdict="ERROR", is_operational=False, cached=False,
            model=MODEL, error=str(e)[:200],
        )

    # Parse response
    raw = response.content[0].text.strip().upper() if response.content else ""
    if "OPERATIONAL" in raw:
        verdict = "OPERATIONAL"
    elif "MARKETING" in raw:
        verdict = "MARKETING"
    elif "UNCLEAR" in raw:
        verdict = "UNCLEAR"
    else:
        # Haiku returned something unexpected — safe fallback
        verdict = "UNCLEAR"

    # Rough cost: input_tokens + output_tokens from usage
    usage = getattr(response, "usage", None)
    in_tokens = getattr(usage, "input_tokens", 0) if usage else 0
    out_tokens = getattr(usage, "output_tokens", 0) if usage else 0
    # Haiku 4.5 pricing: $1.00/M input, $5.00/M output (as of 2026)
    cost = (in_tokens / 1_000_000) * 1.00 + (out_tokens / 1_000_000) * 5.00

    record = {
        "key": key,
        "verdict": verdict,
        "model": MODEL,
        "subject_preview": subject[:80],
        "body_preview_length": len(body),
        "raw_response": raw[:40],
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "cost_usd": round(cost, 6),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _append_cache(record)

    return ClassifyResult(
        verdict=verdict,
        is_operational=(verdict == "OPERATIONAL"),
        cached=False,
        model=MODEL,
        cost_usd=round(cost, 6),
    )


def is_operational(subject: str, body_preview: str) -> bool:
    """Convenience wrapper: True if content should be skipped as operational."""
    result = classify(subject, body_preview)
    return result.is_operational
