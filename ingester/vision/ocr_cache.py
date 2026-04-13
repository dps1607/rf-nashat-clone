"""
SHA-256 keyed on-disk cache for Gemini image OCR results.

Key: sha256 of the image BYTES (not the URL — Drive HTML export URLs are
signed and expire, but bytes are stable).

Value: full OCR result including prompt_version, token counts, decorative
flag, and timestamps. Bumping prompt_version in GeminiVisionClient
automatically invalidates prior entries without any cache-clear step.

Cache location: data/image_ocr_cache/{sha256}.json (gitignored).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class OcrResult:
    sha256: str
    model: str
    prompt_version: str
    mime_type: str
    byte_size: int
    ocr_text: str
    is_decorative: bool
    failed: bool
    failure_reason: str
    vision_input_tokens: int
    vision_output_tokens: int
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "OcrResult":
        return cls(**d)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class OcrCache:
    """Filesystem-backed cache. One JSON file per SHA."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._hits = 0
        self._misses = 0

    def _path_for(self, sha: str) -> Path:
        return self.cache_dir / f"{sha}.json"

    def get(self, sha: str, prompt_version: str, model: str) -> Optional[OcrResult]:
        """Return cached OcrResult if SHA, model, and prompt_version all match."""
        p = self._path_for(sha)
        if not p.exists():
            self._misses += 1
            return None
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
        except (json.JSONDecodeError, OSError):
            self._misses += 1
            return None
        if d.get("prompt_version") != prompt_version or d.get("model") != model:
            # Stale entry — model or prompt changed. Treat as miss;
            # a successful put() will overwrite it.
            self._misses += 1
            return None
        self._hits += 1
        return OcrResult.from_dict(d)

    def put(self, result: OcrResult) -> None:
        p = self._path_for(result.sha256)
        # Write atomically-ish: to a tmp file then rename.
        tmp = p.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        tmp.replace(p)

    @property
    def stats(self) -> dict:
        return {"hits": self._hits, "misses": self._misses}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
