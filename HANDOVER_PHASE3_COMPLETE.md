# Phase 3 Railway Deployment — Handover (April 9, 2026)

## TL;DR

The Phase 3.5 admin panel is **live and fully working** at `https://console.drnashatlatib.com`. Both authorized users can log in with Google OAuth via Cloudflare Access, and every layer of the security stack has been verified end-to-end. The **only** remaining task is uploading `chroma_db` to the Railway volume so test queries return real results — and that task is **paused intentionally** because the only quick upload paths involve exposing confidential data, which is unacceptable.

When you resume, you have one job: upload chroma_db using a method that keeps the data private at every step. Do not use any third-party file host (transfer.sh, file.io, GitHub releases, bashupload, oshi, 0x0, etc.) under any circumstance. Even if the repo is "private," release assets are not the same security boundary as repo code and should be assumed public for confidential data purposes.


## What's live in production

| Component | Status | Notes |
|---|---|---|
| Railway service `rf-nashat-clone` | ✅ Online | UUID `1a89b9b1-e498-4577-9cf8-3fbdbfb16ca0` in project `diligent-tenderness` |
| Custom domain | ✅ `console.drnashatlatib.com` → port 8180 | CNAME to `8acwb20q.up.railway.app`, proxied through Cloudflare orange cloud |
| Cloudflare Access | ✅ Active | App `RF Admin Panel`, AUD `c8d33662919e0e9a9ce2a3c3506c7ef5c4beee7ab631083912e98140e114c0bb` |
| Google OAuth IdP | ✅ Verified | Project `rf-admin-auth` in Google Cloud, allowed users `dan@reimagined-health.com` and `znahealth@gmail.com` |
| Phase 3.5 code | ✅ Deployed | Commit `d5f9e17` on `main`, deployed as Railway `7dd65a34-87af-4c9e-a5a0-16453351e974` |
| Persistent volume | ✅ Mounted | UUID `00a6bdc8-475e-4eff-b162-1cd9f8726e74` at `/data`, region us-east4-eqdc4a, ~4.5GB free |
| `/data/admin_users.json` | ✅ Populated | Both `dan@reimagined-health.com` and `znahealth@gmail.com` as admin |
| `/data/audit.jsonl` | ✅ Writing | startup, login_success, access_denied, admin_user_added, test_query events all verified |
| `/data/config/nashat_sales.yaml` | ✅ Seeded | From repo, editable via admin UI YAML editor |
| `/data/config/nashat_coaching.yaml` | ✅ Seeded | From repo, editable via admin UI YAML editor |
| `/data/chroma_db` | ❌ **EMPTY** | This is the one remaining task. See "Resume task" below. |

## What's NOT done and needs your next session

### 1. Upload chroma_db (the only remaining work)

The local source is at `/Users/danielsmith/Claude - RF 2.0/chroma_db` — 485 MB, 26 files including the 242 MB `chroma.sqlite3` and the HNSW shard binaries. Contains the `rf_coaching_transcripts` collection (9224 chunks) and embeddings made with OpenAI `text-embedding-3-large`. Until this is on the Railway volume, the inline test panel returns 0 chunks for any query and the rag_server logs `collection 'rf_coaching_transcripts' not available: Collection [...] does not exist`.

**The chroma_db contains private and confidential client coaching data.** Treat it the same way you would treat a HIPAA-covered dataset even though we've established RF is trade-secret-protected rather than HIPAA-covered. The transport method must keep it confidential at every hop.

### 2. Rotate the API keys exposed earlier in this session

In the prior chat transcript, I screenshotted Railway's Raw Editor view, which displays env var values in plaintext. The screenshot captured the full `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` values. **Both should be rotated** before the next active development session, even though no third party should have read this conversation. The current Railway env vars still hold the original keys.

- Anthropic: <https://console.anthropic.com/settings/keys> — find the key starting `sk-ant-api03-DeG5-`, revoke, create new, paste new value into Railway via the standard Variables UI (NOT the Raw Editor)
- OpenAI: <https://platform.openai.com/api-keys> — find the key starting `sk-proj-1HMwyxeGkUDgeD8ub`, revoke, create new, paste new value into Railway

