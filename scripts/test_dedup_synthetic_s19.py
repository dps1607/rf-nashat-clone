"""
test_dedup_synthetic_s19.py — verify BACKLOG #23 stage-2 dedup logic.

Synthetic test, no Chroma, no Drive. Mocks the collection.get(where=...)
interface and exercises _compute_content_hash + _check_dedup.

Closes BACKLOG #23 stage-2. Stage 1 (pre-extraction md5 check) is deferred
to a future session — see HANDOVER session 19 for rationale.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ingester.loaders.drive_loader_v3 import _compute_content_hash, _check_dedup


class _MockCollection:
    """Mocks chromadb collection.get(where={...}) for dedup tests."""
    def __init__(self, fake_chunks: list[dict]):
        self._fake = fake_chunks

    def get(self, *, where: dict, limit: int = 10) -> dict:
        # Return chunks whose metadata matches all where-clause keys.
        matched = []
        for chunk in self._fake:
            meta = chunk.get("metadata", {})
            if all(meta.get(k) == v for k, v in where.items()):
                matched.append(meta)
                if len(matched) >= limit:
                    break
        return {"metadatas": matched, "ids": [], "documents": []}


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

def test_content_hash_deterministic() -> None:
    h1 = _compute_content_hash("hello world")
    h2 = _compute_content_hash("hello world")
    assert h1 == h2, "same input should produce same hash"
    assert len(h1) == 64, f"sha256 hex digest should be 64 chars, got {len(h1)}"
    print("  [PASS] content_hash deterministic and 64 chars")


def test_content_hash_sensitive_to_whitespace() -> None:
    h1 = _compute_content_hash("hello world")
    h2 = _compute_content_hash("hello  world")
    h3 = _compute_content_hash("hello world ")
    assert h1 != h2, "extra space should change hash (M-23-D.1 strict mode)"
    assert h1 != h3, "trailing space should change hash"
    print("  [PASS] content_hash strict-byte (whitespace-sensitive)")


def test_content_hash_sensitive_to_case() -> None:
    h1 = _compute_content_hash("Hello World")
    h2 = _compute_content_hash("hello world")
    assert h1 != h2, "case difference should change hash (M-23-D.1)"
    print("  [PASS] content_hash strict-byte (case-sensitive)")


def test_content_hash_empty_string_is_valid() -> None:
    h = _compute_content_hash("")
    # Known SHA256 of empty string
    assert h == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    print("  [PASS] content_hash on empty string is the known empty-SHA256")


def test_dedup_returns_none_on_empty_collection() -> None:
    coll = _MockCollection(fake_chunks=[])
    result = _check_dedup(coll, content_hash="abc123", current_file_id="file_X")
    assert result is None, f"empty collection should return None, got {result!r}"
    print("  [PASS] dedup returns None on empty collection")


def test_dedup_returns_existing_file_id_on_content_hash_match() -> None:
    coll = _MockCollection(fake_chunks=[
        {"metadata": {"content_hash": "matchhash", "source_file_id": "old_file"}},
    ])
    result = _check_dedup(coll, content_hash="matchhash", current_file_id="new_file")
    assert result == "old_file", f"expected 'old_file', got {result!r}"
    print("  [PASS] dedup returns existing file_id on content_hash match")


def test_dedup_returns_none_on_self_match() -> None:
    """Same file_id re-ingest is allowed (upsert behavior). Dedup must NOT fire."""
    coll = _MockCollection(fake_chunks=[
        {"metadata": {"content_hash": "samehash", "source_file_id": "same_file"}},
    ])
    result = _check_dedup(coll, content_hash="samehash", current_file_id="same_file")
    assert result is None, f"self-match should return None, got {result!r}"
    print("  [PASS] dedup returns None on same-file_id self-match (re-ingest allowed)")


def test_dedup_returns_none_on_empty_content_hash() -> None:
    """Defensive: don't query Chroma with empty hash."""
    coll = _MockCollection(fake_chunks=[
        {"metadata": {"content_hash": "", "source_file_id": "old_file"}},
    ])
    result = _check_dedup(coll, content_hash="", current_file_id="new_file")
    assert result is None, "empty content_hash should short-circuit"
    print("  [PASS] dedup short-circuits on empty content_hash")


def test_dedup_skips_other_collisions_finds_real_match() -> None:
    """Multiple chunks in result; one is self-match, one is real dup. Real dup wins."""
    coll = _MockCollection(fake_chunks=[
        {"metadata": {"content_hash": "h1", "source_file_id": "current"}},
        {"metadata": {"content_hash": "h1", "source_file_id": "real_dup"}},
    ])
    result = _check_dedup(coll, content_hash="h1", current_file_id="current")
    assert result == "real_dup", f"expected 'real_dup', got {result!r}"
    print("  [PASS] dedup finds real dup even when self-match also present")


def test_dedup_handles_collection_get_exception() -> None:
    """Defensive: if collection.get raises (e.g., field doesn't exist), return None."""
    class _BrokenCollection:
        def get(self, *, where, limit=10):
            raise RuntimeError("simulated chroma failure")
    result = _check_dedup(_BrokenCollection(), content_hash="any", current_file_id="any")
    assert result is None, "broken collection should return None, not raise"
    print("  [PASS] dedup handles collection.get exception gracefully")


def main() -> None:
    print("test_dedup_synthetic_s19.py")
    print("=" * 60)
    tests = [
        test_content_hash_deterministic,
        test_content_hash_sensitive_to_whitespace,
        test_content_hash_sensitive_to_case,
        test_content_hash_empty_string_is_valid,
        test_dedup_returns_none_on_empty_collection,
        test_dedup_returns_existing_file_id_on_content_hash_match,
        test_dedup_returns_none_on_self_match,
        test_dedup_returns_none_on_empty_content_hash,
        test_dedup_skips_other_collisions_finds_real_match,
        test_dedup_handles_collection_get_exception,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"  [FAIL] {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print("=" * 60)
    print(f"  {len(tests) - failed}/{len(tests)} passing, {failed} failing")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
