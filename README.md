# RF Nashat Clone

Self-hosted, config-driven RAG clone of Dr. Nashat Latib for Reimagined Fertility.
Replaces the previous Delphi.ai "Digital Mind." Built to run locally during
development and deploy to Railway in production.

## What this is

A pair of AI agents — `nashat_sales` (public) and `nashat_coaching` (internal,
paywalled) — that share a single Pydantic-validated YAML schema. Every dial
that shapes Nashat's behavior (persona, voice, instructions, guardrails,
clinical knowledge rules, retrieval modes) lives in `config/*.yaml`, not in
Python. Edit the YAML, save, the running server hot-reloads within ~1 second.

## Project layout

```
rf-nashat-clone/
├── config/
│   ├── schema.py              # Pydantic source of truth
│   ├── nashat_sales.yaml      # public sales agent
│   └── nashat_coaching.yaml   # internal coaching agent (paywalled)
├── shared/
│   └── config_loader.py       # YAML loader + hot reload
├── rag_server/
│   └── app.py                 # Flask server, port 5051
├── admin_ui/                  # Phase 2 — web UI for editing YAMLs
├── requirements.txt
├── .env.example               # template — copy to .env, fill in real keys
├── .gitignore                 # excludes .env, venv/, chroma_db/
└── README.md
```

## Phase status

- **Phase 1 — DONE.** Schema, two YAMLs, loader with hot reload, RAG server,
  end-to-end tested with Claude Sonnet 4.6.
- **Phase 2 — TODO.** Password-protected web admin UI on port 5052 for
  editing the YAMLs through a browser.
- **Phase 3 — TODO.** Railway deployment, persistent volume for ChromaDB,
  custom domain.

## Local setup

You only need to do this once.

```bash
cd "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Open .env in a text editor and paste in real keys
```

The `.env` file is gitignored. Your real API keys never go into git.

## Running the server

Every time:

```bash
cd "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone"
source venv/bin/activate
python3 rag_server/app.py
```

Then in another terminal:

```bash
curl http://localhost:5051/health
```

You should see JSON with `"status": "ok"`, the loaded agent, and the loaded
collections.

## Endpoints

| Method | Path     | Purpose                                          |
|--------|----------|--------------------------------------------------|
| GET    | /health  | Status, agent, modes, collection counts          |
| GET    | /modes   | Available modes for the current agent            |
| POST   | /query   | Raw retrieval, no generation (debugging)         |
| POST   | /chat    | Full pipeline: retrieve + generate via Claude    |

`/chat` body:

```json
{
  "question": "What does AMH actually tell us about fertility?",
  "mode": "public_default",
  "history": []
}
```

`mode` is optional; defaults to the agent's `default_mode`. `history` is an
optional list of `{role, content}` for multi-turn conversations.

## Switching agents

Set `DEFAULT_AGENT` in `.env`:

```
DEFAULT_AGENT=nashat_coaching
```

Then restart the server. (Eventually we'll support per-request agent selection;
for now it's per-process.)

## Hot reload

The server watches `config/<DEFAULT_AGENT>.yaml` for changes. Save the file
in your editor and the server reloads within ~1 second. If your edit fails
schema validation, the previous valid config is kept and the error is logged
to stderr — the server keeps serving requests with the last-known-good state.

## Modes

Each agent defines named "modes" — different combinations of retrieval and
prompt overlays for different conversation types.

Sales agent modes:
- `public_default` — reference library only, general sales conversations
- `a4m_course_analysis` — evaluate A4M course material against FKSP and
  surface evidence/statistics for client belief-building

Coaching agent modes:
- `internal_full` — coaching transcripts + reference (default)
- `coaching_only` — pure clinical experience
- `reference_only` — A4M evidence lookup
- `a4m_course_analysis` — same as sales

To use a non-default mode, pass `"mode": "a4m_course_analysis"` in the
`/chat` request body.

## Knowledge collections

The repo expects a ChromaDB instance at `CHROMA_DB_PATH` (set in `.env`).
Currently:

- `rf_coaching_transcripts` — 9,224 chunks (used by coaching agent only)
- `rf_reference_library` — 584 chunks of A4M course material
- `rf_published_content` — planned, not yet built

The chroma_db directory lives outside this repo and is not tracked in git.
For Railway deployment, the chroma_db will be uploaded to a persistent volume.

## Editing the YAMLs

Phase 1 workflow: open `config/nashat_sales.yaml` in your text editor, change
what you want, save. The running server reloads automatically.

Phase 2 will replace this with a web admin UI.

Schema validation is strict — unknown fields, wrong types, or missing required
fields will fail. Errors are clear (Pydantic tells you exactly which field is
wrong) and the server keeps running with the previous valid config until you
fix the YAML.

## What lives in YAML vs Python

**YAML (edit freely):** persona, bio, custom instructions, speaking style,
guardrails, domain knowledge rules, sales directives, mode definitions,
prompt overlays, model selection, temperature, retrieval parameters.

**Python (don't touch unless you mean it):** the Flask routes, the prompt
assembly logic, the Chroma query mechanics, the Claude API call.

This separation is the whole point: Nashat-the-agent should be tunable
without writing code; the plumbing should be stable.
