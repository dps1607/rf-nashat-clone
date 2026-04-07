"""
Admin UI — Flask app on port 5052.

Loads YAML configs, renders them as forms, validates edits via Pydantic,
writes back to disk. The RAG server picks up changes via hot reload.

Routes:
  GET  /login        login form
  POST /login        authenticate
  GET  /logout       clear session
  GET  /             redirect to editor
  GET  /edit         editor for the selected agent
  POST /save         validate + write YAML
  POST /api/test     proxy a test chat to the RAG server
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
    flash, jsonify, session,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


from admin_ui.auth import (
    authenticate, login_user, logout_user, current_user, login_required,
)
from admin_ui.forms import load_yaml, save_yaml, validate, parse_form_data

load_dotenv(_REPO_ROOT / ".env")

SESSION_SECRET = os.environ.get("ADMIN_SESSION_SECRET", "")
RAG_SERVER_URL = os.environ.get("RAG_SERVER_URL", "http://localhost:5051")
PORT = int(os.environ.get("ADMIN_PORT", "5052"))
# On Railway, set CONFIG_DIR=/data/config so YAMLs live on the persistent
# volume. Falls back to the in-repo config/ directory for local dev.
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", str(_REPO_ROOT / "config")))

AVAILABLE_AGENTS = ["nashat_sales", "nashat_coaching"]

if not SESSION_SECRET or SESSION_SECRET.startswith("change-me"):
    print("WARNING: ADMIN_SESSION_SECRET not set or still default — sessions are insecure",
          file=sys.stderr)
    SESSION_SECRET = "dev-only-not-for-production"

app = Flask(__name__)
app.secret_key = SESSION_SECRET
app.permanent_session_lifetime = timedelta(days=30)


@app.context_processor
def inject_user():
    return {"current_user": current_user(), "available_agents": AVAILABLE_AGENTS}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = authenticate(username, password)
        if user is None:
            flash("Invalid username or password", "error")
            return render_template("login.html"), 401
        login_user(user)
        next_url = request.args.get("next") or url_for("edit")
        return redirect(next_url)
    return render_template("login.html")


@app.route("/logout")
def logout():
    logout_user()
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
    agent_id = request.form.get("__agent_id", "")
    if agent_id not in AVAILABLE_AGENTS:
        return jsonify({"ok": False, "error": f"unknown agent: {agent_id}"}), 400

    path = _agent_path(agent_id)
    try:
        original = load_yaml(path)
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "config file missing"}), 500

    # Strip control fields out of the form before parsing
    form_data = {k: v for k, v in request.form.items() if not k.startswith("__")}
    merged = parse_form_data(form_data, original)

    ok, err = validate(merged)
    if not ok:
        return jsonify({"ok": False, "error": err}), 400

    try:
        save_yaml(path, merged)
    except OSError as e:
        return jsonify({"ok": False, "error": f"write failed: {e}"}), 500

    return jsonify({"ok": True, "agent": agent_id, "saved_by": current_user()["username"]})


@app.route("/api/test", methods=["POST"])
@login_required
def api_test():
    """Proxy a test message to the RAG server's /chat endpoint."""
    body = request.get_json(silent=True) or {}
    question = body.get("question", "").strip()
    mode = body.get("mode") or None
    if not question:
        return jsonify({"error": "question required"}), 400

    payload = {"question": question}
    if mode:
        payload["mode"] = mode

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


if __name__ == "__main__":
    print()
    print("  Nashat Admin UI")
    print(f"  agents:       {', '.join(AVAILABLE_AGENTS)}")
    print(f"  rag server:   {RAG_SERVER_URL}")
    print(f"  url:          http://localhost:{PORT}")
    print()
    app.run(host="0.0.0.0", port=PORT, debug=False)