### 3. (Optional) Lazy-import bcrypt in admin_ui/auth.py

Minor code-quality issue surfaced this session. `admin_ui/auth.py` has `import bcrypt` at module top level. This is fine for the running gunicorn workers (which use `/opt/venv/bin/python` where bcrypt is installed via Nixpacks), but it means scripts that import from `admin_ui.auth` will fail if invoked from outside the venv. Move `import bcrypt` inside the functions that use it (`hash_password`, `verify_password`, `add_user` username-mode branch). Not blocking — just a polish item.


## Resume task: how to actually upload chroma_db privately

This section is the playbook for the next session. Pick option 1 first, fall back through the list.

### Forbidden methods (DO NOT USE)

These were attempted in the prior session and either failed technically or pose unacceptable confidentiality risk:

- **`tar cf - chroma_db | railway ssh "tar xf -"`** — fails because Railway's SSH WebSocket allocates a pty and GNU tar refuses to read binary archives from a terminal
- **`base64 < chroma_db.tar | railway ssh "... | base64 -d | tar xf -"`** — failed with `WebSocket error: IO error: Operation timed out (os error 60)` partway through. Railway's SSH WebSocket appears to have a transfer-size limit that 485 MB exceeds.
- **transfer.sh** — service has been down/unreliable, returned connection refused
- **0x0.st** — disabled uploads due to AI bot spam
- **bashupload.com** — returned HTTP 404
- **file.io** — uploaded at <0.1% per minute, effectively dead
- **GitHub Releases on `dps1607/rf-nashat-clone`** — published a release for ~19 minutes during the prior session before realizing it exposed private data on a third-party platform; release was deleted with `gh release delete v0.1-data --yes --cleanup-tag` and verified gone via API. **Do not redo this.** Even though the repo is private, release assets are a separate trust boundary and storing confidential coaching data on github.com — even briefly, even on a private repo — is not acceptable.
- **Any public file drop service** (regardless of name or provider claims about privacy)
- **Any service that requires uploading to a third-party server before the container fetches it**

### Approved methods

#### Option A — Cloudflare R2 with pre-signed URL (RECOMMENDED)

You already have a Cloudflare account (`info@reimagined-health.com`, account ID `3668a7b75fc8afcd5f98146816668258`) used for Cloudflare Access. R2 is Cloudflare's object storage, fully under your control. Setup:

1. Create an R2 bucket (e.g. `rf-deployment-data`) in your Cloudflare dashboard. R2 buckets are private by default — bucket contents are NOT publicly accessible.
2. Generate an R2 API token with read/write access to the bucket.
3. Install `rclone` or `aws-cli` configured for R2 endpoint.
4. Upload `/Users/danielsmith/Claude - RF 2.0/chroma_db.tar` (recreate it first with `cd "/Users/danielsmith/Claude - RF 2.0" && tar cf /tmp/chroma_db.tar --exclude='.DS_Store' chroma_db/`) to the bucket.
5. Generate a **pre-signed download URL** with a 1-hour expiry for that one specific object. Pre-signed URLs include a signature parameter that authorizes a single download to anyone holding the URL, but they expire automatically.
6. Add the pre-signed URL to Railway as `CHROMA_BOOTSTRAP_URL` env var.
7. Re-add the `bootstrap.sh` chroma_db download block (see "Reverted bootstrap.sh changes" section below for the exact code that was rolled back).
8. Push to `main` → Railway rebuilds → `bootstrap.sh` curls the tarball from R2, extracts to `/data/chroma_db`, the URL expires shortly after.
9. After verifying the upload worked: `railway variable delete CHROMA_BOOTSTRAP_URL` to remove the pre-signed URL from env vars, and either delete the R2 object or leave it for future re-deploys.

