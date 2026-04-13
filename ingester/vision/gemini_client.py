"""
Gemini 2.5 Flash vision client via Vertex AI (google-genai SDK).

Auth: uses GOOGLE_APPLICATION_CREDENTIALS env var (same service account
as DriveClient) via Application Default Credentials. Project and region
come from ingester.config.

Cost model (Vertex AI, gemini-2.5-flash pricing as of 2026-04):
  - Text input:  $0.075 / 1M tokens
  - Image input: ~258 tokens per image (fixed, per Gemini spec)
  - Output:      $0.30 / 1M tokens

The client maintains a running ledger of spend across a session so the
loader can print per-file and per-run totals.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from ingester import config as ingester_config
from ingester.vision.ocr_cache import OcrResult, OcrCache, sha256_hex, now_utc_iso


# Prompt version. Bump when the prompt text below changes — the cache
# will automatically invalidate prior entries.
PROMPT_VERSION = "v1"

OCR_PROMPT = """You are extracting text and visual information from a fertility-medicine reference document.

Describe what this image shows. Handle each category below:

1. If the image contains a PRODUCT (supplement bottle, package, label, box):
   transcribe all visible text verbatim — brand name, product name, dose,
   serving size, ingredient list, claims. Do not summarize.

2. If the image is an INFOGRAPHIC, chart, diagram, or designed visual
   (including Canva-style content): transcribe all visible text preserving
   logical reading order and hierarchy. Capture headings, bullet points,
   labels, numeric data, and any text associated with icons or illustrations.
   Do not summarize — transcribe.

3. If the image is a MEDICAL/CLINICAL figure (lab reference range chart,
   anatomy diagram, protocol flowchart): transcribe labels, values, and
   any legend or caption text.

4. If the image is PURELY STRUCTURAL (horizontal divider, solid color
   block, single decorative icon with no text, ruler line, spacer):
   reply with exactly: DECORATIVE

Return plain text only. No commentary, no speculation about content
not visible. Preserve the document's own terminology."""


# Pricing constants (USD per 1M tokens, Vertex AI gemini-2.5-flash).
# If Google updates pricing, update here.
VISION_INPUT_PRICE_PER_1M = 0.075
VISION_OUTPUT_PRICE_PER_1M = 0.30


@dataclass
class VisionLedger:
    images_seen: int = 0
    images_ocr_called: int = 0
    images_cache_hit: int = 0
    images_decorative: int = 0
    images_failed: int = 0
    vision_input_tokens: int = 0
    vision_output_tokens: int = 0
    errors: list = field(default_factory=list)

    @property
    def vision_cost_usd(self) -> float:
        input_cost = self.vision_input_tokens / 1_000_000 * VISION_INPUT_PRICE_PER_1M
        output_cost = self.vision_output_tokens / 1_000_000 * VISION_OUTPUT_PRICE_PER_1M
        return input_cost + output_cost

    def to_dict(self) -> dict:
        return {
            "images_seen": self.images_seen,
            "images_ocr_called": self.images_ocr_called,
            "images_cache_hit": self.images_cache_hit,
            "images_decorative": self.images_decorative,
            "images_failed": self.images_failed,
            "vision_input_tokens": self.vision_input_tokens,
            "vision_output_tokens": self.vision_output_tokens,
            "vision_cost_usd": round(self.vision_cost_usd, 6),
            "errors": self.errors,
        }


class GeminiVisionClient:
    """Wraps google-genai Vertex AI client for single-image OCR calls."""

    def __init__(self, cache: OcrCache, model: Optional[str] = None):
        self.model = model or ingester_config.VISION_MODEL  # "gemini-2.5-flash"
        self.cache = cache
        self.ledger = VisionLedger()
        self._client = None  # lazy-init to avoid import cost when v2 isn't used

    def _ensure_client(self):
        if self._client is not None:
            return
        # Import here so importing this module doesn't require google-genai
        # to be installed (useful for v1 which never touches vision).
        from google import genai
        self._client = genai.Client(
            vertexai=True,
            project=ingester_config.GCP_PROJECT_ID,
            location=ingester_config.VERTEX_AI_REGION,
        )

    def ocr_image(
        self, image_bytes: bytes, mime_type: str, use_cache: bool = True
    ) -> OcrResult:
        """
        OCR a single image. Returns OcrResult. Checks cache first if
        use_cache=True. On Gemini error, returns an OcrResult with
        failed=True and a reason — does NOT raise (so a single bad
        image doesn't abort the whole file).
        """
        self.ledger.images_seen += 1
        sha = sha256_hex(image_bytes)

        if use_cache:
            cached = self.cache.get(sha, PROMPT_VERSION, self.model)
            if cached is not None:
                self.ledger.images_cache_hit += 1
                if cached.is_decorative:
                    self.ledger.images_decorative += 1
                elif cached.failed:
                    self.ledger.images_failed += 1
                return cached

        # Cache miss — call Gemini
        try:
            self._ensure_client()
            from google.genai import types
            part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            response = self._client.models.generate_content(
                model=self.model,
                contents=[OCR_PROMPT, part],
            )
            text = (response.text or "").strip()

            # Token accounting
            usage = getattr(response, "usage_metadata", None)
            input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
            output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
            self.ledger.vision_input_tokens += input_tokens
            self.ledger.vision_output_tokens += output_tokens
            self.ledger.images_ocr_called += 1

            is_decorative = text.upper().strip() == "DECORATIVE"
            if is_decorative:
                self.ledger.images_decorative += 1

            result = OcrResult(
                sha256=sha,
                model=self.model,
                prompt_version=PROMPT_VERSION,
                mime_type=mime_type,
                byte_size=len(image_bytes),
                ocr_text="" if is_decorative else text,
                is_decorative=is_decorative,
                failed=False,
                failure_reason="",
                vision_input_tokens=input_tokens,
                vision_output_tokens=output_tokens,
                created_at=now_utc_iso(),
            )
            if use_cache:
                self.cache.put(result)
            return result

        except Exception as e:  # noqa: BLE001 — intentionally broad for one-bad-image resilience
            self.ledger.images_failed += 1
            reason = f"{type(e).__name__}: {e}"
            self.ledger.errors.append({"sha256": sha, "reason": reason})
            result = OcrResult(
                sha256=sha,
                model=self.model,
                prompt_version=PROMPT_VERSION,
                mime_type=mime_type,
                byte_size=len(image_bytes),
                ocr_text="",
                is_decorative=False,
                failed=True,
                failure_reason=reason,
                vision_input_tokens=0,
                vision_output_tokens=0,
                created_at=now_utc_iso(),
            )
            # Do NOT cache failures — transient errors (rate limits,
            # 5xx) should be retried on next run.
            return result
