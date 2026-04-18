# Drift Recovery — Session 28-extended scope F (2026-04-17)

**Status:** Drift analysis + recovery plan. Informal, session-scoped.
**Trigger:** Dan surfaced: *"go back to our pilot and other docs. isn't there a rag build path first? where are our drift controls?"*
**Response:** Read ADR_001–006 + HANDOVER_INTERNAL_EDUCATION_BUILD.md. Found significant alignment gaps between s28 scopes A/C/D/E output and the canonical architecture decided 2026-04-10 through 2026-04-12.

This doc records what I found, what drifted, what to correct now, and what to defer to s29+.

---

## Canonical architecture (what the ADRs say)

Sources: `HANDOVER_INTERNAL_EDUCATION_BUILD.md` (April 10 master plan), ADR_001–006 (April 11–12 refinements).

### Four content collections + registry

| Collection | Tier | Purpose |
|---|---|---|
| `rf_reference_library` | reference | External approved content (A4M, ACOG, future curated) |
| `rf_coaching_transcripts` | paywalled | Transcribed coaching-call content |
| `rf_internal_education` | paywalled | **Course curriculum (FKSP / TFF / Preconception Detox)** |
| `rf_published_content` | published | Public-facing: blogs, lead magnets, masterclasses, IG, DMs, emails |
| `rf_library_index` | — | Registry tracking every file's state (ADR_002) |

### Fifteen starter libraries (ADR_002 §"Starter library list")

Libraries are **metadata-filter-discriminated slices** of a collection — NOT separate collections.

- **Reference tier (3):** `a4m_course`, `external_research`, `canva_design_library`
- **Paywalled tier (7):** `historical_coaching_transcripts`, `fksp_curriculum`, `fksp_coaching_calls`, `fertility_formula_curriculum`, `fertility_formula_coaching_calls`, `preconception_detox_curriculum`, `preconception_detox_coaching_calls`
- **Published tier (5):** `blog_posts`, `lead_magnets`, `masterclass_recordings`, `ig_content`, `nashat_dms`

### Three orthogonal dimensions (ADR_005 §7)

- `tier`: reference | paywalled | published | clinical → access control
- `origin`: drive_walk | static_library → ingestion path
- `entry_type`: coaching_transcript | reference_transcript | reference_document | published_post | ig_post | dm_exchange | ... → content kind

### Universal chunk metadata contract (ADR_006 §2)

Every chunk in every collection must carry:
- **7 universal required:** `chunk_id`, `text`, `collection`, `library_name`, `entry_type`, `origin`, `tier`
- **Source attribution:** `source_id`, `source_name`, `source_path`, `chunk_index`, `chunk_total`, `date`, `ingested_at`
- **Optional client correlation:** `client_id`, `linked_test_event_id`
- **48 required boolean marker flags:** `marker_amh`, `marker_lh`, `marker_fsh`, ..., `marker_shbg` (ADR_006 §2 + §2a)
- **Optional content attribution:** `speaker`, `topics`, `recommendations_given`
- **Type-specific escape hatch:** `type_metadata_json`

### Six-session RAG build sequence (master plan April 10)

1. Setup + inventory (service account, Railway ingester service, inventory 3 programs)
2. **Parallel pilot: FKSP video (Pipeline A) + FKSP PDF (Pipeline C) on ONE asset each** — validate before scaling
3. Admin UI image rendering + FKSP full ingestion
4. Fertility Formula + Preconception Detox full ingestion
5. `rf_published_content` build (Canva, IG, blogs, emails, lead magnets)
6. **Agent YAML integration + Railway sync** — ONLY after 1–5

### Four ingestion pipelines (master plan §"ingestion pipeline")

- **Pipeline A:** Video with slides + voiceover (course videos → scene detection → keyframe OCR + voiceover transcription)
- **Pipeline B:** PDF — text-heavy (workbooks, documents → pdfplumber)
- **Pipeline C:** PDF — visual / designed (handouts, lead magnets, Canva exports, scanned → vision OCR)
- **Pipeline D:** IG content, Canva standalone designs, image-only assets

### Ingestion-path architecture (ADR_002 + ADR_005)

- **`drive_walk` path (ADR_002):** Folder walk → diff engine → UI selection → worker ingestion. Continuously updated.
- **`static_library` path (ADR_005):** Dedicated CLI loaders for curated local-file content (A4M). Idempotent CLI, bypasses UI.
- **Railway execution (master plan §"Execution architecture"):** "No more local ChromaDB runs. Ingestion writes directly to the production ChromaDB on the Railway volume."

---

## What drifted in s28 scopes A/C/D/E

### 1. `CONTENT_SOURCES.md` (scope A) — proposed a 13-collection model that contradicts ADR_002

