"""
Nashat RAG Server — Config-Driven
==================================

Loads an agent config from YAML, queries ChromaDB collections according to
the agent's configured modes, and generates responses via Claude.

Unlike the old nashat_server.py, everything that shapes behavior lives in
config/nashat_*.yaml, NOT in this file. To change Nashat's voice, instructions,
guardrails, or which collections she queries, edit the YAML. The server hot-
reloads the YAML on save.

Runs on port 5051 during Phase 1 so it doesn't collide with the old server.

Endpoints:
  GET  /health       — status, collection counts, active agent + mode
  GET  /modes        — list of modes available for the current agent
  POST /query        — raw retrieval, no generation (for debugging)
  POST /chat         — full pipeline: retrieve + generate

Environment variables (from .env or shell):
  ANTHROPIC_API_KEY  — required for /chat
  OPENAI_API_KEY     — required for query embedding
  CHROMA_DB_PATH     — absolute path to chroma_db directory
  DEFAULT_AGENT      — nashat_sales | nashat_coaching
"""
from __future__ import annotations
import os
import sys
import json
from pathlib import Path

from flask import Flask, request, jsonify
from flask_cors import CORS
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv
import requests

# Make sibling packages importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.config_loader import ConfigLoader
from config.schema import AgentConfig, Mode


# =============================================================================
# ENVIRONMENT + CONFIG
# =============================================================================

# Load .env from the repo root if present; fall back to shell environment.
load_dotenv(_REPO_ROOT / ".env")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
CHROMA_DB_PATH = os.environ.get("CHROMA_DB_PATH")
if not CHROMA_DB_PATH:
    # Local dev fallback: use ./chroma_db relative to repo root. Railway must
    # set CHROMA_DB_PATH=/data/chroma_db explicitly — we refuse to guess.
    _default = Path(__file__).resolve().parent.parent / "chroma_db"
    if _default.exists():
        CHROMA_DB_PATH = str(_default)
        print(f"[startup] CHROMA_DB_PATH unset, defaulting to {CHROMA_DB_PATH}",
              file=sys.stderr)
    else:
        raise RuntimeError(
            "CHROMA_DB_PATH environment variable is required. "
            "Set it to the absolute path of your chroma_db directory."
        )
DEFAULT_AGENT = os.environ.get("DEFAULT_AGENT", "nashat_sales")
PORT = int(os.environ.get("PORT", "5051"))

# On Railway, set CONFIG_DIR=/data/config so YAMLs live on the persistent
# volume. Falls back to the in-repo config/ directory for local dev.
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", str(_REPO_ROOT / "config")))
AGENT_YAML = CONFIG_DIR / f"{DEFAULT_AGENT}.yaml"
if not AGENT_YAML.exists():
    print(f"FATAL: agent config not found: {AGENT_YAML}", file=sys.stderr)
    sys.exit(1)

print(f"[startup] loading agent config: {AGENT_YAML.name}")
config_loader = ConfigLoader(AGENT_YAML)
config_loader.start_watching()


# =============================================================================
# CHROMA — embedding function + collection handles
# =============================================================================

if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY not set — query embedding will fail",
          file=sys.stderr)

openai_ef = OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name=config_loader.config.knowledge.retrieval_config.embedding_model,
) if OPENAI_API_KEY else None

print(f"[startup] chroma path: {CHROMA_DB_PATH}")
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

# Load every collection listed in the agent config. Missing ones are logged
# but don't crash the server — the agent just can't use modes that need them.
collections: dict[str, "chromadb.Collection"] = {}
for name in config_loader.config.knowledge.knowledge_collections:
    try:
        collections[name] = chroma_client.get_collection(
            name, embedding_function=openai_ef
        )
        print(f"[startup] loaded collection '{name}': "
              f"{collections[name].count()} chunks")
    except Exception as e:
        print(f"[startup] collection '{name}' not available: {e}",
              file=sys.stderr)


# =============================================================================
# PROMPT ASSEMBLY
# =============================================================================

