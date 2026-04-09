"""
Admin Authentication — Phase 3.5
================================

Two modes, selected by the CLOUDFLARE_ACCESS_ENABLED environment variable:

    CLOUDFLARE_ACCESS_ENABLED=true   → Cloudflare Access mode (production)
    CLOUDFLARE_ACCESS_ENABLED=false  → Local bcrypt mode (dev only)
    (unset)                          → Local bcrypt mode (dev only)

CLOUDFLARE ACCESS MODE
----------------------
Cloudflare Access sits in front of this app, handles sign-in (Google OAuth,
one-time PIN, etc.), and injects two headers on every request that makes it
past its access policy:

    Cf-Access-Authenticated-User-Email — the signed-in user's email
    Cf-Access-Jwt-Assertion            — a JWT signed by Cloudflare proving
                                         the request came from them

We DO NOT trust the email header by itself — anyone on the internet could
set that header with curl if they ever found the raw Railway URL. Instead,
we verify the JWT on every request:

    1. Fetch Cloudflare Access's public keys (JWKS) from the team domain.
    2. Verify the JWT signature using those keys.
    3. Verify the "aud" claim matches our Cloudflare Access application.
    4. Verify the "iss" claim matches our team domain.
    5. Extract the verified email from the JWT "email" claim.
    6. Look up that email in admin_users.json for authorization.

If any of those steps fail, the request is rejected with 401/403.

admin_users.json in Cloudflare mode:

    {
      "dan@reimagined-health.com": {
        "name": "Dan Smith",
        "role": "admin",
        "created": "2026-04-08T17:00:00+00:00"
      },
      "znahealth@gmail.com": {
        "name": "Dr. Nashat Latib",
        "role": "admin",
        "created": "2026-04-08T17:00:00+00:00"
      }
    }

LOCAL BCRYPT MODE (dev only)
----------------------------
Original behavior preserved for local development. Username + bcrypt password
stored in admin_users.json with the older schema. Never use this in production.
"""
from __future__ import annotations
import json
import os
import sys
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Optional

import jwt
import requests
from flask import session, redirect, url_for, request, abort

from admin_ui import audit

_REPO_ROOT = Path(__file__).resolve().parent.parent

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

CLOUDFLARE_ACCESS_ENABLED = os.environ.get(
    "CLOUDFLARE_ACCESS_ENABLED", "false"
).lower() in ("true", "1", "yes", "on")

CLOUDFLARE_ACCESS_AUD = os.environ.get("CLOUDFLARE_ACCESS_AUD", "").strip()
CLOUDFLARE_ACCESS_TEAM_DOMAIN = os.environ.get(
    "CLOUDFLARE_ACCESS_TEAM_DOMAIN", ""
).strip().rstrip("/")

USERS_FILE = Path(os.environ.get(
    "ADMIN_USERS_PATH",
    str(_REPO_ROOT / "config" / "admin_users.json")
))

if CLOUDFLARE_ACCESS_ENABLED:
    if not CLOUDFLARE_ACCESS_AUD or not CLOUDFLARE_ACCESS_TEAM_DOMAIN:
        print(
            "ERROR: CLOUDFLARE_ACCESS_ENABLED=true but "
            "CLOUDFLARE_ACCESS_AUD and CLOUDFLARE_ACCESS_TEAM_DOMAIN must also be set",
            file=sys.stderr,
        )
        # We intentionally do NOT raise here — we want the app to boot so the
        # operator can see the error via the admin panel's own failure page.
        # The login_required decorator will reject every request until this
        # is fixed.


# -----------------------------------------------------------------------------
# User file I/O — supports both schemas (email-keyed for Cloudflare mode,
# username-keyed for local dev mode). The file format auto-detects based on
# what keys look like.
# -----------------------------------------------------------------------------

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
    os.chmod(USERS_FILE, 0o600)


def list_users() -> list[dict]:
    """List all users in whatever schema the file is using."""
    users = _load_users()
    out = []
    for key, data in users.items():
        out.append({
            "key": key,
            "name": data.get("name") or data.get("username") or key,
            "role": data.get("role", "admin"),
            "created": data.get("created", "?"),
        })
    return out


# -----------------------------------------------------------------------------
# Cloudflare mode: email-keyed user management (no passwords)
# -----------------------------------------------------------------------------