**What I wrote:** 13 proposed collections (`rf_published_content`, `rf_curriculum_paywalled`, `rf_sales_playbook`, `rf_marketing`, `rf_testimonials`, `rf_visual_library`, `rf_lab_data`, `rf_supplements`, `rf_internal_knowledge`, etc.)

**What the ADRs say:** 4 content collections + 1 registry. Everything else is libraries within those collections, discriminated by `library_name` metadata.

**Examples of conflation:**
- My `rf_marketing` + `rf_testimonials` + `rf_visual_library` → should be libraries within `rf_published_content` (`masterclass_recordings`, `ig_content`, etc. per ADR_002 starter list)
- My `rf_sales_playbook` → would be a new library (maybe `nashat_dms` for IG DMs, new library for sales call transcripts)
- My `rf_curriculum_paywalled` → this is exactly `rf_internal_education` (already named in ADR_002)
- My `rf_supplements`, `rf_lab_data` → future libraries, not collections
- My `rf_internal_knowledge` → would require a new tier (not in the 4-tier model) or a library within existing tiers; needs more thought

**Missing collection I never wrote about:** `rf_internal_education` — the paywalled course curriculum collection. This is the single biggest collection in the master plan and it's not ingested, not scoped, and not even mentioned in my CONTENT_SOURCES.md.

### 2. Chunk metadata schema (scopes C/D/E) — violates ADR_006

My 14 committed chunks in `rf_published_content` have NONE of the ADR_006 universal fields beyond trivial ones:

