"""
Admin UI — Flask app.

Loads YAML configs, renders them as forms, validates edits via Pydantic,
writes back to disk. The RAG server picks up changes via hot reload.

Runs in one of two auth modes (see admin_ui/auth.py for details):
  - CLOUDFLARE_ACCESS_ENABLED=true  → Cloudflare Access in front, JWT verified
  - otherwise                       → local bcrypt password flow (dev only)

Routes:
  GET  /login        login form (local dev mode only)
  POST /login        authenticate (local dev mode only)
  GET  /logout       clear session
  GET  /             redirect to editor
  GET  /edit         editor for the selected agent
  POST /save         validate + write YAML
  POST /api/test     proxy a test chat to the RAG server
  GET  /api/health   RAG server health
"""
from __future__ import annotations
import os
import sys
from datetime import timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, session, abort,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from werkzeug.middleware.proxy_fix import ProxyFix

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from admin_ui import audit
from admin_ui.auth import (
    CLOUDFLARE_ACCESS_ENABLED,
    authenticate, login_user, logout_user, current_user, login_required,
)
from admin_ui.forms import load_yaml, save_yaml, validate, parse_form_data

load_dotenv(_REPO_ROOT / ".env")

SESSION_SECRET = os.environ.get("ADMIN_SESSION_SECRET", "")
RAG_SERVER_URL = os.environ.get("RAG_SERVER_URL", "http://localhost:5051")
PORT = int(os.environ.get("ADMIN_PORT", "5052"))
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", str(_REPO_ROOT / "config")))

AVAILABLE_AGENTS = ["nashat_sales", "nashat_coaching"]

if not SESSION_SECRET or SESSION_SECRET.startswith("change-me"):
    print("WARNING: ADMIN_SESSION_SECRET not set or still default — sessions are insecure",
          file=sys.stderr)
    SESSION_SECRET = "dev-only-not-for-production"


# -----------------------------------------------------------------------------
# Flask app factory
# -----------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = SESSION_SECRET

# ProxyFix: trust X-Forwarded-For / X-Forwarded-Proto from the proxy in front
# of us (Cloudflare + Railway's edge). Without this, flask-limiter would see
# every request as coming from 127.0.0.1 and rate limiting wouldn't work.
# x_for=1, x_proto=1 means we trust exactly one hop — Railway's edge. Cloudflare
# sits *behind* Railway in the proxy chain from Flask's point of view because
# Cloudflare forwards to Railway's domain; Railway's proxy then forwards the
# X-Forwarded-For chain onward to us.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Session cookie hardening
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,        # https only — Cloudflare/Railway both TLS
    SESSION_COOKIE_SAMESITE="Strict",  # no cross-site cookie sharing
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)

# Security headers via Talisman. CSP is lenient to not break the editor's
# existing inline styles/scripts — this is a private admin panel, not a
# public site facing untrusted content.
_csp = {
    "default-src": "'self'",
    "script-src": ["'self'", "'unsafe-inline'"],
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:"],
    "connect-src": "'self'",
    "frame-ancestors": "'none'",
}
Talisman(
    app,
    content_security_policy=_csp,
    force_https=False,          # Cloudflare/Railway handle TLS termination
    strict_transport_security=True,
    strict_transport_security_max_age=31536000,
    session_cookie_secure=True,
    session_cookie_http_only=True,
    referrer_policy="strict-origin-when-cross-origin",
    frame_options="DENY",
)

# Rate limiting. Defense in depth — Cloudflare Access should stop brute-force
# attempts from reaching us at all, but we enforce locally too. get_remote_address
# reads request.remote_addr which ProxyFix has normalized to the real client IP.
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["500 per hour"],
    storage_uri="memory://",
)

# Log startup so we can correlate audit events with deploys
audit.log("startup", user="-system-", details={
    "cloudflare_access_enabled": CLOUDFLARE_ACCESS_ENABLED,
    "config_dir": str(CONFIG_DIR),
    "rag_server_url": RAG_SERVER_URL,
})


# -----------------------------------------------------------------------------
# Template context + routes
# -----------------------------------------------------------------------------

@app.context_processor
def inject_user():
    user = current_user()
    # Strip the _unauthorized sentinel before handing to templates so
    # templates never accidentally render a forbidden user as logged in.
    if user and user.get("_unauthorized"):
        user = None
    return {
        "current_user": user,
        "available_agents": AVAILABLE_AGENTS,
        "cloudflare_mode": CLOUDFLARE_ACCESS_ENABLED,
    }


