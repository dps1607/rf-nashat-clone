# ADR_006 — Chunk reference contract (universal metadata schema for all RAG chunks)

**Status:** Accepted (2026-04-12); amended same day to add hybrid boolean/delimited encoding for list-shaped fields and phased backfill
**Supersedes:** none
**Amends:** VECTOR_DB_BUILD_GUIDE.md §7 (Vector DB Entry Schema) — extends the `entry_type` enum and relaxes `client_id` from universal-required to optional
**Related:** ADR_002 (registry, file record schema), ADR_005 (static libraries, ingestion categories)

---

## Context

Every chunk written to any content collection in the RAG system (`rf_coaching_transcripts`, `rf_reference_library`, `rf_published_content`, future `rf_coaching_episodes`) needs a consistent metadata contract so that:

1. **Retrieval works across collections.** A query routed to both `rf_coaching_transcripts` and `rf_reference_library` should get back chunks whose metadata can be uniformly filtered, ranked, and presented to the LLM in a single context window.

2. **Citations are attributable.** Every chunk must carry enough metadata to render a human-readable source line (file name, date, library) and to trace back to its origin in the registry if needed.

3. **Agent variant routing is possible.** The public sales agent and the internal coaching agent draw from different subsets of content. The contract must carry enough metadata to make the "is this chunk allowed for this variant?" question answerable at retrieval time without a separate lookup.

4. **Cross-source correlation (BUILD_GUIDE §8) is preserved where it applies.** Coaching transcript chunks that reference real client lab results must carry the correlation metadata (`client_id`, `linked_test_event_id`, marker references) that makes the BUILD_GUIDE's timeline queries possible. But this metadata must be *optional* at the contract level so that non-client-linked content (A4M lectures, blog posts, etc.) doesn't have to fabricate it.

5. **Filter queries must be exact, not substring-match.** The BUILD_GUIDE §5 marker list has real name collisions (`T3`/`FT3`, `T4`/`FT4`, `Iron`/`Iron Saturation %`) that make Chroma's `$contains` substring match unsafe for filtering by marker. A query for "chunks that discuss T3" must not silently match chunks tagged with `FT3`. This has to be solved at the schema layer, not worked around at the query layer, because query layer conventions are fragile — one forgotten delimiter and you silently return wrong answers.

BUILD_GUIDE §7 sketched a universal schema with `entry_type`, `client_id`, `date`, `associated_media`, and per-type metadata blocks. That sketch had two gaps that need closing now:

- **Gap 1:** `client_id` was written as a universal field, implying it's required on every entry. This breaks when reference-library content (A4M) arrives — there's no client to link to.
- **Gap 2:** The `entry_type` enum only included client-linked or distribution content types (`transcript | dm | ig_post | lab_summary | supplement_rec | qpt_reference`). There was no entry type for reference-library content.

ADR_005 (static libraries) mandated that a shared chunk reference contract exist but deferred the field list to "the next ADR or ARCHITECTURE.md update." **This is that ADR.** ADR_006 closes both gaps and locks the contract.

---

## Decisions

### 1. The contract is an ADR, not an ARCHITECTURE.md table

