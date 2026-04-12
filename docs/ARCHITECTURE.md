# RF Nashat RAG — Architecture (stable reference)

Updated in place only when the design itself changes. Not a session log.

## Business context
- Reimagined Fertility (RF) / Reimagined Health — digital therapeutics for women's cyclical health, fertility-first.
- B2B2C: IVF/IUI clinics + insurance. Long-term goal: required pre-ART intervention, $1B+ valuation.
- Core IP: 25 proprietary Qualitative Pattern Types (QPTs) for BBT interpretation.
- Data assets: 5M+ words of coaching transcripts, 716 historical clients (~80 active), 54 with before/after labs, 5 documented pregnancies.

## Two-agent design
1. **Public sales agent** — `rf_published_content` + `rf_reference_library` only. No client data. HIPAA boundary enforced here by design.
2. **Internal coaching agent** (behind paywall) — all three collections including `rf_coaching_transcripts`.

## Collections
- `rf_coaching_transcripts` — ACTIVE. 9,224 chunks. 3,041 tagged with client RFIDs. LLM-powered (Haiku) context-aware chunking. 573-word mean. v3 is the proven approach.
- `rf_reference_library` — PLANNED. A4M fertility course (slides + transcripts) first. Path: local Mac sync (Drive cross-account failed previously).
- `rf_published_content` — PLANNED. Blogs, IG posts.
- `rf_coaching_episodes` — FUTURE. Zoom video pipeline (see BACKLOG.md).

## Stack
- ChromaDB at `/Users/danielsmith/Claude - RF 2.0/chroma_db/` (outside repo).
- Embeddings: OpenAI `text-embedding-3-large`.
- Chunking LLM: Claude Haiku.
- RAG response LLM: Claude Sonnet.
- Flask RAG server: port 5050. Config-driven, Pydantic schema as single source of truth, hot reload via watchdog.
- Admin UI: port 5052. Brand-styled, bcrypt auth, full YAML editor, inline test panel.
- Agent configs: `nashat_sales.yaml`, `nashat_coaching.yaml`. A4M course analysis is a named mode in both.
- Frontend: Flutter. Brand: Santorini script, copper/ivory/navy.
- Deployment: Railway (not Vercel — serverless incompatible with long-lived Flask + persistent Chroma).
- Repo: `github.com/dps1607/rf-nashat-clone`, branch `main`.

## Hard guardrails
- **Never reference Dr. Christina** in any Nashat agent response.
- **Exclude** Kelsey Poe and Erica from RAG retrieval results (internal staff).
- **Dr. Chris** stays internal only (speaker diarization), never surfaced to users.
- Public agent **must never** access `rf_coaching_transcripts` (HIPAA boundary).
- Client coaching data is not HIPAA-regulated but requires professional discretion.

## People
- Dr. Nashat Latib — lead practitioner, AI clone subject, planned 2nd admin user.
- Dan Smith — founder, sole current admin.

## Credential policy
Never store API keys, tokens, passwords, or credential strings in memory or committed files. Ephemeral in chat only. `.env` local, Railway env vars remote.

## Key file paths
- Project root: `/Users/danielsmith/Claude - RF 2.0/`
- Repo: `/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone/`
- ChromaDB: `/Users/danielsmith/Claude - RF 2.0/chroma_db/`
- Google Drive local sync: `/Users/danielsmith/Library/CloudStorage/GoogleDrive-znahealth@gmail.com/Shared drives/`
- Service account JSON (local): `/Users/danielsmith/.config/gcloud/rf-service-account.json` (chmod 600)
- RF 2.0 Drive folder: https://drive.google.com/drive/folders/1H3hs2eQBlksBwPSMn17_nYI75UD-YNCR
- Master spreadsheet ID: `1hzgmL-eV2ac1OM4PpNKBp9INJb9avVAhfH2skL7kIzw`

## Known environment quirks
- Google Drive cross-account search fails for `znahealth@gmail.com` content when authed as `dan@theprofitableleader.com`. Use local sync path.
- Large Python runs: write full script to disk, launch with `start_process`, monitor via `ps aux` + Chroma count (MCP timeout ~4 min).
- Large file writes: chunk via `append`, never single `rewrite`.
- Env vars for child processes: prefix with `source ~/.zshrc &&`.
- Claude Desktop (not browser) is the reliable MCP environment.