| ADR_006 required | My chunks |
|---|---|
| `chunk_id` | ✓ (format: `wp:...`, `email-ac:...`, `drive:...`) |
| `text` | ✓ |
| `collection` | ✗ (I have `source_collection` which overlaps but isn't normalized) |
| `library_name` | ✗ (I used this field but set it to the collection name `rf_published_content`, not a library name like `blog_posts`) |
| `entry_type` | ✗ (not set — should be `published_post` for blogs/lead-magnets, `ig_post` for IG, `dm_exchange` for DMs, etc.) |
| `origin` | ✗ (not set — should be `static_library` for blog_loader and ac_email_loader since they're not drive_walk) |
| `tier` | ✗ (not set — should be `published`) |
| `source_id` | ✗ (format per ADR_002 addendum: `static:{library_name}:{relative_path}` — I used separate `source_file_id` + `source_file_name`) |
| **48 marker flags** (marker_amh, marker_lh, ...) | ✗ **Completely missing** |
| `ingested_at` | ≈ (I have `ingest_timestamp_utc` but it doesn't map to the exact field name) |

**None of the 14 chunks are ADR_006-compliant.** This is the largest single drift.

### 3. Ingestion-path architecture (scopes D/E) — built a third path that's neither `drive_walk` nor `static_library`

`blog_loader.py` and `ac_email_loader.py` are REST-API-pull ingesters. Neither fits cleanly into ADR_002 (Drive-walked) or ADR_005 (static-file local CLI). REST API pulls against periodically-changing remote sources (WordPress posts, AC messages) aren't addressed by either ADR.

Functionally: they look most like `static_library` (CLI-invoked, not walk-driven, bypass the UI), but the "remote API with change detection" concept is new.

**What's needed:** either (a) a new ADR defining `rest_api` as a third `origin` value, or (b) extending ADR_005 to cover REST API sources. Both loaders would need tweaks to conform once the ADR path is picked.

### 4. Execution environment (scopes D/E) — ran locally, contradicts master plan

Master plan (April 10, §"Execution architecture"): *"All ingestion runs on Railway. Local Mac is for code authoring only. No more local ChromaDB runs."*

I ran blog_loader and ac_email_loader **locally against local Chroma**. The 14 committed chunks are in local Chroma only. Railway still doesn't have them. Tracked in STATE_OF_PLAY as the ongoing local-vs-Railway divergence.

### 5. Session sequencing — started Session 5 (`rf_published_content`) before Sessions 2–4

Master plan sequence: Setup → FKSP video+PDF pilot → FKSP full → Fertility Formula + Detox full → `rf_published_content` → Agent wiring.

We implicitly did partial Session 5 (rf_published_content via blogs + AC emails) without any of Sessions 2–4 (the paywalled course curriculum). `rf_internal_education` doesn't exist. Pipelines A/B/C/D aren't built.

The BACKLOG #47 "multi-modal ingestion handler" I opened in scope C is essentially Pipeline A — but I framed it as a new design item, not as "we're behind on Session 2 of the master plan."

### 6. BACKLOG items #50–#55, #73 — misdiagnosed as collection creation

I opened #50-#55 as "create rf_curriculum_paywalled / rf_sales_playbook / rf_marketing / rf_testimonials / rf_visual_library / rf_lab_data". These would all be **libraries within the 4 existing collections**, not new collections. Superseded by ADR_002's 15-library starter list.

---

## Drift controls — where they failed, what's missing

### Existing controls (and why they didn't catch this)

| Control | Why it didn't catch the drift |
|---|---|
| Step 0 reality check | Data-plane focus (collection counts, chunks, tools). Doesn't validate against ADRs. |
| Step 1 reading (CURRENT STATE + HANDOVER) | CURRENT STATE is STATE_OF_PLAY's top section. Doesn't link to or summarize ADR_001–006. |
| Step 1.5 quick-check (4 items) | Checks plan-doc timestamps, BACKLOG closure count, ADR `Status:` line, drift markers. **Does not cross-reference ADR decisions against new scope proposals.** |
| Full Step 1.5 audit (s31 next) | Would catch this. But 3 sessions away. |
| Operating Model #7 governance triggers | BACKLOG closure → update CURRENT STATE. Doesn't require reading predecessor canonical docs before writing a new canonical doc. |
| Anti-goal list (11 items) | None of them say "read ADRs before writing canonical schema." |

### New drift controls to add (this session)

1. **New Operating Model rule #8 — Predecessor-canonical-doc reading required.** Before writing or amending a doc that will be referenced as "canonical source of truth" (CONTENT_SOURCES, CHUNK_SCHEMA, ingestion architecture), read all predecessor canonical docs (ADR_001–006, HANDOVER_INTERNAL_EDUCATION_BUILD.md, and any doc flagged as canonical in STATE_OF_PLAY). Include explicit `Supersedes:` / `Aligns with:` headers. A doc that conflicts with an ADR without explicit supersession is a governance violation.

2. **New anti-goal:** NO new canonical schemas or collection architecture without reading ADR_002, ADR_005, ADR_006 first. This is the specific case that drifted in s28.

3. **Step 1.5 quick-check addition (5th item):** grep ADR_002 starter library list + ADR_006 collection names; verify every collection and library referenced in CURRENT STATE or active scopes exists in the ADRs or has an explicit supersession commit.

4. **Step 1 reading order update:** add **ADR_001–006 + `HANDOVER_INTERNAL_EDUCATION_BUILD.md`** to the default reading set (or at minimum: "if scope touches ingestion, chunk schema, or collection architecture, read these").

---

## Correction plan — split across this session and s29

### This session (scope F, drift recovery)

1. Write this analysis doc ✓
2. Add supersession banner to `CONTENT_SOURCES.md` acknowledging drift + pointing readers to ADRs + flagging the rewrite for s29
3. Update `STATE_OF_PLAY` CURRENT STATE: correct the collections table (4 collections + registry, not 13); flag 14 chunks as schema-non-compliant pending backfill; list the 15 starter libraries
4. Add drift controls to `NEXT_SESSION_PROMPT_S29.md` (OM rule #8, new anti-goal, Step 1.5 5th item, mandatory ADR reading)
5. Triage BACKLOG #50–#78: mark collection-creation items as "SUPERSEDED BY ADR_002 — libraries, not collections"; keep handler/discovery items; add new items for the real next steps (ADR-compliant schema backfill; Pipeline A/B/C/D implementation; FKSP pilot per master plan Session 2)
6. HANDOVER scope-F entry documenting the drift honestly
7. Commit as one scope-F commit

### s29 (drift alignment + master plan resumption)

1. Rewrite `CONTENT_SOURCES.md` completely to align with ADR_002 four-collection / fifteen-library model; keep the per-domain source mapping content (which was good) but re-express in the library vocabulary
2. Schema backfill of the 14 committed chunks to ADR_006 compliance (add `entry_type`, `origin`, `tier`, correct `library_name`, 48 marker flags via regex detection). Zero-cost metadata-only upsert, similar pattern to #44 migration.
3. Pick up master plan Session 2 (FKSP pilot: one video + one PDF end-to-end)
4. OR: explicit discussion with Dan on whether to formally supersede the master plan (if the direction has genuinely changed since April 10) and document that decision in a new ADR

### What is NOT being done this session

- Deleting the 14 chunks — they are content we'll keep; only the metadata is wrong, and metadata backfill is a one-pass upsert in s29
- Reverting commits — no destructive git operations; the drift is recorded in docs rather than rewritten in history
- Re-architecting blog_loader and ac_email_loader — they work; they need their metadata emission fixed in s29 to conform to ADR_006
- Pursuing GHL (#76) or AC bulk (#78) — these are downstream of the schema fix and the master plan sequencing

---

## What this doc is NOT

- NOT a new canonical architecture (it explicitly defers to ADR_001–006)
- NOT a retrospective on "we should have done X instead" — the s28 work was useful (Railway sync, classifier infra, loader patterns, TDD discipline); the governance issue is that it was committed without explicit supersession of pre-existing canonical docs
- NOT a blocker on s28 closing out. Five commits landed; the doc/governance updates in scope F square the record.

*Closed — applied to STATE_OF_PLAY + BACKLOG + HANDOVER + NEXT_SESSION_PROMPT_S29 in the same scope-F commit.*