def add_email_user(email: str, name: str, role: str = "admin") -> None:
    """Create or replace an email-keyed user (Cloudflare Access mode)."""
    email = email.strip().lower()
    if "@" not in email:
        raise ValueError(f"invalid email: {email!r}")
    users = _load_users()
    users[email] = {
        "name": name.strip() or email.split("@")[0],
        "role": role,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _save_users(users)
    audit.log("admin_user_added", user="-system-", details={"email": email, "role": role})


def remove_email_user(email: str) -> bool:
    email = email.strip().lower()
    users = _load_users()
    if email not in users:
        return False
    del users[email]
    _save_users(users)
    audit.log("admin_user_removed", user="-system-", details={"email": email})
    return True


def lookup_email(email: str) -> Optional[dict]:
    """Find an email in admin_users.json. Returns the user record or None."""
    if not email:
        return None
    users = _load_users()
    record = users.get(email.strip().lower())
    if record is None:
        return None
    return {
        "email": email.strip().lower(),
        "name": record.get("name", email),
        "role": record.get("role", "admin"),
    }


# -----------------------------------------------------------------------------
# Local bcrypt mode: username-keyed password auth (dev only, preserved)
# -----------------------------------------------------------------------------
#
# bcrypt is imported lazily inside the functions that use it. This is
# deliberate: scripts that `from admin_ui.auth import ...` from a non-venv
# python (e.g. tooling, maintenance scripts) should not crash at import time
# just because bcrypt isn't installed system-wide. Cloudflare-mode production
# deployments never touch these functions, so they never need bcrypt at all.

def _bcrypt():
    import bcrypt  # noqa: WPS433 — deliberate lazy import, see block comment above
    return bcrypt


def hash_password(plaintext: str) -> str:
    if not plaintext:
        raise ValueError("password cannot be empty")
    bcrypt = _bcrypt()
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plaintext.encode("utf-8"), salt).decode("utf-8")


def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        bcrypt = _bcrypt()
        return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def add_user(username: str, password: str, role: str = "admin") -> None:
    """Create or replace a local-dev bcrypt user."""
    if not username or not username.isidentifier():
        raise ValueError(f"invalid username: {username!r}")
    users = _load_users()
    users[username] = {
        "password_hash": hash_password(password),
        "username": username,
        "role": role,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _save_users(users)


def remove_user(username: str) -> bool:
    users = _load_users()
    if username not in users:
        return False
    del users[username]
    _save_users(users)
    return True


# Cached dummy hash for constant-time comparison on unknown username.
# Computed lazily on first use so importing this module doesn't require
# bcrypt to be installed (see _bcrypt() block comment above).
_DUMMY_HASH_CACHE: Optional[bytes] = None


def _dummy_hash() -> bytes:
    global _DUMMY_HASH_CACHE
    if _DUMMY_HASH_CACHE is None:
        bcrypt = _bcrypt()
        _DUMMY_HASH_CACHE = bcrypt.hashpw(b"unused", bcrypt.gensalt(rounds=12))
    return _DUMMY_HASH_CACHE


def authenticate(username: str, password: str) -> Optional[dict]:
    """LOCAL DEV ONLY: bcrypt authentication. Return user dict or None."""
    if CLOUDFLARE_ACCESS_ENABLED:
        # In Cloudflare mode, the local password flow is disabled entirely.
        return None
    users = _load_users()
    user = users.get(username)
    if user is None or "password_hash" not in user:
        bcrypt = _bcrypt()
        bcrypt.checkpw(password.encode("utf-8"), _dummy_hash())  # timing constant
        return None
    if verify_password(password, user["password_hash"]):
        return {
            "username": username,
            "email": None,
            "name": user.get("username", username),
            "role": user.get("role", "admin"),
        }
    return None


# -----------------------------------------------------------------------------
# Cloudflare Access JWT verification
# -----------------------------------------------------------------------------
#
# Cloudflare signs a JWT on every authenticated request and delivers it in the
# Cf-Access-Jwt-Assertion header. The signing keys rotate periodically and are
# published as a JWKS at:
#
#     https://<team>.cloudflareaccess.com/cdn-cgi/access/certs
#
# We fetch this once on first use, cache it in memory for an hour, and use
# it to verify every incoming JWT. PyJWT's PyJWKClient handles key rotation
# and caching for us.
#
# Docs: https://developers.cloudflare.com/cloudflare-one/identity/authorization-cookie/validating-json/

_jwks_client: Optional["jwt.PyJWKClient"] = None
_jwks_error: Optional[str] = None


def _get_jwks_client() -> Optional["jwt.PyJWKClient"]:
    """Lazy-initialize the JWKS client. Returns None if misconfigured or
    if the JWKS endpoint is unreachable."""
    global _jwks_client, _jwks_error
    if _jwks_client is not None:
        return _jwks_client
    if not CLOUDFLARE_ACCESS_TEAM_DOMAIN:
        _jwks_error = "CLOUDFLARE_ACCESS_TEAM_DOMAIN not set"
        return None
    try:
        url = f"https://{CLOUDFLARE_ACCESS_TEAM_DOMAIN}/cdn-cgi/access/certs"
        _jwks_client = jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)
        return _jwks_client
    except Exception as e:
        _jwks_error = f"failed to init JWKS client: {e}"
        print(f"[auth] {_jwks_error}", file=sys.stderr)
        return None


