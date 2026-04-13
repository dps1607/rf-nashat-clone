# COACHING_CHUNK_CURRENT_SCHEMA — current metadata shape of `rf_coaching_transcripts`

**Captured:** 2026-04-13 (session 8, step 1 / Gate 1)
**Source:** `scripts/peek_coaching_schema.py` run against local ChromaDB at `/Users/danielsmith/Claude - RF 2.0/chroma_db/`
**Method:** `coll.get(limit=5, include=["metadatas", "documents"])`. Strictly read-only.

**Purpose.** Single source of truth for the current on-disk metadata shape of `rf_coaching_transcripts` chunks. Required input for Plan 2 (Phase 1 structural backfill, session 8). Before session 8 this shape existed only in the live Chroma DB and was not documented anywhere in the repo — session 7 strategic concern #2 (cheap insurance). This doc fixes that.

---

## Collection state

| Field | Value |
|---|---|
| Collection name | `rf_coaching_transcripts` |
| Total count | **9,224** |
| Expected (session 7 HANDOVER) | 9,224 |
| Match | ✅ |
| Other collections in this Chroma | `rf_reference_library` (covered separately in `A4M_LEGACY_CHUNKS_INVENTORY.md`) |

---

## Metadata key inventory

12 metadata keys observed across the 5-sample union. Shape is uniform across the sample — every sampled chunk has all 12 keys.