def _user_label(user: dict | None) -> str:
    """Short identifier for audit logs."""
    if not user:
        return "-"
    return user.get("email") or user.get("username") or user.get("name") or "-"


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per 15 minutes", methods=["POST"])
def login():
    if CLOUDFLARE_ACCESS_ENABLED:
        # Password login disabled in Cloudflare mode. Show a clear message.
        return render_template("login.html"), 200

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = authenticate(username, password)
        if user is None:
            audit.log("login_failure", user=username or "-",
                      details={"reason": "invalid credentials"})
            flash("Invalid username or password", "error")
            return render_template("login.html"), 401
        login_user(user)
        audit.log("login_success", user=_user_label(user),
                  details={"mode": "local_bcrypt"})
        next_url = request.args.get("next") or url_for("edit")
        return redirect(next_url)
    return render_template("login.html")


@app.route("/logout")
def logout():
    logout_user()
    if CLOUDFLARE_ACCESS_ENABLED:
        # In Cloudflare mode we can't actually log the user out of Cloudflare
        # from here. Send them to Cloudflare's logout URL.
        team_domain = os.environ.get("CLOUDFLARE_ACCESS_TEAM_DOMAIN", "").strip()
        if team_domain:
            return redirect(f"https://{team_domain}/cdn-cgi/access/logout")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return redirect(url_for("edit"))


def _agent_path(agent_id: str) -> Path:
    if agent_id not in AVAILABLE_AGENTS:
        raise ValueError(f"unknown agent: {agent_id}")
    return CONFIG_DIR / f"{agent_id}.yaml"


@app.route("/edit")
@login_required
def edit():
    agent_id = request.args.get("agent", "nashat_sales")
    if agent_id not in AVAILABLE_AGENTS:
        agent_id = "nashat_sales"
    try:
        data = load_yaml(_agent_path(agent_id))
    except FileNotFoundError:
        flash(f"Config file not found: {agent_id}.yaml", "error")
        return redirect(url_for("edit", agent="nashat_sales"))
    return render_template(
        "editor.html",
        agent_id=agent_id,
        data=data,
        rag_server_url=RAG_SERVER_URL,
    )


@app.route("/save", methods=["POST"])
@login_required
def save():
    user = current_user()
    user_label = _user_label(user)
    agent_id = request.form.get("__agent_id", "")
    if agent_id not in AVAILABLE_AGENTS:
        return jsonify({"ok": False, "error": f"unknown agent: {agent_id}"}), 400

    path = _agent_path(agent_id)
    try:
        original = load_yaml(path)
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "config file missing"}), 500

    form_data = {k: v for k, v in request.form.items() if not k.startswith("__")}
    merged = parse_form_data(form_data, original)

    ok, err = validate(merged)
    if not ok:
        audit.log("yaml_save_invalid", user=user_label,
                  details={"agent_id": agent_id, "error": err[:500]})
        return jsonify({"ok": False, "error": err}), 400

    try:
        save_yaml(path, merged)
    except OSError as e:
        audit.log("yaml_save", user=user_label,
                  details={"agent_id": agent_id, "ok": False, "error": str(e)})
        return jsonify({"ok": False, "error": f"write failed: {e}"}), 500

    audit.log("yaml_save", user=user_label,
              details={"agent_id": agent_id, "ok": True,
                       "field_count": len(form_data)})
    return jsonify({"ok": True, "agent": agent_id, "saved_by": user_label})


@app.route("/api/test", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def api_test():
    """Proxy a test message to the RAG server's /chat endpoint."""
    user_label = _user_label(current_user())
    body = request.get_json(silent=True) or {}
    question = body.get("question", "").strip()
    mode = body.get("mode") or None
    if not question:
        return jsonify({"error": "question required"}), 400

    payload = {"question": question}
    if mode:
        payload["mode"] = mode

    # Log the query (truncated) but NOT the response — responses may contain
    # retrieved coaching transcript chunks which we don't want in the audit log.
    audit.log("test_query", user=user_label,
              details={"mode": mode or "default", "q_len": len(question),
                       "q_preview": question[:200]})

    try:
        r = requests.post(f"{RAG_SERVER_URL}/chat", json=payload, timeout=90)
        r.raise_for_status()
        return jsonify(r.json())
    except requests.exceptions.ConnectionError:
        return jsonify({
            "error": f"could not reach RAG server at {RAG_SERVER_URL} — is it running?"
        }), 502
    except requests.exceptions.HTTPError as e:
        return jsonify({"error": f"RAG server error: {e}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health")
@login_required
def api_health():
    """Proxy through to the RAG server's health endpoint."""
    try:
        r = requests.get(f"{RAG_SERVER_URL}/health", timeout=5)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"status": "unreachable", "error": str(e)}), 502


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        "error": "rate limit exceeded",
        "detail": str(e.description),
    }), 429


if __name__ == "__main__":
    print()
    print("  Nashat Admin UI")
    print(f"  mode:         {'Cloudflare Access' if CLOUDFLARE_ACCESS_ENABLED else 'local bcrypt'}")
    print(f"  agents:       {', '.join(AVAILABLE_AGENTS)}")
    print(f"  rag server:   {RAG_SERVER_URL}")
    print(f"  url:          http://localhost:{PORT}")
    print()
    app.run(host="0.0.0.0", port=PORT, debug=False)
