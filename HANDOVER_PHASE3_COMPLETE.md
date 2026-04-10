# Phase 3 Railway Deployment — Handover

**Last updated:** April 9, 2026 (evening session — chroma_db upload + bootstrap hardening + bcrypt polish)
**Status:** FUNCTIONALLY COMPLETE — admin panel fully live, real RAG queries returning cited chunks
**Latest commit on main:** `082a4da`

---

## TL;DR for the next agent

Phase 3.5 of the RF / Reimagined Health admin panel is **done**. The full stack is live in production at https://console.drnashatlatib.com:

- Cloudflare Access in front, gating on Google OAuth
- JWT verified on every request via Cloudflare's JWKS endpoint
- Both authorized users (Dan + Dr. Nashat Latib) can log in
- Audit log capturing every meaningful event (startup, login, access_denied, admin_user_added, test_query, etc.) at /data/audit.jsonl
- Agent YAML configs (nashat_sales.yaml, nashat_coaching.yaml) editable from the admin UI YAML editor with hot-reload
- ChromaDB on the Railway persistent volume at /data/chroma_db: 485 MB, 5 collection subdirectories, 242 MB sqlite, the full rf_coaching_transcripts collection (9,224 chunks) plus an unexpected 584 chunks in rf_reference_library

The admin panel test query was verified end-to-end by Dan running a real query and seeing real cited chunks come back from coaching transcripts. Phase 3.5 is shipped.

**Two non-blocking loose ends** remain (see "What's NOT done" section below for details):
1. Rotate ANTHROPIC_API_KEY and OPENAI_API_KEY on Railway — exposed in a prior session screenshot. ~5 minutes, requires Dan logging into Anthropic Console + OpenAI Platform + Railway dashboard. Cannot be Claude-automated.
2. Investigate why rf_reference_library already has 584 chunks when userMemories said it was unbuilt. Doesn't affect anything live; worth checking when convenient.

There is also one deferred polish item documented in the "Known design decisions" section: jwt/requests/flask are still top-level imports in admin_ui/auth.py even though bcrypt was made lazy this session. If you want admin_ui.auth to be importable from system Python (no venv required), the same lazy-getter pattern would need to apply to those three. No concrete use case currently blocked.

---

## What's live in production (verified this session)

| Component | Status | Notes |
|---|---|---|
| Railway service `rf-nashat-clone` | LIVE | Project `diligent-tenderness`, service `1a89b9b1-e498-4577-9cf8-3fbdbfb16ca0` |
| Custom domain | LIVE | `https://console.drnashatlatib.com` → `8acwb20q.up.railway.app` (orange cloud ON) |
| Cloudflare Access | ACTIVE | App `RF Admin Panel`, AUD `c8d33662919e0e9a9ce2a3c3506c7ef5c4beee7ab631083912e98140e114c0bb` |
| Google OAuth IdP | VERIFIED | Allowlisted: `dan@reimagined-health.com`, `znahealth@gmail.com` |
| Persistent volume | MOUNTED | Volume `00a6bdc8-475e-4eff-b162-1cd9f8726e74` at `/data`, ~4 GB free |
| `/data/admin_users.json` | POPULATED | Both admins, role=admin |
| `/data/audit.jsonl` | WRITING | All event types verified end-to-end |
| `/data/config/nashat_sales.yaml` | SEEDED | Editable via UI YAML editor |
| `/data/config/nashat_coaching.yaml` | SEEDED | Editable via UI YAML editor |
| `/data/chroma_db` | POPULATED THIS SESSION | 485 MB, 5 UUID collection subdirs, 242 MB sqlite |
| `rf_coaching_transcripts` collection | 9,224 chunks | Verified by SQL count + live UI test query |
| `rf_reference_library` collection | 584 chunks | Unexpected — see "Known unknowns" |
| Latest deployed commit | `082a4da` | `auth: lazy-import bcrypt so module imports without venv` |

---

## Recent work done this session (April 9 evening)

Three code commits + this handover doc, all on top of the Phase 3.5 baseline (`d5f9e17`). In commit order:

### 1. `529e0a0` — bootstrap: add chroma_db download via CHROMA_BOOTSTRAP_URL

Re-added the bootstrap block that was reverted at the end of the prior session. The block downloads a tarball from `$CHROMA_BOOTSTRAP_URL` on first deploy when `/data/chroma_db` is empty, extracts it to the volume, logs progress, and is non-fatal on failure (the app still boots with an empty chroma_db, which was the previous baseline). Idempotent: skips on subsequent deploys when chroma_db is already populated.

### 2. `52d66da` — bootstrap: tighten chroma_db guard and clear skeleton before extract

This was a critical fix discovered mid-deployment, and it's the most important learning of the session — **next agent: read this carefully if you ever touch ChromaDB bootstrapping**.

**The bug:** when rag_server.py starts up against an empty `/data/chroma_db` directory, it opens a ChromaDB `PersistentClient(path=...)` which immediately writes a skeleton `chroma.sqlite3` file (188 KB, no collection data, no UUID subdirectories). The original bootstrap guard was:

```bash
if [ -d "$CHROMA_DB_PATH" ] && [ -n "$(ls -A "$CHROMA_DB_PATH" 2>/dev/null)" ]; then
    echo "[bootstrap] chroma_db already populated, leaving alone"
```

That `ls -A` test returns non-empty because the skeleton sqlite file is present, so the guard **false-positives on a freshly-initialized-but-empty volume** and would have silently skipped the download forever, leaving every test query returning zero chunks while the bootstrap looked clean.

**The fix:** check for at least one subdirectory inside `chroma_db`. A populated ChromaDB collection always has UUID-named subdirectories (one per collection) containing HNSW binary index files. A skeleton has zero subdirectories — just the bare sqlite file.

```bash
if [ -d "$CHROMA_DB_PATH" ] && [ -n "$(find "$CHROMA_DB_PATH" -mindepth 1 -type d 2>/dev/null)" ]; then
    echo "[bootstrap] chroma_db already populated (has collection subdirs), leaving alone"
```

Also added `rm -rf "$CHROMA_DB_PATH"` immediately before the `tar xf` extract step, so any pre-existing skeleton sqlite is cleared cleanly rather than risking weird tar-merge behavior with the incoming archive.

### 3. `082a4da` — auth: lazy-import bcrypt so module imports without venv

Polish item flagged in the previous session's handover. `admin_ui/auth.py` had `import bcrypt` at module top level AND a module-scope `_DUMMY_HASH = bcrypt.hashpw(b"unused", bcrypt.gensalt(rounds=12))`. Both ran at import time, meaning any script doing `from admin_ui.auth import ...` from a Python without bcrypt installed (e.g., system python3 vs. the gunicorn venv) crashed at import time before reaching whatever Cloudflare-mode functions it actually wanted.