def assemble_system_prompt(config: AgentConfig, mode: Mode) -> str:
    """Build the full system prompt from config + the active mode overlay."""
    parts: list[str] = []

    parts.append(config.behavior.purpose.strip())
    parts.append("")
    parts.append("YOUR SPEAKING STYLE:")
    parts.append(config.behavior.speaking_style.strip())

    if config.behavior.custom_instructions:
        parts.append("")
        parts.append("BEHAVIORAL RULES:")
        for i, instr in enumerate(config.behavior.custom_instructions, 1):
            parts.append(f"{i}. {instr}")

    g = config.guardrails
    if g.character_rules:
        parts.append("")
        parts.append("CHARACTER RULES (non-negotiable):")
        for rule in g.character_rules:
            parts.append(f"- {rule}")

    if g.never_do:
        parts.append("")
        parts.append("NEVER:")
        for rule in g.never_do:
            parts.append(f"- {rule}")

    if g.always_do:
        parts.append("")
        parts.append("ALWAYS:")
        for rule in g.always_do:
            parts.append(f"- {rule}")

    if g.domain_knowledge_rules:
        parts.append("")
        parts.append("CLINICAL KNOWLEDGE RULES:")
        for rule in g.domain_knowledge_rules:
            parts.append(f"- {rule}")

    if g.escalation_rules:
        parts.append("")
        parts.append("ESCALATION:")
        for rule in g.escalation_rules:
            parts.append(f"- {rule}")

    if g.sales_directives:
        parts.append("")
        parts.append("SALES DIRECTION:")
        for rule in g.sales_directives:
            parts.append(f"- {rule}")

    if mode.prompt_overlay:
        parts.append("")
        parts.append("=" * 60)
        parts.append("MODE-SPECIFIC INSTRUCTIONS FOR THIS CONVERSATION:")
        parts.append(mode.prompt_overlay.strip())
        parts.append("=" * 60)

    parts.append("")
    parts.append(
        "If you lack sufficient context from the retrieved knowledge, say so "
        "clearly. Do not fabricate."
    )

    return "\n".join(parts)


def retrieve_for_mode(question: str, mode: Mode) -> list[dict]:
    """Query each collection listed in the mode and return merged chunks."""
    chunks: list[dict] = []

    n_map = {
        "rf_coaching_transcripts": mode.coaching_n,
        "rf_reference_library": mode.reference_n,
        "rf_published_content": mode.published_n,
    }

    for coll_name in mode.collections:
        n = n_map.get(coll_name, 0)
        if n == 0:
            continue
        coll = collections.get(coll_name)
        if coll is None:
            print(f"[retrieve] skipping '{coll_name}' — not loaded",
                  file=sys.stderr)
            continue
        try:
            results = coll.query(query_texts=[question], n_results=n)
            for i in range(len(results["documents"][0])):
                chunks.append({
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] or {},
                    "distance": results["distances"][0][i],
                    "source": coll_name,
                })
        except Exception as e:
            print(f"[retrieve] '{coll_name}' query error: {e}",
                  file=sys.stderr)

    return chunks


def format_context(chunks: list[dict]) -> str:
    """Turn retrieved chunks into labeled context blocks for the LLM."""
    if not chunks:
        return ""

    by_source: dict[str, list[dict]] = {}
    for chunk in chunks:
        by_source.setdefault(chunk["source"], []).append(chunk)

    blocks: list[str] = []
    if "rf_coaching_transcripts" in by_source:
        blocks.append("COACHING CONTEXT (from real coaching sessions):")
        blocks.append("")
        for i, c in enumerate(by_source["rf_coaching_transcripts"], 1):
            meta = c["metadata"]
            blocks.append(f"--- Coaching Exchange {i} ---")
            if meta.get("topics"):
                blocks.append(f"Topics: {meta['topics']}")
            blocks.append(c["text"])
            blocks.append("")

    if "rf_reference_library" in by_source:
        blocks.append("REFERENCE KNOWLEDGE (from A4M Fertility Certification):")
        blocks.append("")
        for i, c in enumerate(by_source["rf_reference_library"], 1):
            meta = c["metadata"]
            blocks.append(f"--- Reference {i} ---")
            if meta.get("module_number") and meta.get("module_topic"):
                blocks.append(f"Module {meta['module_number']}: {meta['module_topic']}")
            if meta.get("speaker"):
                blocks.append(f"Presenter: {meta['speaker']}")
            blocks.append(c["text"])
            blocks.append("")

    if "rf_published_content" in by_source:
        blocks.append("PUBLISHED CONTENT (Dr. Nashat's own writing/teaching):")
        blocks.append("")
        for i, c in enumerate(by_source["rf_published_content"], 1):
            blocks.append(f"--- Published {i} ---")
            blocks.append(c["text"])
            blocks.append("")

    return "\n".join(blocks)


# =============================================================================
# CLAUDE API
# =============================================================================