**Why this is safe:** the data lives in your own Cloudflare account on a private bucket. The only thing that touches the public internet is a single 1-hour pre-signed URL that authorizes one download. After expiry, the URL is dead. No third party ever holds or sees the data. R2's egress to Railway will be fast (both are in the same datacenter regions for most of the US East deployments).

**Estimated time:** 30 minutes including R2 setup the first time, ~5 minutes on subsequent uses.

#### Option B — `cloudflared tunnel --url localhost:8000` (FAST, ZERO PERSISTENT INFRASTRUCTURE)

`cloudflared` is Cloudflare's tunnel daemon. The "quick tunnel" feature lets you expose a localhost port via a one-shot HTTPS URL that auto-expires when you Ctrl+C the daemon. The data never lives on any third-party server — it streams directly from your Mac to the Railway container through Cloudflare's edge.

1. Recreate the tarball: `cd "/Users/danielsmith/Claude - RF 2.0" && tar cf /tmp/chroma_db.tar --exclude='.DS_Store' chroma_db/`
2. Terminal 1: `cd /tmp && python3 -m http.server 8000 --bind 127.0.0.1` (binds to localhost only, never exposed on your LAN)
3. Terminal 2: `cloudflared tunnel --url http://127.0.0.1:8000` (install with `brew install cloudflared` if not present, no account needed for quick tunnels)
4. cloudflared prints a one-shot HTTPS URL like `https://random-words-1234.trycloudflare.com`
5. Terminal 3: `railway ssh "cd /data && rm -rf chroma_db && curl -fsSL https://random-words-1234.trycloudflare.com/chroma_db.tar -o /tmp/chroma.tar && tar xf /tmp/chroma.tar && rm /tmp/chroma.tar && du -sh chroma_db && find chroma_db -type f | wc -l"`
6. **Immediately Ctrl+C the cloudflared tunnel** (Terminal 2) and the Python server (Terminal 1). The quick tunnel URL is now dead.
7. `rm /tmp/chroma_db.tar` to clean up the local tarball.
8. `railway redeploy --yes` to bounce the workers so gunicorn re-opens ChromaDB with the populated data.

**Why this is safe:** the data is in transit for ~3-5 minutes total. The cloudflared quick tunnel URL is unguessable (random subdomain), short-lived (you control when it dies), and never logged by third parties for content. Your Python HTTP server is bound to 127.0.0.1 so it's only accessible via the tunnel, not your LAN. After Ctrl+C the tunnel is gone and the URL returns 502.

**Estimated time:** 10 minutes if `cloudflared` is already installed.

#### Option C — Investigate `railway volume upload` or `railway run`

When this session was active, `railway volume --help` was not checked. Newer Railway CLI versions (v4.30+) may have added a direct volume upload command. Check `railway --version` and `railway volume --help` first. If a direct volume upload exists, use it — it's the simplest path because it's first-party and uses Railway's own ingress instead of an SSH WebSocket.

Similarly, `railway run` executes a command in a fresh ephemeral container with the volume mounted. It's worth checking whether `cat /tmp/chroma_db.tar | railway run -- bash -c 'tar xf - -C /data'` succeeds where `railway ssh` failed. The pty allocation behavior is different for `run` vs `ssh`.

#### Option D (LAST RESORT) — Manual `git lfs` to private repo + bootstrap pull with token

Only if A, B, and C all fail. Add `chroma_db/*` to git-lfs tracking, commit and push to main (LFS keeps the binaries out of the regular git history but in GitHub's LFS storage, which is gated by the same auth as the repo). Bootstrap.sh would `git lfs pull` during container startup using a deploy token. This is operationally complex and pulls confidential data through git-lfs's storage, which is more attack surface than R2. Avoid unless there's no choice.


## Reverted bootstrap.sh changes (re-add when ready to upload)

This is the exact code block that was added to `bootstrap.sh` and then `git reset --hard`'d during the prior session. Re-add it between the existing "1. seed configs" and "2. check admin_users" sections when you're ready to do the chroma_db upload via Option A or B. The block is idempotent (skips if `/data/chroma_db` already exists and is non-empty) and fails gracefully (if download fails, app still boots normally).

```bash
# 1b. Bootstrap chroma_db on first deploy by downloading a tarball from a
#     URL specified via CHROMA_BOOTSTRAP_URL env var. On subsequent deploys,
#     volume's copy is source of truth and we leave it alone. Failure is
#     non-fatal — app still boots with empty chroma_db, which is the
#     current baseline state.
CHROMA_DB_PATH="${CHROMA_DB_PATH:-/data/chroma_db}"
CHROMA_BOOTSTRAP_URL="${CHROMA_BOOTSTRAP_URL:-}"

if [ -d "$CHROMA_DB_PATH" ] && [ -n "$(ls -A "$CHROMA_DB_PATH" 2>/dev/null)" ]; then
    echo "[bootstrap] chroma_db already populated at $CHROMA_DB_PATH, leaving alone"
elif [ -n "$CHROMA_BOOTSTRAP_URL" ]; then
    echo "[bootstrap] chroma_db empty, downloading bootstrap tarball..."
    mkdir -p "$(dirname "$CHROMA_DB_PATH")"
    TMPTAR="$(mktemp /tmp/chroma_bootstrap.XXXXXX.tar)"
    if curl -fsSL --retry 3 --retry-delay 5 -o "$TMPTAR" "$CHROMA_BOOTSTRAP_URL"; then
        TARSIZE="$(du -h "$TMPTAR" | cut -f1)"
        echo "[bootstrap] download complete ($TARSIZE), extracting..."
        if (cd "$(dirname "$CHROMA_DB_PATH")" && tar xf "$TMPTAR"); then
            FILECOUNT="$(find "$CHROMA_DB_PATH" -type f 2>/dev/null | wc -l | tr -d ' ')"
            FINALSIZE="$(du -sh "$CHROMA_DB_PATH" 2>/dev/null | cut -f1)"
            echo "[bootstrap] chroma_db extracted: $FINALSIZE, $FILECOUNT files"
        else
            echo "[bootstrap] ERROR: tar extraction failed"
        fi
        rm -f "$TMPTAR"
    else
        echo "[bootstrap] ERROR: download failed from $CHROMA_BOOTSTRAP_URL"
        rm -f "$TMPTAR"
    fi
else
    echo "[bootstrap] chroma_db empty and CHROMA_BOOTSTRAP_URL not set, skipping"
fi
```

The container has `curl 8.5.0`, `tar 1.35`, and ~4.5GB free on `/data` — verified this session. No additional dependencies needed.

## Audit log evidence (confirms everything works)

From `railway ssh "cat /data/audit.jsonl"` during the prior session:

```json
{"timestamp": "2026-04-09T06:20:15+00:00", "event": "startup", "user": "-system-", "details": {"cloudflare_access_enabled": true, "config_dir": "/data/config", "rag_server_url": "http://localhost:5051"}}
{"timestamp": "2026-04-09T13:10:37+00:00", "event": "access_denied", "user": "dan@reimagined-health.com", "ip": "157.52.76.78", "details": {"path": "/"}}
{"timestamp": "2026-04-09T13:23:09+00:00", "event": "admin_user_added", "user": "-system-", "details": {"email": "dan@reimagined-health.com", "role": "admin"}}
{"timestamp": "2026-04-09T13:23:09+00:00", "event": "admin_user_added", "user": "-system-", "details": {"email": "znahealth@gmail.com", "role": "admin"}}
{"timestamp": "2026-04-09T13:43:14+00:00", "event": "test_query", "user": "dan@reimagined-health.com", "ip": "157.52.76.78", "details": {"mode": "default", "q_len": 62, "q_preview": "Can you review my labs and let me know if I can get pregnant ?"}}
```

Every layer verified:
- `startup` with `cloudflare_access_enabled: true` proves the env var is being read
- `access_denied` proves Cloudflare → JWT → JWKS verification → email extraction → admin_users.json lookup → 403 path works
- `admin_user_added` proves the CLI tool wrote to the volume successfully
- `test_query` proves the full logged-in flow works (just returned 0 chunks because chroma_db is empty)
- Audit log correctly logs `q_preview` but not the response (privacy by design)


## Key identifiers for next session

```
Railway project:     diligent-tenderness
Railway project ID:  878965fa-7f50-4a63-a442-6e5b3a7a25d9
Railway service:     rf-nashat-clone
Railway service ID:  1a89b9b1-e498-4577-9cf8-3fbdbfb16ca0
Railway environment: production (954f2ad8-51df-4377-b829-1342b85bcb57)
Railway volume ID:   00a6bdc8-475e-4eff-b162-1cd9f8726e74 mounted at /data
Railway region:      us-east4-eqdc4a

GitHub repo:         dps1607/rf-nashat-clone (private)
Latest deployed:     d5f9e17 (Phase 3.5 on main, no commits ahead)

Cloudflare account:  info@reimagined-health.com
CF account ID:       3668a7b75fc8afcd5f98146816668258
CF team domain:      reimagined-health.cloudflareaccess.com
CF Access AUD:       c8d33662919e0e9a9ce2a3c3506c7ef5c4beee7ab631083912e98140e114c0bb
CF Access app:       RF Admin Panel
DNS zone:            drnashatlatib.com
Custom hostname:     console.drnashatlatib.com (CNAME → 8acwb20q.up.railway.app, orange cloud ON)

Allowlist emails:    dan@reimagined-health.com, znahealth@gmail.com
```

## Railway env vars currently set on the production service

These are confirmed live as of end of session:

```
CONFIG_DIR=/data/config
ADMIN_USERS_PATH=/data/admin_users.json
CHROMA_DB_PATH=/data/chroma_db
DEFAULT_AGENT=nashat_sales
ADMIN_PASSWORD=<set, currently unused in Cloudflare mode>
ADMIN_SESSION_SECRET=<set, signs Flask session cookies in local mode, unused in Cloudflare mode>
ANTHROPIC_API_KEY=<set, NEEDS ROTATION per "What's NOT done" #2>
OPENAI_API_KEY=<set, NEEDS ROTATION per "What's NOT done" #2>
RAG_SERVER_URL=http://localhost:5051
CLOUDFLARE_ACCESS_ENABLED=true
CLOUDFLARE_ACCESS_TEAM_DOMAIN=reimagined-health.cloudflareaccess.com
CLOUDFLARE_ACCESS_AUD=c8d33662919e0e9a9ce2a3c3506c7ef5c4beee7ab631083912e98140e114c0bb
AUDIT_LOG_PATH=/data/audit.jsonl
```

(Plus Railway's auto-injected `PORT`, `RAILWAY_*`, etc.)

`CHROMA_BOOTSTRAP_URL` was set briefly during the prior session and then deleted via `railway variable delete CHROMA_BOOTSTRAP_URL`. Confirmed gone.

## Resume prompt for next Claude session

Open a new chat and paste this:

> Resume RF Railway deployment. Phase 3.5 is fully live at console.drnashatlatib.com. Both Dan and Nashat can log in via Cloudflare Access + Google OAuth. Audit log is working. Only remaining task is uploading chroma_db to the Railway volume so RAG queries return real results.
>
> Read the handover doc at /Users/danielsmith/Claude - RF 2.0/rf-nashat-clone/HANDOVER_PHASE3_COMPLETE.md before doing anything. Critical constraint: chroma_db contains private/confidential coaching client data. Do NOT use any third-party file host (transfer.sh, file.io, GitHub releases, bashupload, etc.). Use Cloudflare R2 with a pre-signed URL OR a cloudflared quick tunnel — both are documented in the handover doc with full step-by-step instructions.
>
> Also rotate ANTHROPIC_API_KEY and OPENAI_API_KEY on Railway before doing anything else — they were exposed in a screenshot in a prior session.