def verify_cloudflare_jwt(token: str) -> Optional[dict]:
    """Verify a Cloudflare Access JWT. Returns the decoded claims on success,
    None on any failure. Never raises.

    Checks performed (all MUST pass):
        - Signature validates against Cloudflare's published JWKS
        - `aud` claim contains our CLOUDFLARE_ACCESS_AUD
        - `iss` claim matches https://<team>.cloudflareaccess.com
        - Token is not expired (exp) and not used before its nbf
        - `email` claim is present
    """
    if not token:
        return None
    if not CLOUDFLARE_ACCESS_AUD or not CLOUDFLARE_ACCESS_TEAM_DOMAIN:
        return None

    client = _get_jwks_client()
    if client is None:
        return None

    expected_issuer = f"https://{CLOUDFLARE_ACCESS_TEAM_DOMAIN}"

    try:
        signing_key = client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=CLOUDFLARE_ACCESS_AUD,
            issuer=expected_issuer,
            options={"require": ["exp", "iat", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError:
        print("[auth] JWT expired", file=sys.stderr)
        return None
    except jwt.InvalidAudienceError:
        print("[auth] JWT audience mismatch — check CLOUDFLARE_ACCESS_AUD",
              file=sys.stderr)
        return None
    except jwt.InvalidIssuerError:
        print("[auth] JWT issuer mismatch — check CLOUDFLARE_ACCESS_TEAM_DOMAIN",
              file=sys.stderr)
        return None
    except jwt.InvalidTokenError as e:
        print(f"[auth] JWT invalid: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[auth] JWT verification error: {e}", file=sys.stderr)
        return None

    if "email" not in claims:
        print("[auth] JWT missing email claim", file=sys.stderr)
        return None
    return claims


# -----------------------------------------------------------------------------
# Flask session + login_required decorator
# -----------------------------------------------------------------------------

def login_user(user: dict) -> None:
    """Set the Flask session after a successful login (local dev mode)."""
    session.clear()
    session["user"] = user
    session.permanent = True


def logout_user() -> None:
    prev = current_user()
    session.clear()
    if prev:
        audit.log("logout", user=prev.get("email") or prev.get("username") or "-")


def current_user() -> Optional[dict]:
    """Return the current user. In Cloudflare mode, this reads the verified
    JWT claims from the request (NOT the Flask session — every request
    re-verifies). In local mode, reads from the Flask session."""
    if CLOUDFLARE_ACCESS_ENABLED:
        return _cloudflare_user_from_request()
    return session.get("user")


def _cloudflare_user_from_request() -> Optional[dict]:
    """In Cloudflare mode, authenticate from the JWT on every request.

    Flow:
        1. Grab Cf-Access-Jwt-Assertion header
        2. Verify it (signature, aud, iss, exp)
        3. Extract email from verified claims
        4. Look up email in admin_users.json
        5. Return user dict or None

    If the JWT is missing the user is unauthenticated. If the JWT verifies
    but the email isn't in admin_users.json, the user is forbidden (handled
    by the decorator below).
    """
    if not request:
        return None
    token = request.headers.get("Cf-Access-Jwt-Assertion")
    if not token:
        return None
    claims = verify_cloudflare_jwt(token)
    if claims is None:
        return None
    email = claims.get("email", "").strip().lower()
    if not email:
        return None
    record = lookup_email(email)
    if record is None:
        # JWT is valid but this user isn't in our allowlist.
        # Return a sentinel so the decorator can distinguish "not signed in"
        # from "signed in but not authorized".
        return {"email": email, "name": email, "role": None, "_unauthorized": True}
    return record


def login_required(view_func):
    """Decorator: require an authenticated + authorized user.

    In Cloudflare mode:
        - No JWT → 401 (Cloudflare should have bounced them already)
        - JWT verifies but email not in admin_users.json → 403 + audit log
        - JWT verifies + email authorized → proceed

    In local mode:
        - No session → redirect to /login
        - Session present → proceed
    """
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            if CLOUDFLARE_ACCESS_ENABLED:
                # Should never happen if Cloudflare Access is correctly
                # sitting in front of us. Treat it as a misconfiguration.
                abort(401, "Missing or invalid Cloudflare Access JWT")
            return redirect(url_for("login", next=request.path))
        if user.get("_unauthorized"):
            audit.log("access_denied", user=user.get("email", "-"),
                      details={"path": request.path})
            abort(403, "Your email is not authorized for the admin panel. "
                       "Contact the administrator.")
        return view_func(*args, **kwargs)
    return wrapped