def call_claude(system_prompt: str, messages: list[dict],
                model: str, max_tokens: int, temperature: float) -> str:
    """Call the Anthropic Messages API and return the assistant text."""
    if not ANTHROPIC_API_KEY:
        return "[ERROR] ANTHROPIC_API_KEY not set on the server."

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system_prompt,
                "messages": messages,
            },
            timeout=60,
        )
        data = resp.json()
        if "content" in data and data["content"]:
            return data["content"][0]["text"]
        if "error" in data:
            return f"[Claude API error] {data['error'].get('message', str(data['error']))}"
        return f"[Unexpected Claude response] {json.dumps(data)[:400]}"
    except Exception as e:
        return f"[Generation error] {e}"


# =============================================================================
# FLASK APP
# =============================================================================

app = Flask(__name__)
CORS(app)


@app.route("/health", methods=["GET"])
def health():
    cfg = config_loader.config
    return jsonify({
        "status": "ok",
        "agent_id": cfg.agent_id,
        "persona_name": cfg.persona.name,
        "default_mode": cfg.behavior.default_mode,
        "available_modes": list(cfg.behavior.modes.keys()),
        "loaded_collections": {
            name: collections[name].count()
            for name in collections
        },
        "model": cfg.behavior.model_name,
        "anthropic_key_set": bool(ANTHROPIC_API_KEY),
        "openai_key_set": bool(OPENAI_API_KEY),
    })


@app.route("/modes", methods=["GET"])
def list_modes():
    cfg = config_loader.config
    return jsonify({
        "default_mode": cfg.behavior.default_mode,
        "modes": {
            name: {
                "label": m.label,
                "description": m.description,
                "collections": m.collections,
            }
            for name, m in cfg.behavior.modes.items()
        },
    })


@app.route("/query", methods=["POST"])
def raw_query():
    """Raw retrieval — returns chunks, no generation. For debugging."""
    data = request.json or {}
    question = data.get("question", "")
    mode_name = data.get("mode") or config_loader.config.behavior.default_mode

    cfg = config_loader.config
    mode = cfg.behavior.modes.get(mode_name)
    if mode is None:
        return jsonify({
            "error": f"unknown mode '{mode_name}'",
            "available_modes": list(cfg.behavior.modes.keys()),
        }), 400

    chunks = retrieve_for_mode(question, mode)
    return jsonify({
        "mode": mode_name,
        "chunk_count": len(chunks),
        "chunks": chunks,
    })


@app.route("/chat", methods=["POST"])
def chat():
    """Full pipeline: retrieve context, build prompt, call Claude."""
    data = request.json or {}
    question = data.get("question", "")
    history = data.get("history", [])
    mode_name = data.get("mode") or config_loader.config.behavior.default_mode

    cfg = config_loader.config
    mode = cfg.behavior.modes.get(mode_name)
    if mode is None:
        return jsonify({
            "error": f"unknown mode '{mode_name}'",
            "available_modes": list(cfg.behavior.modes.keys()),
        }), 400

    chunks = retrieve_for_mode(question, mode)
    context = format_context(chunks)
    system_prompt = assemble_system_prompt(cfg, mode)

    messages: list[dict] = []
    for m in history[-6:]:
        messages.append({"role": m["role"], "content": m["content"]})

    user_content = f"{context}\n\nUSER QUESTION:\n{question}" if context else question
    messages.append({"role": "user", "content": user_content})

    response_text = call_claude(
        system_prompt=system_prompt,
        messages=messages,
        model=cfg.behavior.model_name,
        max_tokens=cfg.behavior.max_tokens,
        temperature=cfg.behavior.temperature,
    )

    return jsonify({
        "response": response_text,
        "mode": mode_name,
        "mode_label": mode.label,
        "agent_id": cfg.agent_id,
        "chunk_count": len(chunks),
        "chunks": chunks if cfg.behavior.show_citations else [],
    })


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    cfg = config_loader.config
    print()
    print(f"  Nashat RAG Server (config-driven)")
    print(f"  agent:    {cfg.agent_id} ({cfg.persona.name})")
    print(f"  default:  {cfg.behavior.default_mode}")
    print(f"  modes:    {', '.join(cfg.behavior.modes.keys())}")
    print(f"  model:    {cfg.behavior.model_name}")
    print(f"  url:      http://localhost:{PORT}")
    print()
    app.run(host="0.0.0.0", port=PORT, debug=False)