Two reasons: (a) the contract encodes real decisions with tradeoffs (which fields are required vs optional, how to reconcile BUILD_GUIDE §7 with ADR_005's client-free content, how to handle correlation fields across collections) — ADRs are the right home for decisions; (b) ADR_002's registry schema is in ADR_002, not ARCHITECTURE.md, so this keeps the pattern consistent — schemas live in the ADR that decides them, and `docs/ARCHITECTURE.md` points to the ADRs.

`docs/ARCHITECTURE.md` gets a short "Chunk metadata schema → see ADR_006" pointer. Nothing more.

### 2. The universal chunk schema

Every chunk in every content collection must carry the following fields. Fields marked **required** must be non-null on every chunk. Fields marked **optional** may be null.

```
# ── Universal fields (all chunks, all collections) ──

chunk_id            required   string      # collection-unique chunk ID (e.g., "a4m_course:reference_transcript:module_01:chunk_0007")
text                required   string      # the embeddable/searchable content of the chunk
collection          required   string      # which ChromaDB collection this chunk lives in
library_name        required   string      # which library (ADR_002 first-class library) this chunk belongs to
entry_type          required   string      # one of the enum values below (see §3)
origin              required   string      # "drive_walk" | "static_library" (mirrors the source file's origin in rf_library_index)
tier                required   string      # "reference" | "paywalled" | "published" | "clinical" (denormalized from library for retrieval-time filtering)

# ── Source attribution (all chunks) ──

source_id           required   string      # matches the source_id on the file record in rf_library_index (drive_file_id for drive_walk, "static:{lib}:{path}" for static_library)
source_name         required   string      # human-readable filename (e.g., "Module_01_Epigenetics_and_Nutrigenomics.txt")
source_path         optional   string      # drive_path (drive_walk) or local_path (static_library); null OK if redundant with source_name
chunk_index         required   int         # zero-based ordinal of this chunk within its source file
chunk_total         optional   int         # total number of chunks produced from this source file, if known at write time
date                optional   string      # ISO date (YYYY-MM-DD) — the content's relevant date, not the ingestion date. For coaching calls: call date. For A4M lectures: recording date if known, else null. For blog posts: publication date.
ingested_at         required   string      # ISO timestamp (UTC) — when this chunk was written to the collection

# ── Client correlation (optional — populated when applicable) ──

client_id           optional   string      # BUILD_GUIDE §2 Client ID format "RF-XXXX" or RFID-XXX per Program Key (§13). Null for reference-library, published-content, and any chunk not tied to a specific client.
linked_test_event_id   optional   string   # BUILD_GUIDE §2 Test Event ID format "RF-XXXX-T1". Null when not applicable.

# ── Marker discussion flags (required on EVERY chunk; see §2a for the locked canonical set) ──
# All 44 marker flags are required boolean fields on every chunk regardless of entry_type.
# Default value is `false`. Set to `true` when the chunk text discusses that marker.
# Reference-library loaders do regex-based detection (~20 lines of code, acceptable precision for lecture content).
# Coaching transcript loaders can use more sophisticated detection (see §7 phased backfill).

marker_amh                          required   bool   # BUILD_GUIDE §5 Day 3 Hormones
marker_lh                           required   bool
marker_fsh                          required   bool
marker_prolactin                    required   bool
marker_estradiol                    required   bool
marker_ft3                          required   bool   # Thyroid Panel
marker_ft4                          required   bool
marker_tsh                          required   bool
marker_thyroglobulin_antibodies     required   bool
marker_tpo_antibodies               required   bool
marker_progesterone                 required   bool   # Day 21
marker_wbc                          required   bool   # CBC
marker_hemoglobin                   required   bool
marker_hct                          required   bool
marker_mcv                          required   bool
marker_platelets                    required   bool
marker_sodium                       required   bool   # CMP
marker_potassium                    required   bool
marker_chloride                     required   bool
marker_co2                          required   bool
marker_bun                          required   bool
marker_creatinine                   required   bool
marker_glucose                      required   bool
marker_alk_phos                     required   bool
marker_ast                          required   bool
marker_alt                          required   bool
marker_ggt                          required   bool
marker_calcium                      required   bool
marker_magnesium                    required   bool
marker_phosphorus                   required   bool
marker_zinc                         required   bool
marker_homocysteine                 required   bool   # Special
marker_hscrp                        required   bool
marker_vitamin_d                    required   bool
marker_iron                         required   bool   # Iron panel
marker_iron_saturation_pct          required   bool
marker_transferrin_sat              required   bool
marker_ferritin                     required   bool
marker_insulin                      required   bool   # Metabolic
marker_hba1c                        required   bool
marker_total_cholesterol            required   bool   # Lipid
marker_ldl                          required   bool
marker_hdl                          required   bool
marker_triglycerides                required   bool
marker_dheas                        required   bool   # Optional hormones
marker_total_testosterone           required   bool
marker_free_testosterone            required   bool
marker_shbg                         required   bool

# Note: the above list is 48 flags (44 unique markers from BUILD_GUIDE §5 plus 4 minor
# additions for the Optional Hormones block). Treat it as the canonical flag set — do not
# add or rename without an ADR_006 amendment.

markers_discussed   optional   string     # Human-readable pipe-delimited display string with bookend delimiters, e.g., "|AMH|FSH|TSH|". NEVER used for filtering — booleans are the filter. Used only for display and debugging. Null allowed when no markers.

# ── QPT pattern flags (forward-compat spec; NOT yet required on chunks) ──
# These 25 boolean flags are specified here so the schema is stable when QPT reference
# entries are first built. Until then:
#   - Existing and new chunks MAY omit these fields (treat as optional for now)
#   - When the first QPT-aware loader is built, it must populate all 25 flags on its chunks
#   - A future ADR_006 amendment will flip these from optional to required and trigger
#     a QPT-detection backfill pass on existing chunks
# Format: qpt_01 through qpt_25, all boolean. Naming: zero-padded two-digit number.

qpt_01  optional  bool
qpt_02  optional  bool
# ... through qpt_25 (all 25 flags; see §2a for the expansion)

qpt_patterns_referenced   optional   string    # Human-readable pipe-delimited display, e.g., "|QPT-07|QPT-14|". Never used for filtering.

# ── Content attribution (optional — populated when known) ──

speaker             optional   string      # Coach or speaker identity. "Dr. Nashat", "Dr. Chris", "Avery", etc. For A4M: the lecture speaker if identifiable. Null if unknown.
topics              optional   string      # Pipe-delimited topic tags with bookend delimiters, e.g., "|fertility|amh|egg_quality|". Free-form but loaders should reuse existing tags where possible. Topics are unbounded so boolean expansion is impractical — delimited string is acceptable here because topic vocabulary is controlled and we can avoid substring collisions by convention. Filter queries MUST use bookend delimiters (`$contains: "|fertility|"`) to avoid partial-match bugs.
recommendations_given  optional  string    # Pipe-delimited list with bookend delimiters. Coaching chunks only.

# ── Type-specific metadata (entry_type-dependent) ──

type_metadata_json  optional   string      # JSON-encoded object containing fields specific to this entry_type that don't fit the universal schema. See §4 below for per-type expectations.
```

**ChromaDB metadata compatibility note.** ChromaDB metadata values must be scalar (str, int, float, bool, or None). This constraint forces three encoding decisions:

1. **Filterable list-shaped fields become boolean columns.** Marker discussion is the canonical example: instead of storing `markers_discussed: "AMH|FSH|TSH"` and filtering with `$contains`, we store `marker_amh: true`, `marker_fsh: true`, `marker_tsh: true` and filter with `{"marker_amh": true}`. This is mandatory because substring filtering on marker names is unsafe (`T3` is a substring of `FT3`). The hybrid retains a human-readable `markers_discussed` display string for rendering and debugging, but **filtering always goes through the boolean columns.** The same applies to QPTs (forward-compat spec — §2a).

2. **Non-filterable unbounded lists use bookend-delimited strings.** `topics` and `recommendations_given` are unbounded (new topic tags can emerge over time) so boolean expansion is impractical. These use pipe-delimited strings with leading and trailing `|` bookend delimiters (`"|fertility|amh|"`). The bookend delimiter convention prevents partial-match bugs as long as queries also use bookend delimiters. Vocabulary for these fields is controlled internally, so substring collisions are less catastrophic than the marker case. **If a future use case needs exact filtering on topics, a migration to boolean flags will be required — document it at that point and amend ADR_006.**

3. **Nested type-specific metadata uses JSON-encoded string.** `type_metadata_json` is the escape hatch for per-type fields that don't generalize. It's a JSON-encoded string (not a dict) for the Chroma scalar rule. At query time, retrieval code parses it back into a dict when it needs type-specific filtering. Fields inside `type_metadata_json` cannot be used as ChromaDB metadata filters — if a field inside `type_metadata_json` needs to be filterable, it should be hoisted to a top-level column.

**Why this hybrid is the right answer (2026-04-12 amendment).** A previous version of this ADR used pipe-delimited strings for all list-shaped fields including markers. The BUILD_GUIDE §5 marker list has enough name collisions (`T3`/`FT3`, `T4`/`FT4`, `Iron`/`Iron Saturation %`) that substring filtering is genuinely dangerous — a query for `T3` silently matches `FT3` chunks and returns wrong answers with no error. The bookend-delimiter convention mitigates this in principle but requires every query site to honor the convention perfectly; one forgotten delimiter is a silent correctness bug. Boolean columns are the right shape because (a) marker vocabulary is closed and known (44 markers locked in BUILD_GUIDE §5, updated only via ADR amendment), (b) Chroma handles 50+ boolean metadata columns without performance issues at the scale we're operating, and (c) correctness for clinical-content retrieval is non-negotiable — we cannot ship a system that occasionally matches wrong markers. The storage bloat is minor and the safety gain is large.

### 2a. Canonical marker and QPT flag naming

**Markers (required on every chunk, 48 flags).** The flag names above derive from BUILD_GUIDE §5 with the following normalization rules:

- Prefix: `marker_`
- Snake case, lowercase
- Percent signs become `_pct` (e.g., `marker_iron_saturation_pct`)
- Hyphens dropped, spaces become underscores
- `HbA1C` → `marker_hba1c`, `DHEA-s` → `marker_dheas`, `hsCRP` → `marker_hscrp`

**QPTs (forward-compat spec, 25 flags).** The full expansion is `qpt_01` through `qpt_25`, zero-padded to two digits. The `qpt_patterns_referenced` display string uses the non-padded form `QPT-7` to match the convention already in use elsewhere. At query time, retrieval code bridges the two forms when rendering citations.

**Adding new marker or QPT flags requires an ADR_006 amendment.** The marker set follows BUILD_GUIDE §5; if BUILD_GUIDE §5 ever adds or renames a marker, ADR_006 amends at the same time. No silent drift.

### 3. The `entry_type` enum (extended from BUILD_GUIDE §7)

BUILD_GUIDE §7 listed `transcript | dm | ig_post | lab_summary | supplement_rec | qpt_reference`. ADR_006 extends this enum with entries for reference-library and future content types, and slightly renames `transcript` for clarity.

**Locked enum (2026-04-12):**

| `entry_type` value | Collection | Description | Source ADR |
|---|---|---|---|
| `coaching_transcript` | `rf_coaching_transcripts` | Chunk from a coaching call transcript (FKSP Q&A, lab review, VIP, etc.). Replaces BUILD_GUIDE §7's generic `transcript`. | ADR_002 + this ADR |
| `reference_transcript` | `rf_reference_library` | Chunk from a curated lecture/course transcript (A4M, ACOG, etc.). Non-client-linked. | ADR_005 + this ADR |
| `reference_document` | `rf_reference_library` | Chunk from a curated non-transcript reference document (slide decks, PDFs, research snapshots). Non-client-linked. | ADR_005 + this ADR |
| `published_post` | `rf_published_content` | Chunk from a published piece (blog post, masterclass recording, lead magnet). | ADR_002 |
| `ig_post` | `rf_published_content` | Chunk from an Instagram post (caption + metadata). | BUILD_GUIDE §7 |
| `dm_exchange` | `rf_published_content` (semi-private library `nashat_dms`) | Chunk from an Instagram DM enrollment conversation. Renamed from BUILD_GUIDE §7's generic `dm` for clarity. | BUILD_GUIDE §7 |
| `lab_summary` | (future) | Per-client lab profile summary. Not yet built. | BUILD_GUIDE §7 |
| `supplement_rec` | (future) | Supplement protocol entry. Not yet built. | BUILD_GUIDE §7 |
| `qpt_reference` | (future) | One of the 25 QPT pattern definitions. Not yet built. | BUILD_GUIDE §7 |
| `coaching_episode` | `rf_coaching_episodes` (planned) | Zoom video pipeline output (transcript + scene-change + OCR). Not yet built. | BACKLOG |

**Notes on the enum:**
- `coaching_transcript` is the existing 9,224 chunks in `rf_coaching_transcripts`. Any backfill pass that adds `entry_type` to existing chunks should set it to `coaching_transcript`.
- `reference_transcript` and `reference_document` are **the values A4M content will use.** A4M transcripts (`Transcriptions/*.txt`) get `reference_transcript`; A4M slide decks (`Slides/*.pdf`) get `reference_document`.
- The generic names (`reference_transcript`, `reference_document`) were chosen over A4M-specific names (`course_transcript`, `course_slides`) to future-proof for ACOG snapshots and other curated sources.
- `dm_exchange` replaces BUILD_GUIDE §7's `dm` and `coaching_transcript` replaces `transcript` purely for clarity. Neither rename requires backfill work today because neither source has been ingested yet (`dm_exchange`) or because the existing population is uniform enough that a backfill pass can set the value in one update (`coaching_transcript`).
- Adding a new `entry_type` value in the future requires an ADR_006 amendment (not a new ADR). Keep the enum disciplined — proliferation is the main risk.

### 4. Per-type `type_metadata_json` expectations

`type_metadata_json` stores fields specific to each entry type that don't fit the universal schema. This section specifies what each type should put in there. Fields inside `type_metadata_json` are not enforced by schema; they're a convention loader scripts should follow.

**`coaching_transcript`:**
```json
{
  "call_type": "Q&A | Lab Review | VIP | Mind+Body | Coaching | TFF | GASP",
  "call_date": "2026-03-14",
  "fksp_id": "FKSP-QA-152",
  "cycle_day_discussed": "CD 3",
  "emotional_tone": "reassurance | education | celebration | tough_love",
  "client_program_stage": "early | mid | late | re-enrollment",
  "scene_change_markers": ["00:04:12", "00:11:45"]
}
```
Several of these overlap with the universal fields (`speaker`, `date`). The universal fields are authoritative; `type_metadata_json` holds type-specific extras only.

**`reference_transcript` (A4M and similar):**
```json
{
  "course_name": "A4M Fertility Course",
  "module_number": 1,
  "module_title": "Epigenetics & Nutrigenomics in Fertility",
  "lecturer": "Dr. [Name]",
  "run_time_total_seconds": 3840,
  "speaker_block_count": 394
}
```

**`reference_document` (A4M slides and similar):**
```json
{
  "course_name": "A4M Fertility Course",
  "module_number": 1,
  "slide_number": 7,
  "slide_title": "MTHFR and methylation cycles",
  "has_images": true,
  "has_tables": false
}
```

**`published_post`:**
```json
{
  "post_type": "blog | masterclass | lead_magnet",
  "published_date": "2025-11-02",
  "canonical_url": "https://reimagined-health.com/blog/...",
  "word_count": 1840,
  "target_keyword": "AMH levels fertility"
}
```

**`ig_post`:**
```json
{
  "post_format": "carousel | reel | single_image | text_post",
  "engagement": {"likes": 342, "saves": 89, "shares": 12, "reach": 5400},
  "visual_asset_paths": ["path/to/canva/original.png"],
  "cta_used": "Link in bio | DM me | Comment below"
}
```

**`dm_exchange`, `lab_summary`, `supplement_rec`, `qpt_reference`, `coaching_episode`:** deferred until the respective ingestion paths are built. Each will get a per-type block added to this ADR when the loader is written.

### 5. Required vs optional — the full field matrix

For quick reference during loader implementation, here's the full field matrix. "R" = required, "O" = optional, "—" = N/A at the universal level (lives in `type_metadata_json`).

| Field | `coaching_transcript` | `reference_transcript` | `reference_document` | `published_post` | `ig_post` |
|---|---|---|---|---|---|
| `chunk_id` | R | R | R | R | R |
| `text` | R | R | R | R | R |
| `collection` | R | R | R | R | R |
| `library_name` | R | R | R | R | R |
| `entry_type` | R | R | R | R | R |
| `origin` | R | R | R | R | R |
| `tier` | R | R | R | R | R |
| `source_id` | R | R | R | R | R |
| `source_name` | R | R | R | R | R |
| `source_path` | O | O | O | O | O |
| `chunk_index` | R | R | R | R | R |
| `chunk_total` | O | O | O | O | O |
| `date` | O (call date) | O | O | O (pub date) | O (post date) |
| `ingested_at` | R | R | R | R | R |
| `client_id` | O (set when known) | **null** | **null** | **null** | **null** |
| `linked_test_event_id` | O (set when known) | **null** | **null** | **null** | **null** |
| `marker_*` (48 flags) | **R** (all false by default, true per detection) | **R** (all false by default, true per detection) | **R** (all false by default, true per detection) | **R** | **R** |
| `markers_discussed` (display) | O | O | O | O | O |
| `qpt_01`–`qpt_25` | O (forward-compat) | O (forward-compat) | O (forward-compat) | O (forward-compat) | O (forward-compat) |
| `qpt_patterns_referenced` (display) | O | O | O | O | O |
| `speaker` | O (Dr. Nashat, etc.) | O (lecturer) | — | O (author) | — |
| `topics` | O | O | O | O | O |
| `recommendations_given` | O | — | — | — | — |
| `type_metadata_json` | O | O | O | O | O |

**Key rules from this matrix:**
- **Marker flags are required on EVERY chunk**, regardless of entry_type. Default value is `false`. A chunk that doesn't mention any markers has all 48 flags set to `false` explicitly — missing fields in Chroma become `None` and are not filterable, which breaks retrieval queries. **Explicit false is not the same as missing.**
- **Bold null** entries are enforced: reference-library and published-content loaders must write `client_id: null` and `linked_test_event_id: null`, not fabricated values. This keeps retrieval filters clean (a query for "chunks about client RF-0042" won't accidentally hit A4M lecture content).
- **QPT flags are forward-compat** until the first QPT-aware loader is built. Until then they may be omitted; after that amendment, they become required with the same "explicit false, not missing" rule.

### 6. BUILD_GUIDE §7 reconciliation

BUILD_GUIDE §7 defined a universal schema with top-level fields `text`, `entry_type`, `associated_media`, `client_id`, `date`, and per-type `metadata` blocks. ADR_006 diverges from §7 in the following ways, and the divergences are deliberate:

| BUILD_GUIDE §7 | ADR_006 | Reason |
|---|---|---|
| `client_id` at top level as universal | `client_id` optional; required null for non-client content | Accommodates reference-library and published content, which have no client link. |
| `metadata: {}` as a nested dict | `type_metadata_json` as a JSON-encoded string | Chroma metadata must be scalar. JSON encoding is the compatibility workaround. |
| `associated_media` as a top-level list | Lives inside `type_metadata_json` (e.g., `visual_asset_paths` for `ig_post`) | Only some entry types have associated media; not universal enough to hoist to top level. |
| `entry_type` enum with 6 values | Enum with 10 values (see §3) | Adds `reference_transcript`, `reference_document`, `published_post`, `coaching_episode`; renames `transcript` → `coaching_transcript` and `dm` → `dm_exchange` for clarity. |
| No `origin`, `tier`, `library_name`, `source_id` on chunks | All four required | Enables retrieval-time filtering without a registry join, and aligns with the ADR_002 + ADR_005 library/tier/origin model. |
| No `chunk_id`, `chunk_index`, `chunk_total` | All three present (`chunk_id` required) | Necessary for chunk-level traceability and for rendering "chunk 7 of 42 from Module_01.txt" source lines. |
| Marker references inside nested `metadata: {markers_discussed: [...]}` | 48 top-level boolean columns (`marker_amh`, ...) + optional display string | Enables exact boolean filtering. Substring filtering on a delimited marker list is unsafe due to name collisions (`T3`/`FT3`, etc.). |

BUILD_GUIDE §7 is not being deleted — it's being treated as the original design sketch that ADR_006 now supersedes for the fields it covers. A recommended §7 revision note is flagged in `docs/BACKLOG.md` for a future BUILD_GUIDE update pass.

### 7. Existing 9,224 `rf_coaching_transcripts` chunks — phased backfill

The existing population in `rf_coaching_transcripts` was built before ADR_006. Its metadata uses a flat-at-root convention (locked 2026-04-12 per earlier handover notes) but does not carry `origin`, `tier`, `library_name`, `source_id`, `entry_type`, or any of the 48 marker flags — those fields did not exist yet.

The backfill is split into two phases so that structural schema compliance is not gated on marker-detection accuracy, and so A4M ingestion is not blocked waiting for marker-detection work on the coaching transcripts.

#### Phase 1 — Structural annotation (cheap, unblocks A4M)

A one-time backfill script reads every chunk in `rf_coaching_transcripts` and sets:

- `entry_type = "coaching_transcript"`
- `origin = "drive_walk"` (the historical transcripts all came from Drive originally)
- `tier = "paywalled"`
- `library_name = "historical_coaching_transcripts"` (matches ADR_002's starter library list)
- `collection = "rf_coaching_transcripts"`
- `source_id` derived from the existing `source_file` field if present, else a synthesized value
- `ingested_at` set to a sentinel ISO timestamp `2026-04-12T00:00:00Z` marking "backfilled, actual ingestion date unknown"
- **All 48 `marker_*` flags set to `false`** (explicit false — NOT missing)
- `markers_discussed` display string set to null
- QPT flags omitted (forward-compat spec, not yet required)

**No marker detection in Phase 1.** Setting all flags to false is a deliberate placeholder that Phase 2 will correct. The implication for retrieval: queries that filter on `marker_amh: true` will return zero coaching transcript chunks until Phase 2 runs, even though there are thousands of coaching chunks that discuss AMH. The sales agent and reference-library queries are unaffected (they don't query coaching transcripts). The internal coaching agent will see reduced utility on marker-filtered queries until Phase 2 completes — acceptable tradeoff since the agent can still retrieve by semantic similarity against chunk text.

The Phase 1 backfill runs alongside ADR_002's file-record backfill pass (which populates `rf_library_index` with file records for the historical transcripts). Both backfills should share a coordinator script so they stay in sync.

**No chunk text changes; no re-embedding; no chunk boundaries re-computed.** This is purely a metadata-annotation pass.

Dan approves before the Phase 1 backfill runs (first touch of `rf_coaching_transcripts` in annotation mode).

#### Phase 2 — Marker detection (independent, can run later)

A second backfill pass reads every chunk in `rf_coaching_transcripts` and sets the 48 `marker_*` flags to `true` where the chunk text discusses that marker, and writes the corresponding `markers_discussed` display string.

**Detection method for Phase 2 (to be decided in the Phase 2 session, not locked here):**

- **Option A — regex-based:** cheap, fast, probably acceptable for high-confidence markers (AMH, FSH, TSH, progesterone are unambiguous) but will have precision problems on the shortest marker names and collisions (T3/FT3). Roughly 40 lines of Python.
- **Option B — LLM-assisted:** feed each chunk to Haiku with the 48-marker list and ask "which of these markers does this chunk discuss?". More expensive (9,224 Haiku calls), more accurate, and the LLM can handle contextual references like "her T3 was low" without confusing it with FT3. Roughly $20–30 at Haiku pricing.
- **Option C — hybrid:** regex for high-confidence markers, Haiku for ambiguous ones (the T3/FT3/T4/FT4 collision set specifically).

Phase 2 does NOT need to run before Phase 1 is approved. It is independent work that can be a dedicated session. Unit 14 A4M merge work, A4M ingestion, and subsequent reference-library loads can proceed with Phase 1 only.

Phase 2 requires Dan approval before running (another first-touch of `rf_coaching_transcripts`).

**No chunk text changes in Phase 2 either.** Still metadata-only.

**Why not re-chunk:** the v3 LLM-chunked population is already proven in production (573-word mean, 9,224 chunks). Re-chunking to fit a new contract would throw away that investment. The contract is designed to be achievable via metadata annotation alone.

### 8. Marker detection for new loaders (A4M and forward)

New loaders written against ADR_006 must populate all 48 `marker_*` flags on every chunk they write. The detection method is loader-specific but should follow these guidelines:

- **Reference-library loaders (A4M transcripts, A4M slides, future ACOG):** simple regex-based detection is acceptable. Lecture content mentions markers conceptually (e.g., "AMH measures ovarian reserve") rather than in the client-value context where ambiguity bites hardest. A ~20-line regex pass over each chunk's text is sufficient. Include marker aliases and common abbreviations (e.g., `anti-müllerian hormone` → `marker_amh`). False positives are less costly here than false negatives — a reference chunk that wrongly flags `marker_hba1c` because the word "metabolic" triggered a loose pattern is annoying but not clinically dangerous; a reference chunk that fails to flag `marker_amh` in a lecture about AMH means retrieval misses relevant educational content.

- **Future coaching-transcript loaders (if v4 is ever built):** match whatever detection method Phase 2 of the historical backfill uses. Consistency across the collection is more important than theoretical accuracy on individual chunks.

- **Future published-content and IG-post loaders:** regex-based. Published content is curated and short; precision concerns are minimal.

**Regex starter kit for reference-library loaders (illustrative, not normative).** Each marker has a canonical pattern and optional aliases:

```python
MARKER_PATTERNS = {
    "marker_amh":            r"\b(AMH|anti[- ]?müllerian|anti[- ]?mullerian)\b",
    "marker_fsh":            r"\bFSH\b",
    "marker_lh":             r"\bLH\b",
    "marker_tsh":            r"\bTSH\b",
    "marker_ft3":            r"\b(FT3|free\s*T3)\b",
    "marker_ft4":            r"\b(FT4|free\s*T4)\b",
    "marker_progesterone":   r"\bprogesterone\b",
    "marker_vitamin_d":      r"\b(vitamin\s*D|25[- ]?OH[- ]?D|cholecalciferol)\b",
    "marker_hba1c":          r"\b(HbA1c|hemoglobin\s*A1c|A1c)\b",
    # ... remainder of 48 flags elaborated per loader
}
```

The full canonical regex table should live in a shared `marker_detection.py` module in the ingester package so every loader uses the same patterns. Keeping detection logic in one place means Phase 2 of the backfill can reuse it, new loaders inherit consistency for free, and updates propagate without hunting through multiple files.

### 9. Retrieval-time usage (what this enables)

With ADR_006 in place, the retrieval layer can do the following at query time **without needing to join to the registry**:

1. **Tier filter for agent variant routing.** The public sales agent passes `tier in ["reference", "published"]` as a metadata filter; the internal coaching agent passes `tier in ["reference", "paywalled", "published"]`. No registry lookup required — `tier` is denormalized onto every chunk.
2. **Library filter for mode routing.** A mode like `a4m_course_analysis` can pass `library_name = "a4m_course"` directly.
3. **Cross-collection queries.** A query that hits both `rf_coaching_transcripts` and `rf_reference_library` gets back chunks with uniform metadata shape, so the LLM sees them in a consistent format in its context window.
4. **Exact marker filtering.** `{"marker_amh": true}` returns exactly the chunks that discuss AMH. No substring collisions. No partial matches. A query filtering on multiple markers combines with Chroma's `$and` / `$or` operators: `{"$and": [{"marker_amh": true}, {"marker_fsh": true}]}` returns chunks discussing both AMH and FSH.
5. **Correlation queries preserved.** BUILD_GUIDE §8 timeline queries (e.g., "what coaching was given to clients whose AMH was <1.0 at T1?") still work: `client_id`, `linked_test_event_id`, and the marker flags are on every `coaching_transcript` chunk that has them, and false/null on the rest without contamination.
6. **Citation rendering.** Every chunk has `source_name`, `chunk_index`, and `library_name`, so source lines like "A4M Course Module 1, chunk 7 of 42" render from chunk metadata alone. The `markers_discussed` display string provides a human-readable marker list for citations without requiring the retrieval layer to reverse-engineer it from the 48 boolean columns.

### 10. Scope — what this ADR does NOT do

- **Does not re-embed anything.** Embedding model stays OpenAI `text-embedding-3-large`. Contract is metadata-only.
- **Does not change collection boundaries.** `rf_coaching_transcripts`, `rf_reference_library`, `rf_published_content`, `rf_coaching_episodes` remain the four content collections. `rf_library_index` remains the metadata/registry collection.
- **Does not decide clone-variant library-access rules.** Which libraries each clone variant (content-gen, paid-client, public) can draw from is deferred to a future ADR. ADR_006 just makes sure the chunk metadata carries enough information for that future decision to be answerable without schema changes.
- **Does not address chunk-boundary rules.** How text is split into chunks (LLM-powered for coaching transcripts, rule-based per-slide for A4M slides) is a per-loader concern. ADR_006 only governs what metadata each chunk carries once it exists.
- **Does not define the retrieval layer.** That's a separate concern. ADR_006 provides the inputs; the retrieval layer is built on top.
- **Does not choose a Phase 2 marker-detection method.** Phase 2 is independent work and the detection method (regex vs LLM-assisted vs hybrid) is decided in the Phase 2 session against real chunks.

---

## Consequences

**Enables:**
- A4M transcript loader can now be written against a locked contract (unblocks Unit 14 merge plan and A4M pilot).
- All future loaders inherit a single schema to conform to — no per-collection invention.
- Retrieval-time filtering by tier, library, origin, entry_type, **and marker** works without registry joins and without substring-collision risk.
- Citation and source-attribution rendering works from chunk metadata alone.
- The BUILD_GUIDE §7 sketch is formally extended and reconciled with ADR_002 and ADR_005.
- Phased backfill unblocks A4M ingestion immediately (Phase 1 only) without waiting for the marker-detection work (Phase 2) to complete.

**Constrains:**
- Existing 9,224 coaching transcript chunks need Phase 1 metadata backfill before they fully conform. Until Phase 1 runs, retrieval queries that depend on `tier`, `library_name`, or `entry_type` fields will not find them. Until Phase 2 runs, marker-filtered queries against coaching transcripts return zero results (all flags are `false` placeholders).
- Loader authors must write chunk records that conform to §2's required fields (including all 48 marker flags, default `false`) and §5's per-type matrix. Non-conforming loaders cannot write to any content collection.
- All loaders must share a canonical marker-detection module. Inconsistent detection across loaders is a correctness bug.
- Adding new `entry_type` values, marker flags, or QPT flags requires an ADR_006 amendment. Keep the enums disciplined.
- QPT flags are spec-only today; when the first QPT-aware loader is built, an amendment flips them from optional to required and triggers a QPT-detection backfill pass on existing chunks. Plan for this.

**Out of scope, flagged for later:**
- BUILD_GUIDE §7 revision to match ADR_006 — a future documentation-alignment pass.
- `dm_exchange`, `lab_summary`, `supplement_rec`, `qpt_reference`, `coaching_episode` type_metadata_json blocks — added when loaders are built.
- Clone-variant library-access rules (which library_names each variant is allowed to retrieve) — separate ADR.
- Phase 2 backfill detection method (regex vs LLM-assisted vs hybrid) — decided in the Phase 2 session.
- QPT detection and QPT flag backfill — deferred until the first QPT-aware loader exists.

---

## Cross-references

- **ADR_002 (registry, file records):** ADR_006 chunks carry `source_id`, `library_name`, `origin`, and `tier` that mirror the corresponding fields on the ADR_002 file record. A chunk's `source_id` must match an existing file record's `source_id` in `rf_library_index`. The ADR_002 2026-04-12 addendum (added in the same session as this ADR) defines the `origin` and `source_id` field generalization that ADR_006 chunks depend on.
- **ADR_005 (static libraries):** ADR_005 §4 defers the chunk contract to ADR_006. ADR_006 fulfills that forward reference. Static-library loaders (e.g., `ingest_a4m_transcripts.py`) must produce chunks conforming to this ADR, including all 48 marker flags populated by regex detection.
- **VECTOR_DB_BUILD_GUIDE.md §5 (44 Lab Markers):** The canonical marker list. ADR_006 §2's 48 marker flags are derived from this list. If BUILD_GUIDE §5 adds or renames a marker, ADR_006 amends at the same time.
- **VECTOR_DB_BUILD_GUIDE.md §7 (Vector DB Entry Schema):** ADR_006 extends the `entry_type` enum with `reference_transcript`, `reference_document`, `published_post`, `coaching_episode`; relaxes `client_id` from universal-required to optional; hoists `library_name`, `tier`, `origin`, `source_id` to universal-required; moves `metadata: {}` to `type_metadata_json` as a JSON-encoded string for Chroma compatibility; hoists marker references from nested metadata to 48 top-level boolean columns. BUILD_GUIDE §7 should be updated in a future pass to reference this ADR as the authoritative schema.
- **VECTOR_DB_BUILD_GUIDE.md §8 (Correlation model):** ADR_006 preserves the correlation fields (`client_id`, `linked_test_event_id`) and replaces the loose `markers_discussed` list with the 48 boolean flags. BUILD_GUIDE §8 timeline queries continue to work against `coaching_transcript` chunks — now with exact-match filtering rather than substring search.
- **VECTOR_DB_BUILD_GUIDE.md §13 (Client identification):** The `client_id` field on `coaching_transcript` chunks should use the canonical `RFID-XXX` form from the Client Program Key where available, falling back to the `RF-XXXX` form from the folder-name-derived script when not. This is a loader-level detail and should be documented per loader, not repeated here.
- **`docs/ARCHITECTURE.md`:** Gets a short pointer to ADR_006 under a new "Chunk metadata schema" section. No duplication of the schema.

---

*ADR originally drafted 2026-04-12 session 6 to close the forward reference from ADR_005 §4 and reconcile BUILD_GUIDE §7 with the ADR_002 + ADR_005 library/tier/origin model. Amended same session to replace pipe-delimited marker encoding with 48 boolean flags (after recognizing the T3/FT3 substring-collision risk) and to split the coaching-transcripts backfill into two phases so A4M ingestion is not blocked on marker-detection work. No loaders conforming to this contract exist yet — the A4M transcript loader (planned in the next session) will be the first.*