**Fix:** removed the top-level `import bcrypt`. Added a `_bcrypt()` lazy getter and a `_dummy_hash()` function that computes-and-caches the dummy hash on first call. Routed all four bcrypt callsites (`hash_password`, `verify_password`, `authenticate`'s timing-constant path, the dummy hash itself) through the lazy getter.

Verified end-to-end in the venv: `hash_password` produces a valid `$2b$12$` hash, `verify_password` correctly matches and rejects, `_dummy_hash()` computes bytes and caches.

**Important caveat:** jwt, requests, and flask are still top-level imports in the same file. So this commit only fixes the bcrypt-specific failure mode. Importing admin_ui.auth from system python3 still fails, just at a different line — `ModuleNotFoundError: No module named 'jwt'` instead of bcrypt. To fully decouple from the venv, the same lazy-getter pattern needs to apply to jwt, requests, and flask. I deliberately stopped at bcrypt because previous-Claude's polish item was bcrypt-specific and going further was unjustified scope creep without a concrete use case driving it.

---

## How chroma_db was uploaded — Option B (cloudflared quick tunnel)

The archived prior-session handover doc (`HANDOVER_PHASE3_ARCHIVED_20260409.md`) labeled this "Option B" and recommended it for the no-third-party-storage property. It worked cleanly. Total elapsed time from tunnel-start to teardown was about 6 minutes including the 485 MB transfer over a residential connection.

### Steps that worked

1. **Build the tarball locally** (on Dan's Mac):
   ```bash
   cd "/Users/danielsmith/Claude - RF 2.0"
   tar cf /tmp/chroma_db.tar --exclude='.DS_Store' chroma_db/
   ```
   Produces a ~485 MB tarball with `chroma_db/` as the top-level directory entry.

2. **Start a localhost-only HTTP server** (dedicated terminal, leave running):
   ```bash
   cd /tmp && python3 -m http.server 8000 --bind 127.0.0.1
   ```
   The `--bind 127.0.0.1` is important: it ensures the server is NOT exposed on the LAN, only via the tunnel.

3. **Start a cloudflared quick tunnel** (another dedicated terminal, leave running):
   ```bash
   cloudflared tunnel --url http://127.0.0.1:8000
   ```
   `cloudflared` quick tunnels require no Cloudflare account, are anonymous, and die instantly when you Ctrl-C the daemon. The daemon prints a URL like `https://random-three-words-1234.trycloudflare.com`. This session's URL was `https://defines-strap-rows-files.trycloudflare.com` and is now dead.

4. **Verify the tunnel reaches the tarball end-to-end** before involving Railway:
   ```bash
   curl -sI https://<tunnel-url>/chroma_db.tar
   ```
   Expected: `HTTP/2 200`, `content-type: application/x-tar`, `content-length: 508040704` (~485 MB). The python http.server terminal should also log a `HEAD /chroma_db.tar HTTP/1.1 200` line confirming the request reached the Mac. **Do not skip this step** — it catches tunnel/server/path mismatches before you've spent a Railway redeploy on them.

5. **Set the bootstrap URL on Railway**:
   ```bash
   cd "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone"
   railway variables --set "CHROMA_BOOTSTRAP_URL=https://<tunnel-url>/chroma_db.tar"
   ```

6. **Explicitly trigger a redeploy** — setting a variable does NOT auto-redeploy on the current Railway CLI version (this was a surprise; the older CLI behavior used to do this automatically):
   ```bash
   railway redeploy --yes
   ```

7. **Watch the bootstrap logs** while the new container builds and boots:
   ```bash
   railway logs --deployment
   ```
   You're looking for, in order:
   ```
   [bootstrap] chroma_db empty, downloading bootstrap tarball...
   [bootstrap] download complete (485M), extracting...
   [bootstrap] clearing skeleton chroma_db before extract...
   [bootstrap] chroma_db extracted: 485M, 55 files
   ```
   The "55" is not a typo or a bug — see "Gotchas" below.

8. **Tear everything down immediately on success**, in this order:
   - Ctrl-C the cloudflared tunnel terminal (kills the public URL)
   - Ctrl-C the python http.server terminal
   - `railway variables delete CHROMA_BOOTSTRAP_URL` (verified: this does NOT trigger another redeploy on the current CLI version, which is convenient)
   - `rm /tmp/chroma_db.tar`

9. **Verify the final state on the volume**:
   ```bash
   railway ssh "du -sh /data/chroma_db && find /data/chroma_db -mindepth 1 -type d && find /data/chroma_db -type f | wc -l"
   ```
   Expected: ~485M, 5 UUID-named directories, ~55 files.

10. **The real test**: log into the admin panel at console.drnashatlatib.com, run a meaningful query through the test panel (e.g., "fertility labs AMH" or "progesterone supplementation"), confirm cited chunks come back. This was the verification that this session was actually complete.

### Gotchas discovered this session

- **Railway CLI subcommand names changed.** `railway variables --remove KEY` is wrong; the correct form is `railway variables delete KEY`. The `delete` subcommand also rejects `--skip-deploys` (that flag is only valid on the parent `variables` command, not the `delete` subcommand). But neither auto-triggers redeploys anymore, so `--skip-deploys` is also unnecessary. To force a redeploy after variable changes, use `railway redeploy --yes` explicitly.

- **zsh `status` is a read-only builtin variable.** Polling scripts that do `status=$(railway status --json | ...)` in zsh fail with `read-only variable: status`. Use a different variable name like `state` or `deploy_state`. (Bash doesn't have this collision.)

- **macOS `tar` bundles AppleDouble xattr metadata.** When you `tar cf` a directory on macOS that has filesystem extended attributes (like the "downloaded from internet" flag), the tarball includes parallel `._<filename>` AppleDouble entries. Linux `tar` warns about them on extraction:
  ```
  tar: Ignoring unknown extended header keyword 'LIBARCHIVE.xattr.com.apple.provenance'
  ```
  These warnings are harmless. The `._*` files do get extracted alongside the real files, so the file count on the Linux side is roughly double the file count on the Mac side (this session: 26 real files → 55 extracted files). **Do not use raw file count as a correctness signal.** Use `find -mindepth 1 -type d` (subdirectory count) and the SQLite `SELECT COUNT(*) FROM collections` query as ground truth.

- **The skeleton-sqlite-on-empty-volume bug** (see commit `52d66da` description above). Any future code path that bootstraps a ChromaDB volume must NOT use a naive "directory non-empty" guard. Use a subdirectory check or check for HNSW binary index files specifically.

- **`railway logs --deployment` shows only the currently-active deployment's logs**, and exits when you've read them all (it's not a follow). To watch a deploy come up live, either re-run the command after the deploy state flips to SUCCESS, or use `railway logs` (no `--deployment`) which is a follow.

---

## What's NOT done (non-blocking, deferred)

### 1. Rotate the exposed API keys (DAN-ONLY, ~5 minutes)

In an earlier session (before this one), a screenshot of Railway's Raw Editor view captured the full plaintext values of `ANTHROPIC_API_KEY` (key starts `sk-ant-api03-DeG5-`) and `OPENAI_API_KEY` (key starts `sk-proj-1HMwyxeGkUDgeD8ub`). No third party is known to have seen the screenshot, but standard hygiene says rotate. **Both keys are still the original values on Railway** as of this handover.

This task cannot be Claude-automated because it requires logging into the Anthropic Console and OpenAI Platform with Dan's credentials and 2FA. The sequence per provider:

1. Anthropic Console → Settings → API Keys → create a new key (name it something like `rf-nashat-clone-railway-apr2026`), copy the new value, **don't delete the old key yet**
2. Railway dashboard → diligent-tenderness → rf-nashat-clone → Variables (use the standard Variables UI, NOT the Raw Editor — the Raw Editor is what got these screenshotted in the first place) → update `ANTHROPIC_API_KEY` to the new value
3. Wait for Railway to auto-rebuild and finish (~2-3 min)
4. Hit the admin panel and run a test query that touches Claude (any query will, since the rag_server pipes results through Sonnet) — confirm it works
5. Once verified, go back to the Anthropic Console and revoke the old key
6. Repeat the same 5 steps for OpenAI at platform.openai.com/api-keys for the key starting `sk-proj-1HMwyxeGkUDgeD8ub`
7. Check both providers' usage dashboards for anomalous spend in the last ~24h. If no anomalies, you're done.

### 2. Investigate the rf_reference_library mystery chunks

The SQLite count after the upload showed 584 chunks in the `rf_reference_library` collection. This contradicts userMemories, which said this collection's content (A4M Fertility Certification course material) was the next active task and not yet built. Possibilities:

- A past session partially ingested 584 chunks of A4M material and the memory wasn't updated to reflect it
- It's stale test data from an early experiment
- Dan or a prior agent built it and the memory simply didn't capture it

To investigate (when convenient, not blocking anything):
- Run `railway ssh "python3 -c 'import sqlite3; c=sqlite3.connect(\"/data/chroma_db/chroma.sqlite3\"); print(c.execute(\"SELECT * FROM collection_metadata WHERE collection_id=(SELECT id FROM collections WHERE name=\"rf_reference_library\")\").fetchall())'"` to see metadata
- Run a test query against an agent that references rf_reference_library and inspect what the chunks look like
- Compare against the local source A4M material to see if the chunks match recent ingestion or look like test data

This does not affect any user-facing functionality. The `rf_coaching_transcripts` collection (the main one) is fully intact and serving real queries.

### 3. (Future / Maybe) Fully decouple admin_ui.auth from the venv

The `082a4da` commit made bcrypt lazy. If anyone wants `admin_ui.auth` to be importable from a Python that doesn't have the gunicorn venv's deps installed, the same `_pkg_name()` lazy-getter pattern needs to be applied to `jwt`, `requests`, and `flask` (top-level imports near line ~62 of `admin_ui/auth.py`). About 30 minutes of work, mechanical but spans more functions than the bcrypt fix did.

I (this session's Claude) deliberately stopped at bcrypt because the previous session's polish item was bcrypt-specific and going further was unjustified scope creep without a concrete use case. If a future maintenance script needs to import from admin_ui.auth outside the venv, this is the pattern to follow.

### 4. Audit log retention / rotation strategy

The audit log at `/data/audit.jsonl` is currently append-only with no rotation. Over time it'll grow without bound. Not urgent at current usage levels (a handful of events per day, plus startup events on every redeploy), but worth thinking about before this becomes thousands of users hitting the panel daily. Easy fix when needed: a daily cron + logrotate, or a Python helper that rotates by line count.

---

## Known design decisions and architecture facts (so you don't have to re-derive them)

### Two-process architecture via honcho (Procfile.honcho)

The Railway service runs TWO gunicorn processes managed by honcho, not one:
- `admin.1` — the admin UI Flask app, listening on `0.0.0.0:8180` (the public port that Cloudflare Access routes to)
- `rag.1` — the rag_server Flask app, listening on `127.0.0.1:5051` (localhost-only, no external exposure)

The admin UI proxies test queries internally to the rag_server via `RAG_SERVER_URL=http://localhost:5051`. This split exists because the rag_server has no auth of its own — its localhost binding IS its security boundary. Anything that needs to talk to the rag_server has to go through the admin UI's auth-gated endpoints.

**If you ever need to change ports**, both `Procfile.honcho` and the `RAG_SERVER_URL` env var have to change in lockstep, and the Cloudflare custom domain routing has to point at the admin UI's port (8180), not the rag_server's.

### Why Procfile.honcho instead of plain Procfile

Railway auto-detects a plain `Procfile` and tries to split it into multiple services automatically (one process per Procfile line). That's fine for most apps but it broke this architecture because it would have put rag_server on its own externally-routable hostname, defeating the localhost-binding security model. Renaming to `Procfile.honcho` and invoking it explicitly via `bootstrap.sh && honcho start -f Procfile.honcho` from `railway.json`'s startCommand sidesteps the auto-detection. See commit `4763c72`.

### Why CHROMA_DB_PATH is an env var

Set to `/data/chroma_db` in production via the Railway env var, defaults to `./chroma_db` (relative) for local dev. This lets the same code run both on the Railway persistent volume mount and on Dan's Mac without code changes. The `bootstrap.sh` script honors the env var; rag_server.py honors it; the admin UI test panel honors it. If you need to point at a different path, change the env var and redeploy.

### Cloudflare Access JWT verification, not just header trust

`admin_ui/auth.py` does NOT trust the `Cf-Access-Authenticated-User-Email` header by itself — that header could be forged by anyone who reaches the raw Railway URL directly (bypassing Cloudflare). Instead, every request re-verifies the `Cf-Access-Jwt-Assertion` header against Cloudflare's JWKS endpoint:

1. Fetch `https://reimagined-health.cloudflareaccess.com/cdn-cgi/access/certs` (cached for 1 hour by PyJWKClient)
2. Verify the JWT signature
3. Verify the `aud` claim matches `CLOUDFLARE_ACCESS_AUD`
4. Verify the `iss` claim matches `https://reimagined-health.cloudflareaccess.com`
5. Extract the verified `email` claim
6. Look up that email in `/data/admin_users.json`

If any of those steps fail, the request is rejected. The `_unauthorized` sentinel pattern in `_cloudflare_user_from_request()` distinguishes "not signed in at all" (401) from "signed in via Cloudflare but email not in our allowlist" (403 + audit log entry).

### Current loading behavior of collections

`rag_server.py` does NOT eagerly load all collections at startup. It eagerly loads `rf_reference_library` (which is why that one shows up in startup logs as `loaded collection 'rf_reference_library': 584 chunks`). Other collections including `rf_coaching_transcripts` are loaded lazily on first query that touches them.

This was a brief source of confusion this session — the absence of `rf_coaching_transcripts` from startup logs looked suspicious, but Dan's live test query confirmed the collection was reachable and working. **Do not "fix" this by making all collections eager-load** unless you have a reason to; lazy loading saves startup time and only matters if a startup health check needs to validate every collection up front.

---

## Key identifiers (all current as of this handover)

```
RAILWAY
  Project:           diligent-tenderness
  Project ID:        878965fa-7f50-4a63-a442-6e5b3a7a25d9
  Service:           rf-nashat-clone
  Service ID:        1a89b9b1-e498-4577-9cf8-3fbdbfb16ca0
  Environment:       production (954f2ad8-51df-4377-b829-1342b85bcb57)
  Volume ID:         00a6bdc8-475e-4eff-b162-1cd9f8726e74
  Volume mount:      /data
  Region:            us-east4-eqdc4a

GITHUB
  Repo:              dps1607/rf-nashat-clone (private)
  Branch:            main
  Latest deployed:   082a4da

CLOUDFLARE
  Account:           info@reimagined-health.com
  Account ID:        3668a7b75fc8afcd5f98146816668258
  Team domain:       reimagined-health.cloudflareaccess.com
  Access AUD:        c8d33662919e0e9a9ce2a3c3506c7ef5c4beee7ab631083912e98140e114c0bb
  Access app:        RF Admin Panel
  DNS zone:          drnashatlatib.com
  Custom hostname:   console.drnashatlatib.com (CNAME → 8acwb20q.up.railway.app, orange cloud ON)

ALLOWLISTED USERS
  dan@reimagined-health.com
  znahealth@gmail.com (Dr. Nashat Latib)

LOCAL SOURCE DATA (Dan's Mac, untouched this session)
  /Users/danielsmith/Claude - RF 2.0/chroma_db/             (485 MB, source of truth)
  /Users/danielsmith/Claude - RF 2.0/chroma_db_backup_20260405/
  /Users/danielsmith/Claude - RF 2.0/chroma_db_backup_pre_v2/
  /Users/danielsmith/Claude - RF 2.0/chroma_db_backup_with_names/
```

## Railway env vars (production, end of session state)

```
CONFIG_DIR=/data/config
ADMIN_USERS_PATH=/data/admin_users.json
CHROMA_DB_PATH=/data/chroma_db
DEFAULT_AGENT=nashat_sales
ADMIN_PASSWORD=<set, currently unused — Cloudflare mode active>
ADMIN_SESSION_SECRET=<set, currently unused — Cloudflare mode active>
ANTHROPIC_API_KEY=<set, NEEDS ROTATION — see "What's NOT done" #1>
OPENAI_API_KEY=<set, NEEDS ROTATION — see "What's NOT done" #1>
RAG_SERVER_URL=http://localhost:5051
CLOUDFLARE_ACCESS_ENABLED=true
CLOUDFLARE_ACCESS_TEAM_DOMAIN=reimagined-health.cloudflareaccess.com
CLOUDFLARE_ACCESS_AUD=c8d33662919e0e9a9ce2a3c3506c7ef5c4beee7ab631083912e98140e114c0bb
AUDIT_LOG_PATH=/data/audit.jsonl
```

`CHROMA_BOOTSTRAP_URL` was set briefly during this session (to the cloudflared tunnel URL) and deleted via `railway variables delete CHROMA_BOOTSTRAP_URL` after successful extraction. Confirmed gone via `railway variables | grep CHROMA_BOOTSTRAP` returning nothing.

## Recent commit history (top of main)

```
082a4da auth: lazy-import bcrypt so module imports without venv
52d66da bootstrap: tighten chroma_db guard and clear skeleton before extract
529e0a0 bootstrap: add chroma_db download via CHROMA_BOOTSTRAP_URL
824de58 docs: add Phase 3 deployment handover with chroma_db upload playbook
d5f9e17 Phase 3.5: Cloudflare Access + audit log + ruamel.yaml + security hardening
4763c72 Phase 3: rename Procfile to Procfile.honcho to prevent Railway auto-split
beaa8db Phase 3: prepare for Railway deployment
```

---

## Where to look in the codebase

```
rf-nashat-clone/
├── bootstrap.sh                           # Container startup, runs before honcho. Seeds /data/config YAMLs from /app/config on first deploy. Bootstraps /data/chroma_db if CHROMA_BOOTSTRAP_URL is set. Idempotent.
├── Procfile.honcho                        # honcho process definitions for admin.1 and rag.1
├── railway.json                           # Railway service config; startCommand calls bootstrap.sh && honcho start -f Procfile.honcho
├── config/
│   ├── nashat_sales.yaml                  # Sales agent config (seeded into /data/config on first deploy, then editable via UI)
│   └── nashat_coaching.yaml               # Coaching agent config (same)
├── admin_ui/
│   ├── auth.py                            # Two-mode auth: Cloudflare Access (production) or local bcrypt (dev). bcrypt is now lazy-imported (commit 082a4da).
│   ├── audit.py                           # Audit log writer (writes to AUDIT_LOG_PATH as JSONL)
│   ├── add_user.py                        # CLI tool to seed admin_users.json on the volume (called via railway shell)
│   └── app.py                             # Flask routes including /test for the inline test query panel
├── rag_server.py                          # The actual RAG pipeline; loads from CHROMA_DB_PATH; not externally exposed
└── HANDOVER_PHASE3_COMPLETE.md            # This document — read first when starting a new session
└── HANDOVER_PHASE3_ARCHIVED_20260409.md   # Earlier (pre-upload) handover; useful for the original Option A (R2) playbook and historical context
```

---

## Resume prompt for the next Claude session

Open a new chat and paste this:

> Resume RF Railway deployment work. Phase 3.5 is fully live and verified at https://console.drnashatlatib.com — both authorized users can log in, audit log is working, agent YAML editor is working, and chroma_db is on the Railway volume with the full rf_coaching_transcripts collection (9,224 chunks) returning real cited chunks on test queries.
>
> Read `/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone/HANDOVER_PHASE3_COMPLETE.md` first — it has the full state, the architecture decisions, the gotchas discovered last session, and the two non-blocking loose ends.
>
> The two loose ends are: (1) rotate ANTHROPIC_API_KEY and OPENAI_API_KEY on Railway (Dan-only, ~5 min, requires Anthropic Console + OpenAI Platform + Railway dashboard logins) and (2) investigate why rf_reference_library has 584 chunks when userMemories said it was unbuilt (non-blocking, satisfy curiosity / data hygiene).
>
> If Dan wants to move on to new work — possible next directions include: ingesting `rf_published_content` (blogs + IG posts), building the `rf_reference_library` properly if the existing 584 chunks are stale, working on the Nashat app feature spec, the Reddit marketing companion, or the gut health ebook. Ask Dan which thread to pull.
>
> Don't redo any of this session's work. The bootstrap script's chroma_db guard is correctly hardened (commit 52d66da) — do not loosen it back to a naive `ls -A` test. The bcrypt lazy import (commit 082a4da) is correct as-is — only extend the lazy-import pattern to jwt/requests/flask if you have a concrete use case driving it.

---

*End of handover. If you're a future Claude reading this: welcome. Dan has been very patient with us today. Pay it forward.*
