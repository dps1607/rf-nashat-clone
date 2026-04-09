"""
Audit log for the admin UI.

Writes one JSON object per line to AUDIT_LOG_PATH. Events record who did
what, when, and from where — enough for a "reasonable measures" trade-secret
protection story, and enough to reconstruct a timeline if something ever
goes wrong.

Never logs passwords, API keys, tokens, session cookies, JWT contents,
or bcrypt hashes. Only logs event metadata.

Event types currently emitted:
    login_success      — user authenticated (Cloudflare or local)
    login_failure      — failed auth attempt (local mode only)
    logout             — explicit logout
    access_denied      — authenticated user not in admin_users.json
    yaml_save          — agent config written to disk
    yaml_save_invalid  — save rejected by Pydantic validation
    test_query         — inline test panel query sent to RAG server
    admin_user_added   — new user written to admin_users.json
    admin_user_removed — user removed from admin_users.json
    startup            — app process booted (records mode + version info)
"""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import has_request_context, request

_REPO_ROOT = Path(__file__).resolve().parent.parent

# On Railway, set AUDIT_LOG_PATH=/data/audit.jsonl so the log lives on the
# persistent volume and survives redeploys. Locally, default to a file in
# the repo root (gitignored).
AUDIT_LOG_PATH = Path(os.environ.get(
    "AUDIT_LOG_PATH",
    str(_REPO_ROOT / "audit.jsonl"),
))


def _client_ip() -> str:
    """Best-effort client IP. Trusts X-Forwarded-For because we run behind
    Cloudflare + Railway's proxy. ProxyFix in app.py normalizes this."""
    if not has_request_context():
        return "-"
    # Flask's request.remote_addr already reflects ProxyFix-normalized value
    # when ProxyFix is installed.
    return request.remote_addr or "-"


def _user_agent() -> str:
    if not has_request_context():
        return "-"
    ua = request.headers.get("User-Agent", "-")
    # Truncate pathological user agents
    return ua[:200]


def log(event: str, user: str | None = None, details: dict[str, Any] | None = None) -> None:
    """Append one structured event to the audit log.

    Failures to write the audit log are logged to stderr but do NOT raise —
    we never want an audit-log problem to break the actual request flow.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event": event,
        "user": user or "-",
        "ip": _client_ip(),
        "user_agent": _user_agent(),
        "details": details or {},
    }
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Open in append mode; each write is a single JSON object + newline.
        # Append on POSIX is atomic for writes smaller than PIPE_BUF (~4KB),
        # which our entries always are.
        with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        # Restrict perms to owner read/write on first write
        try:
            os.chmod(AUDIT_LOG_PATH, 0o600)
        except OSError:
            pass
    except Exception as e:
        print(f"[audit] WARNING: failed to write audit log: {e}", file=sys.stderr)


def tail(n: int = 100) -> list[dict]:
    """Read the last N audit events. Returns oldest-first.

    Used for an eventual admin-UI log viewer. Not called from any route yet.
    """
    if not AUDIT_LOG_PATH.exists():
        return []
    try:
        with open(AUDIT_LOG_PATH, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []
    out = []
    for line in lines[-n:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
