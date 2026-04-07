"""
Admin Authentication
====================

Tiny user system for the admin UI. NOT for end users — see Phase 4 for that.

Stores users in a flat JSON file at config/admin_users.json:

    {
      "username": {
        "password_hash": "$2b$12$...",
        "role": "admin",
        "created": "2026-04-07T10:00:00"
      }
    }

The file is gitignored. Never commit it.

Use the CLI helper to add users:
    python3 -m admin_ui.add_user <username>
"""
from __future__ import annotations
import json
import os
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Optional

import bcrypt
from flask import session, redirect, url_for, request

_REPO_ROOT = Path(__file__).resolve().parent.parent
# On Railway, set ADMIN_USERS_PATH=/data/admin_users.json so the file lives
# on the persistent volume. Falls back to the in-repo location for local dev.
USERS_FILE = Path(os.environ.get(
    "ADMIN_USERS_PATH",
    str(_REPO_ROOT / "config" / "admin_users.json")
))


def _load_users() -> dict:
    if not USERS_FILE.exists():
        return {}
    try:
        with open(USERS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_users(users: dict) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)
    # Owner read/write only
    os.chmod(USERS_FILE, 0o600)


def hash_password(plaintext: str) -> str:
    """Hash a password with bcrypt. Returns a UTF-8 string for JSON storage."""
    if not plaintext:
        raise ValueError("password cannot be empty")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plaintext.encode("utf-8"), salt).decode("utf-8")


def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def add_user(username: str, password: str, role: str = "admin") -> None:
    """Create or replace a user in the admin file."""
    if not username or not username.isidentifier():
        raise ValueError(f"invalid username: {username!r} (use letters, digits, underscore)")
    users = _load_users()
    users[username] = {
        "password_hash": hash_password(password),
        "role": role,
        "created": datetime.utcnow().isoformat(timespec="seconds"),
    }
    _save_users(users)


def remove_user(username: str) -> bool:
    users = _load_users()
    if username not in users:
        return False
    del users[username]
    _save_users(users)
    return True


def list_users() -> list[dict]:
    users = _load_users()
    return [
        {"username": name, "role": data.get("role", "admin"),
         "created": data.get("created", "?")}
        for name, data in users.items()
    ]


# Pre-computed dummy hash for constant-time comparison when username is unknown.
# This prevents timing-based username enumeration. Computed once at import.
_DUMMY_HASH = bcrypt.hashpw(b"unused", bcrypt.gensalt(rounds=12))


def authenticate(username: str, password: str) -> Optional[dict]:
    """Return user dict on success, None on failure."""
    users = _load_users()
    user = users.get(username)
    if user is None:
        # Run a real bcrypt compare against a dummy hash to keep timing constant
        bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH)
        return None
    if verify_password(password, user["password_hash"]):
        return {"username": username, "role": user.get("role", "admin")}
    return None


# -----------------------------------------------------------------------------
# Flask session helpers
# -----------------------------------------------------------------------------

def login_user(user: dict) -> None:
    session.clear()
    session["username"] = user["username"]
    session["role"] = user.get("role", "admin")
    session.permanent = True


def logout_user() -> None:
    session.clear()


def current_user() -> Optional[dict]:
    if "username" not in session:
        return None
    return {"username": session["username"], "role": session.get("role", "admin")}


def login_required(view_func):
    """Decorator: redirect to /login if no active session."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped
