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
- `rf_reference_library` — PLANNED. A4M fertility course (slides + transcripts) first. Path: local Mac sync (Drive cross-account failed previously). Loaded via static-library ingestion path (ADR_005).
- `rf_published_content` — PLANNED. Blogs, IG posts.
- `rf_coaching_episodes` — FUTURE. Zoom video pipeline (see BACKLOG.md).
- `rf_library_index` — PLANNED. Metadata-only registry collection per ADR_002 (file records + library records). Not a content collection. Schema amended 2026-04-12 to support `origin` field and non-Drive file records (see ADR_002 addendum).

## Chunk metadata schema (locked 2026-04-12)
The universal metadata contract for every chunk in every content collection is defined in **ADR_006 (chunk reference contract)**. All loaders — Drive-walk and static-library alike — must produce chunks conforming to that contract.

**Core required fields on every chunk:** `chunk_id`, `text`, `collection`, `library_name`, `entry_type`, `origin`, `tier`, `source_id`, `source_name`, `chunk_index`, `ingested_at`, plus **48 `marker_*` boolean flags** (one per BUILD_GUIDE §5 marker — see ADR_006 §2a for canonical naming). Marker flags default to `false` and are set to `true` when chunk text discusses that marker.

**Optional fields:** `client_id`, `linked_test_event_id`, `speaker`, `topics`, `recommendations_given`, `type_metadata_json`, `markers_discussed` (display-only string), `qpt_01`–`qpt_25` (forward-compat spec). `client_id` and `linked_test_event_id` must be **null** on non-client-linked content (reference-library, published-content, ig_post) — not fabricated.

**Encoding conventions:**
- **Marker references** use 48 top-level boolean columns, NOT a delimited list. This is mandatory because BUILD_GUIDE §5 marker names have substring collisions (`T3`/`FT3`, `T4`/`FT4`) that make substring filtering unsafe. The `markers_discussed` display string is for rendering only — never for filtering.
- **Unbounded list fields** (`topics`, `recommendations_given`) use pipe-delimited strings with **bookend delimiters** (`"|fertility|amh|"`). Queries must use bookend delimiters too (`$contains: "|fertility|"`) to avoid partial-match bugs.
- **Nested type-specific metadata** uses `type_metadata_json` as a JSON-encoded string (ChromaDB metadata must be scalar).

The `entry_type` enum is locked (ADR_006 §3): `coaching_transcript | reference_transcript | reference_document | published_post | ig_post | dm_exchange | lab_summary | supplement_rec | qpt_reference | coaching_episode`. Adding new values requires an ADR_006 amendment. Same rule for the marker and QPT flag sets.

**Backfill for existing 9,224 `rf_coaching_transcripts` chunks is phased** (ADR_006 §7):
- **Phase 1** — structural annotation only. Sets `entry_type`, `origin`, `tier`, `library_name`, `source_id`, `ingested_at`, and all 48 marker flags to explicit `false`. Cheap, unblocks A4M ingestion. Dan approves before it runs.
- **Phase 2** — marker detection pass. Reads each chunk's text and flips the appropriate `marker_*` flags to `true`. Independent of Phase 1; can run in a dedicated later session. Detection method (regex vs LLM-assisted) decided in the Phase 2 session. Dan approves before it runs.

See **ADR_006** for the full field definitions, per-type `type_metadata_json` expectations, BUILD_GUIDE §7 reconciliation, marker-detection starter kit, and the phased backfill plan.

## Ingestion paths
Two distinct ingestion categories with different lifecycles:
1. **Drive-walked content** (ADR_002) — continuously diffed against a live Google Drive walk via the folder-selection UI and a service-account-driven ingester. Writes file records to `rf_library_index` with `origin: "drive_walk"`. Governs most coaching transcripts, future FKSP curriculum, blog posts, and IG content.
2. **Static libraries** (ADR_005) — one-shot CLI loaders for curated non-Drive content (A4M course materials, future ACOG-style snapshots). Writes file records to `rf_library_index` with `origin: "static_library"`. Not surfaced in the folder-selection UI by design. Loaders own idempotency and re-ingestion semantics.

Both paths write chunks that conform to ADR_006's chunk reference contract. They share the same registry (`rf_library_index`) but through separate code paths; the diff engine and folder-selection UI filter on `origin = "drive_walk"` and do not see static-library records. All loaders should share a canonical `marker_detection.py` module in the ingester package so the 48 marker flags are populated consistently across sources.

## Governing docs
- **`/Users/danielsmith/Claude - RF 2.0/VECTOR_DB_BUILD_GUIDE.md`** — canonical project-level data architecture (unified ID system §2, data source map §3, 44 lab markers §5, vector DB entry schema sketch §7, correlation model §8, client identification §13). Predates the ADR-numbered workflow. ADRs and this ARCHITECTURE.md must stay consistent with it; where they extend or diverge, the ADRs document the divergence explicitly (see ADR_005 context section and ADR_006 §6 reconciliation).
- **ADR_001** — Drive ingestion scope
- **ADR_002** — Library registry, continuous diff, library-aware agents (amended 2026-04-12 for `origin` field)
- **ADR_003** — Canva dedup
- **ADR_004** — Folder-selection UI
- **ADR_005** — Static libraries (non-Drive ingestion)
- **ADR_006** — Chunk reference contract (universal metadata schema; 48 marker boolean flags; phased backfill)

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
- **Static-library loaders must verify their source contains no client-identifying data before ingesting** (ADR_005 Consequences). Reference-tier content is public-agent-eligible by default, so loader authors own this check.
- **Marker flags must be written as explicit `false`, not omitted.** Missing Chroma metadata fields become `None` and cannot be filtered on — this silently breaks retrieval. Applies to all 48 `marker_*` columns on every chunk.

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