| Key | Inferred type | Sample value | Null/empty rate | ADR_006 routing |
|---|---|---|---|---|
| `call_file` | string | `"bf085d1-c70e-d0cb-e52d-cc5ff345dd_Fertility_Kickstart_Program_Weekly_Q_A_530pm_CST.mp4"` | 0/5 | → `source_name` (top-level) AND preserved in `type_metadata_json` |
| `call_fksp_id` | string | `"FKSP-QA-001"` | 0/5 | → `type_metadata_json.fksp_id` (per ADR_006 §4 coaching_transcript block) |
| `call_date` | string | `""` (empty) | 5/5 empty | → top-level `date` if non-empty, else `null`; preserve raw in `type_metadata_json.call_date_raw` |
| `call_type` | string | `""` (empty) | 5/5 empty | → `type_metadata_json.call_type` per ADR_006 §4 (enum: Q&A / Lab Review / VIP / Mind+Body / Coaching / TFF / GASP); null on these samples |
| `call_section` | string | `"1 - FKSP WEEKLY Q&A CALLS (PRIMARY CLINICAL DATA)"` | 0/5 | → `type_metadata_json.call_section` (not in ADR_006 §4 standard block but preserved per don't-drop-data) |
| `coaches` | string | `"Dr. Nashat (primary) + Dr. [REDACTED-EXCLUDED]"` | 0/5 | → `type_metadata_json.coaches_raw`. **Never** hoisted to top-level `speaker`. Retrieval layer must scrub on render (see Strategic concern below). |
| `topics` | string | `"Stress/Cortisol\|Labs General"` (pipe-delimited, NO bookend delimiters) | 0/5 | → top-level `topics`, **normalized** to lowercase bookend-delimited form per ADR_006 (`"\|stress_cortisol\|labs_general\|"`). Also preserved raw in `type_metadata_json.topics_raw` for audit. |
| `start_time` | string | `"00:00:17"` | 0/5 | → `type_metadata_json.start_time` |
| `end_time` | string | `"00:03:45"` | 0/5 | → `type_metadata_json.end_time` |
| `word_count` | int | `584` | 0/5 | → `type_metadata_json.word_count` |
| `client_rfids` | string (literal `"[]"`) | `"[]"` | 5/5 empty-list-as-string | NOT hoisted. Cleared per 2026-04-10 wipe (see "Drift correction" below). Preserved in `type_metadata_json.client_rfids_raw` for audit, otherwise dropped at top level. |
| `client_names` | string (literal `"[]"`) | `"[]"` | 5/5 empty-list-as-string | Same as `client_rfids`. |

**No ADR_006 universal fields are present.** Specifically absent: `chunk_id` (it's a Chroma primary-key string on the row, not a metadata field — see below), `text` (lives in `documents`, not metadata), `collection`, `library_name`, `entry_type`, `origin`, `tier`, `source_id`, `chunk_index`, `chunk_total`, `ingested_at`, `client_id`, `linked_test_event_id`, none of the 48 `marker_*` flags, none of the 25 `qpt_*` flags, `markers_discussed`, `speaker`, `recommendations_given`, `type_metadata_json`. **Session 8 Plan 2 creates all of these from scratch.**

**Chunk ID format (row primary key, not metadata):** `CHUNK-0000-000`, `CHUNK-0000-001`, `CHUNK-0000-002`, … Pattern appears to be `CHUNK-{file_index_4digit}-{chunk_index_3digit}`. Well-formed (unique, deterministic, readable) but **not ADR_006-conformant**. ADR_006 §2 specifies `{library_name}:{entry_type}:{source_component}:{chunk_index_zero_padded}`. See "Plan 2 mapping resolution" below for how this is handled.

---

## Sentinel verification

### Post-2026-04-10 RFID wipe

- **`client_rfids` present on all 5 sampled chunks as the literal string `"[]"`.** Not removed, not null — stored as empty-list-as-string.
- **`client_names` present on all 5 sampled chunks as the literal string `"[]"`.** Same shape.

**Drift correction needed in session 8 HANDOVER entry.** Session 7 HANDOVER claims the wipe "cleared" these fields; the REPO_MAP claims "all `client_rfids` and `client_names` metadata fields cleared." The actual on-disk state is that the field **keys still exist** and **values are the string `"[]"`**. Plan 2's post-wipe sanity preflight must test for `value in ("", "[]", None, "null")` rather than `field not in metadata`.

The semantic intent of the wipe — "no chunk is currently tagged to a client" — holds: `"[]"` is semantically empty. Plan 2 proceeds as planned; Phase 1 writes `client_id: None` and `linked_test_event_id: None` on every chunk regardless of the legacy `client_rfids`/`client_names` string values.

### Re-run-after-Phase-2 guard

- **No `marker_*` keys observed on any sampled chunk.** Consistent with Phase 2 not having run. Plan 2 is safe to populate all 48 flags as explicit `False`.

---

## Plan 2 mapping resolution

Filling in the cells from the HANDOVER session 7 Plan 2 mapping table that the inventory was supposed to resolve.

| ADR_006 field | Resolved source |
|---|---|
| `chunk_id` | **Synthesize via `build_chunk_id()`**. The existing `CHUNK-NNNN-III` IDs are readable but not ADR_006-conformant, and the ADR_006 format is load-bearing for cross-library consistency. The Chroma row primary key (`ids` in the `get`/`update` API) stays as `CHUNK-NNNN-III` — **Plan 2 does NOT rename row IDs** because that requires delete+re-insert (touches embeddings) rather than metadata-only update. The new ADR_006-format chunk_id is stored as a **metadata field** named `chunk_id`, with format `historical_coaching_transcripts:coaching_transcript:{source_file_stem}:chunk_{chunk_index:04d}`. Retrieval code that needs the ADR_006 ID filters on the metadata field; Chroma-internal operations continue to use the row primary key. This is consistent with ADR_006 §2 which specifies chunk_id as a metadata field on the chunk, not necessarily as the Chroma row primary key. |
| `chunk_index` | **Derived from the row primary key suffix.** The `CHUNK-NNNN-III` format encodes file index and per-file chunk index directly. Plan 2 parses the row ID as `CHUNK-{file_idx}-{chunk_idx}` and takes the `chunk_idx` part. No existing metadata field provides this. |
| `chunk_total` | **Computed by grouping all 9,224 row IDs by `call_file`, counting per group.** Single in-memory pass during the build phase. |
| `source_id` / `source_name` | **`source_name` = existing `call_file` value unchanged.** `source_id` = `call_file` value (Option B: filename-based, per session 7 tactical decision — not reconstructed to Drive file ID). |
| `source_path` | `null`. No path-like field in current metadata. |
| `date` | `null` on all sampled chunks because `call_date` is empty string. Future backfill may populate from the Zoom pipeline. |
| `speaker` | `null` at top level. The existing `coaches` field contains a string like `"Dr. Nashat (primary) + Dr. X"` which is file-level, not chunk-level, and mixes names with guardrail-sensitive content. Route raw value to `type_metadata_json.coaches_raw`. |
| `topics` | **Top-level `topics` = normalized** from existing `topics` field. Normalization: lowercase, spaces/slashes → underscores, pipe-delimited with bookend delimiters. Example: `"Stress/Cortisol\|Labs General"` → `"\|stress_cortisol\|labs_general\|"`. Raw value preserved in `type_metadata_json.topics_raw`. |
| `recommendations_given` | `null`. No existing field. Phase 2 or a future pass may populate. |
| `type_metadata_json` | JSON-encoded string. Contains the full ADR_006 §4 `coaching_transcript` block where data is available (much will be null), plus preserved raw fields: `call_file_raw`, `call_fksp_id` (as `fksp_id`), `call_date_raw`, `call_type_raw`, `call_section`, `coaches_raw`, `topics_raw`, `start_time`, `end_time`, `word_count`, `client_rfids_raw`, `client_names_raw`. Don't-drop-data principle: every existing field has a home. |

**Existing fields routed entirely to `type_metadata_json`** (not hoisted to any top-level ADR_006 field):
`call_fksp_id`, `call_section`, `coaches`, `start_time`, `end_time`, `word_count`, `client_rfids`, `client_names`, `call_date` (when empty), `call_type` (when empty).

**Existing fields hoisted to a top-level ADR_006 field (and also preserved raw in `type_metadata_json`):**
`call_file` → `source_name` + `source_id`; `topics` → normalized top-level `topics`.

---

## Strategic concerns surfaced by the inventory (for session 8 HANDOVER)

1. **Dr. Christina is embedded in every coaching chunk's `coaches` metadata value.** The guardrail says never surface her to users; the retrieval layer must scrub or drop the `coaches` field on render. Session 8 does not touch retrieval code, so this is a **flag for the next retrieval-layer change**, not an action item for this session. Adding to BACKLOG / session 8 HANDOVER strategic concerns.

2. **`SPEAKER_NN` diarization labels appear in chunk document text.** Already known (Dr. Chris internal only, per ARCHITECTURE guardrails) but worth restating: any retrieval-time renderer must either strip or remap `[SPEAKER_NN]` before sending to a user-facing agent. Not a session 8 action.

3. **Drift in "post-wipe state" language.** HANDOVER session 7 says fields were "wiped/cleared"; actual state is values are the literal string `"[]"`. Correcting in session 8 HANDOVER.

4. **`topics` is NOT bookend-delimited in current storage.** Every retrieval query that does a `$contains: "|stress_cortisol|"` filter against these chunks will **silently return zero hits** until Plan 2 normalizes them. No filter query currently depends on this (the retrieval layer doesn't filter on `topics` yet per my reading), so no production breakage — but Plan 2's normalization is load-bearing for any future `topics` filter. Flagging so it's not a surprise later.

---

## Next step (Step 2 / Gate 2)

With the inventory captured, session 8 proceeds to build the shared infrastructure (`ingester/marker_detection.py` + `ingester/backfills/_common.py`), then Plan 1 (A4M migration) can consume that infrastructure, then Plan 2 (Phase 1 backfill) consumes both the infrastructure AND this schema doc to build its field mapping safely.
