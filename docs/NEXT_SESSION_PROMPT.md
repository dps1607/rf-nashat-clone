# NEXT SESSION PROMPT — session 10

> **⚠ READ THIS FIRST, BEFORE ANY READING LIST**
>
> Session 9 was a stabilization session that corrected major drift inherited from sessions 5–8. The previous version of this prompt pointed Claude at executing Plans 1 and 2 from the session 7 HANDOVER. That work was based on premises that turned out to be wrong (see `docs/STATE_OF_PLAY.md`). **Do not re-derive Plan 1, Plan 2, or Plan 3 from the session 7 HANDOVER without first reading STATE_OF_PLAY.md in full.** They are frozen, not driving next-session work.

---

## Step 0 — Tool and reality check (mandatory, takes ~5 minutes)

Before reading anything else, do all of the following. **Stop and tell Dan if any of them surface a surprise.**

1. **Tool enumeration.** You need filesystem tools (`Filesystem:read_text_file`, `Filesystem:write_file`) AND process execution (`Desktop Commander:start_process` and friends, `bash_tool`, or `tool_search` you can use to load Desktop Commander). If you only have filesystem and no process pathway, stop and tell Dan the chat needs Desktop Commander loaded.

2. **Smoke test process execution.** Run `echo "session 10 tool check $(date -u +%Y-%m-%dT%H:%M:%SZ)"`. Confirm it works.

3. **Repo state.** `cd /Users/danielsmith/Claude\ -\ RF\ 2.0/rf-nashat-clone && git status && git log --oneline -5`. The expected baseline is "clean tree, on `main`, top commit is whatever Dan landed at the end of session 9 (probably a docs commit)." If the tree is not clean or the top commits don't match what HANDOVER.md describes, stop and surface it.

4. **Reality-vs-prompt check.** This is the new one, added because session 8 didn't do it and session 9 had to clean up the mess. Before reading the reading list below, independently verify the following claims against the actual filesystem and git history:
   - Does `rag_server/app.py` still read exactly four metadata fields (`topics` from coaching, `module_number` / `module_topic` / `speaker` from reference library)? `grep -n "metadata\|meta\.get" rag_server/app.py | head -30`. If something has changed the consumer of metadata, that changes the consistency analysis in STATE_OF_PLAY and you should re-check before proceeding.
   - Does `data/selection_state.json` still contain placeholder data (`"abc"`, `"def"`)? If a previous session wrote real data into it, the "UI never driven end-to-end" framing in STATE_OF_PLAY is stale.
   - Does the local Chroma at `/Users/danielsmith/Claude - RF 2.0/chroma_db/` still have `rf_coaching_transcripts` (9,224) and `rf_reference_library` (584)? Run `./venv/bin/python scripts/peek_reference_library.py 2>&1 | head -10` to confirm count quickly.
   - Is Railway production still serving at `https://console.drnashatlatib.com`? `curl -sI https://console.drnashatlatib.com | head -5` should return an HTTP/2 302 redirecting to `cloudflareaccess.com`. (Don't try to log in. Just confirm the front door is alive.)

If any of these checks return surprises, **stop**, surface the surprise to Dan, and reorient before reading anything further. The whole point of step 0 is to catch drift like this *before* the architecture-shaped framing of the reading list pulls you into work that doesn't match reality.

---

## Reading order (after step 0 passes)

Tight reading list. ~15% of context budget on reads, ~70% on actually building/debugging the UI flow, ~15% reserve.

1. **`docs/STATE_OF_PLAY.md`** — the corrected current-state document from session 9. **This is authoritative.** It supersedes parts of REPO_MAP, ARCHITECTURE, and the session 7 HANDOVER entry. Read it in full.
2. **`docs/REPO_MAP.md`** — orient to file layout. Treat the "Coaching collection state" and "Phase 1 backfill" claims as superseded by STATE_OF_PLAY; everything else is still useful.
3. **`admin_ui/app.py`** — focus on the routes under `/admin/folders` and `/admin/api/folders/*` and `/admin/api/drive/*`. This is where the UI thread lives.
4. **`admin_ui/templates/folders.html` and `admin_ui/static/folder-tree.js`** — what the UI actually renders. Skim, do not deep-read; you'll need to come back to specific sections when bugs surface.
5. **`admin_ui/manifest.py`** — how the folder walk manifests get loaded and consumed by the UI.
6. **`data/inventories/folder_walk_20260412_153931.json`** — head peek only, don't dump the 13 MB file. Use `python3 -c "import json; d=json.load(open('...')); print(json.dumps({k: type(v).__name__ for k,v in d.items()}))"` to see top-level shape, then peek into one drive's structure.
7. **`rag_server/app.py`** — focus on `retrieve_for_mode()` and `format_context()` (around lines 190–270). These are the two functions that consume metadata. Anything that changes how chunks are rendered to the LLM happens here.

**Do not read** (deliberate skips):
- The session 7 HANDOVER entry — frozen, see STATE_OF_PLAY's note on this
- ADR_005, ADR_006, ADR_002 addendum — frozen design work, not driving next-session decisions
- `HANDOVER_INTERNAL_EDUCATION_BUILD.md`, `INCIDENTS.md`, anything from sessions 5/6/7
- `BACKLOG.md` unless you finish the main task and have time for one of the deferred items

---

## The actual goal for session 10

**Drive the folder-selection UI end-to-end with one real folder.** Concretely:

1. Start the admin UI locally in dev mode (Cloudflare Access disabled, local password mode). The exact command is in the dev portion of `bootstrap.sh` or `Procfile.honcho` — figure it out, don't guess. Confirm the rag_server is also running locally so the test panel works.
2. Open a browser to `http://localhost:5052/admin/folders` (or whatever port the admin UI runs on locally — verify from `app.py` and `.env.example`).
3. Browse the real Drive folder tree. Confirm the existing 13 MB manifest at `data/inventories/folder_walk_20260412_153931.json` actually loads, that all 12 Shared Drives appear, and that you can drill into folders.
4. Pick one real folder — something small and uncomplicated, ideally one Dan can name in the conversation. Assign it to a library through the UI. Hit save. **Watch what happens.**
5. The first thing that breaks is the next bug to fix. Examples of likely-but-not-certain failure modes (don't over-anticipate; let the actual breakage tell you what's broken):
   - Save button persists `selection_state.json` correctly but no downstream consumer reads it
   - Library name doesn't match anything the rag_server knows about
   - There's no "ingestion trigger" wired up between the UI's save and any actual loader
   - The loader exists but is the Drive ingester (`ingester/folder_walk.py`, `ingester/main.py`) and the wiring between the UI's selection and the ingester's input format is incomplete
6. Fix one thing at a time. Each fix should be a small, reviewable diff, dry-run-tested, with Dan approving before any state-changing operation.

**Stop conditions** (any of these is success enough for one session):
- One real folder is selected, saved, and either ingested OR the exact missing piece between "saved" and "ingested" is identified, written up, and reviewed with Dan.
- One real chunk from a newly-ingested source comes back in a test query through the admin UI's inline test panel.
- One unexpected bug in the UI flow gets fixed and verified, even if the end-to-end flow isn't yet complete.

**Anti-goal:** do not extend the session past the first natural stopping point in pursuit of an end-to-end happy path. Sessions that try to do too much produce drift like sessions 5–8. One real concrete step forward is more valuable than a planned-out roadmap of three steps that doesn't get executed.

---

## The smaller side quest (only if it surfaces as a blocker)

If, while driving the UI flow, you discover that the test panel renders a coaching chunk's citation as "Topics: Vitamin D|Insulin/Blood Sugar" with no source/date/speaker provenance — and Dan agrees that's a problem worth fixing during this session — the fix is documented in `STATE_OF_PLAY.md` under "The minimum bar for 'metadata consistent enough'." It's a small read-time normalizer in `rag_server/app.py`'s `format_context()` function, mapping both collections into a 5-field display shape. ~50 lines of Python. **No Chroma writes. No backfill. Pure read-side.**

This is *not* the goal. Do not start with this. Only do it if it surfaces naturally as a blocker on actually reading what comes back from the UI test panel after a new ingestion lands.

---

## Hard rules carried forward (unchanged from sessions 7, 8, 9)

- No ChromaDB writes without explicit Dan approval at the specific write moment, and never to Railway without a pre-flight discussion of backups
- No git push, commit, or add — Dan runs git, Claude suggests
- No Railway operations without explicit approval
- No deletions without approval and a verified backup
- Never reference Dr. Christina (she's stored in the `coaches` field of every coaching chunk; the read-time normalizer if built must scrub her out)
- Exclude Kelsey Poe and Erica from any retrieval sample output
- Dr. Chris stays internal (diarization label, not surfaced)
- Public agent never accesses `rf_coaching_transcripts` (HIPAA boundary)
- Credentials are ephemeral — never stored in memory or files
- `create_file` writes to Claude's sandbox, not the Mac. **Use Desktop Commander heredocs (`cat > path <<'EOF'`) or `Filesystem:write_file` for any file that must land in the repo.** Session 8 hit this trap. Don't repeat it.

---

## Tech-lead mandate (carried forward, with one addition)

Claude holds tech-lead role. Tactical decisions (script layout, validator shape, mapping conventions, where a helper lives) are Claude's call. Strategic decisions (irreversible operations, money spend > $25, anything crossing the RAG/app/product/legal boundary, anything that fails the "can we fix this later?" reversibility test) get flagged to Dan first.

**Addition from session 9:** at session start, *before* reading the reading list, independently verify the bootstrap prompt's description of the world against the evidence on disk. If the prompt describes a world that doesn't match the file tree, the git history, or the deployed system, **stop and surface the drift before doing any other work.** Step 0's reality-vs-prompt check is the implementation of this rule. This addition exists because session 8 followed an inherited reading list that described a world that no longer matched reality, and the resulting work was about to do harm. The rule is: read the system, *then* read what someone wrote about the system, and reconcile any gaps before acting.

---

## Quick reference

- Repo root: `/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone`
- Local Chroma: `/Users/danielsmith/Claude - RF 2.0/chroma_db/` (development sandbox; Railway is canonical)
- Railway production: `https://console.drnashatlatib.com` (Cloudflare Access in front; allowlisted: dan@reimagined-health.com, znahealth@gmail.com)
- venv interpreter: `./venv/bin/python` (Python 3.11.3, chromadb 1.5.6) — use this for all Python commands, not system python3
- Most recent folder walk manifest: `data/inventories/folder_walk_20260412_153931.json` (13 MB, 12 Shared Drives)
- `selection_state.json`: still contains placeholder `["abc", "def"]` as of session 9
