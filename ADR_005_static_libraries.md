# ADR_005 — Static libraries: non-Drive sources for `rf_reference_library` and future curated collections

**Status:** Accepted (2026-04-12); amended same day to reflect BUILD_GUIDE review findings
**Supersedes:** none
**Related:** ADR_002 (Drive continuous diff + registry), ADR_004 (folder selection UI), ADR_006 (chunk reference contract), VECTOR_DB_BUILD_GUIDE.md

---

## Context

The RAG system has two fundamentally different content lifecycles, and conflating them in a single ingestion model would push the wrong abstraction onto both:

1. **Drive-walked content** — the *living* corpus. Folders in Google Drive are walked, diffed against a manifest, and surfaced in the folder-selection UI for assignment to libraries. ADR_002 governs this end-to-end.

2. **Static libraries** — curated, one-shot content drops. The A4M fertility course is the canonical example: 14 lecture transcripts and 15 slide decks that exist as files on a local Mac path (not in Drive), are loaded once, and don't change. Future examples include ACOG-style clinical reference snapshots, downloaded research bundles, and any other curated corpus that arrives as a fixed artifact.

A prior session attempted to model this as a `source_origin` field on a shared registry path — i.e., treat the distinction as "where the bytes came from." That framing is wrong. The real distinction is **content lifecycle**, not byte source: Drive content is walked-and-diffed because it changes; static libraries are loaded-and-left because they don't. Different lifecycle → different ingestion path → separate ADR.

The folder-selection UI (ADR_004 / `docs/plans/2026-04-11-folder-selection-ui.md`) already treats *libraries* as first-class destinations that Drive folders get *assigned to*. ADR_005 extends that conceptually: a library is an entity that contains chunks, and chunks can arrive at a library through two doors — Drive assignment (ADR_002 + ADR_004) or static-library load (this ADR). Same destination, different doors, no collision.

### Relationship to VECTOR_DB_BUILD_GUIDE.md

The canonical build guide (`/Users/danielsmith/Claude - RF 2.0/VECTOR_DB_BUILD_GUIDE.md`, dated April 3, 2026) was written before A4M was scoped as a reference library. Its §3 Data Source Map enumerates client-linked sources only (labs, coaching transcripts, IG DMs, IG posts, BBT, supplement protocols). It does not list curated external course material. ADR_005 fills that gap without contradicting anything in the guide: the guide's correlation model (§8) and unified ID system (§2) apply to client-linked content, and static-library content simply doesn't participate in those correlations. A recommended `3G. Reference Library Content (Non-Client-Linked)` addendum to the BUILD_GUIDE is flagged for a future session — tracked in `docs/BACKLOG.md`.

### Business-priority pivot note

BUILD_GUIDE §12 ("What to Build Next") lists immediate priorities as (1) lab data, (2) coaching transcripts, (3) retrieval layer, (4) IG data. Reference-library content (A4M) was not in that roadmap. Between April 3 and April 12, 2026, the `rf_coaching_transcripts` collection was built (fulfilling priority 2), and the near-term focus shifted to building `rf_reference_library` as the foundation for the public-facing sales agent's knowledge base. ADR_005 is partly a reflection of that priority pivot. The pivot is intentional and has Dan's approval.

---

## Decisions

1. **Static libraries are a distinct ingestion category from Drive-walked content.** ADR_002 stays Drive-scoped (with the 2026-04-12 addendum adding the `origin` field and generalizing the file record primary key); ADR_005 covers everything else. This is not an amendment to ADR_002's core design — it is a complementary ingestion path that writes into the same registry through a separate code path.

2. **Loaded via dedicated CLI scripts** (e.g., `ingest_a4m_transcripts.py`). No walk, no diff, no manifest. One-shot operations. Idempotency and re-ingestion semantics are the loader script's responsibility.

3. **NOT surfaced in the folder-selection UI.** The UI is Drive-only by deliberate design. Adding static sources would conflate two unlike lifecycles. This is **permanent**, not "for now." A future library inventory view (a separate admin surface, not the folder-selection UI) may show static-loaded and Drive-loaded content side-by-side; that is out of scope for this ADR.

4. **Shared chunk reference contract.** All chunks in the RAG system, regardless of byte source, must conform to the shared chunk reference contract defined in **ADR_006 (chunk reference contract)**. ADR_005 does not define the field list itself — ADR_006 does. ADR_005's only requirement is that static-library loaders produce output that conforms to ADR_006.

   The contract deliberately accommodates client-free content:
   - `client_id` is **optional**, not required as BUILD_GUIDE §7 originally implied. Static-library chunks (e.g., A4M lecture content) set it to `null`.
   - BUILD_GUIDE §8 correlation fields (`linked_test_event_id`, `markers_discussed`, `qpt_patterns_referenced`) are **optional**. Static-library chunks that don't apply to a specific client timeline leave them null rather than fabricating values. This keeps retrieval filters clean downstream.

   See ADR_006 for the full field list and extended `entry_type` enum.

5. **Registry integration — static-library write path.** Static-library loaders write file records to the `rf_library_index` ChromaDB collection (ADR_002) through a **separate code path** from the Drive walk/diff pipeline. Per the **2026-04-12 addendum to ADR_002**, the file record schema now supports this with:
   - A new `origin` field with value `"static_library"` (vs. `"drive_walk"` for Drive-native content).
   - A generalized primary key: `file:{source_id}` where `source_id = static:{library_name}:{relative_path}` for static-library files.
   - Nullable Drive-specific fields (`drive_file_id`, `drive_path`, `source_drive`, `source_folder_id`) when `origin == "static_library"`.
   - A new `local_path` field recording the absolute path on the local Mac the loader read from.
   - `content_hash` computed as sha256 of the file bytes (vs. md5 from Drive API for Drive-native files).

   The diff engine (ADR_002) explicitly filters `WHERE origin = "drive_walk"` and does not see static-library records. The folder-selection UI does the same. Static libraries are invisible to ADR_002's walk/diff/soft-delete machinery by design.

   This is no longer a forward-compat requirement — it is a **present-tense requirement**. The ADR_002 addendum locks the schema; the first static-library loader (A4M transcripts) is expected to conform to it from day one.

6. **Flexible CLI structure.** ADR_005 does NOT mandate one script per static library. A4M needed two (transcripts + slides) because transcripts use LLM-powered chunking and slides use rule-based per-slide PDF extraction. These are very different internal pipelines; forcing them into one script would be awkward. The constraint that matters is the **output contract** (ADR_006), not the script structure. One or more CLI scripts per static library, each producing chunks and file records that conform to the shared contracts.

7. **Naming and orthogonal dimensions.** The category name is **"static libraries"** (not "local libraries" — local is incidental, static is the actual property). The registry discriminator field name is **`origin`** with values `"drive_walk"` and `"static_library"`.

   **Orthogonality clarification.** Three independent dimensions classify content in the RAG system, and they should not be confused:

   | Dimension | Source ADR | Example values | What it answers |
   |---|---|---|---|
   | `tier` | ADR_002 | `reference | paywalled | published | clinical` | Who is allowed to retrieve this? (access control) |
   | `origin` | ADR_005 (this ADR) | `drive_walk | static_library` | How did this get into the registry? (ingestion path) |
   | `entry_type` | ADR_006 / BUILD_GUIDE §7 | `transcript | reference_transcript | reference_document | dm | ig_post | lab_summary | supplement_rec | qpt_reference` | What kind of content is this? (content type) |

   A single library like `a4m_course` has:
   - **tier** = `reference` (from ADR_002's starter list)
   - **origin** = `static_library` (all its files are CLI-loaded from a local path)
   - **entry_type** values across its chunks = `reference_transcript` (A4M transcripts) and `reference_document` (A4M slides)

   These three dimensions are independent. A future hybrid library could in principle contain `drive_walk` and `static_library` origins side-by-side; the `tier` would still be a single value for the whole library; `entry_type` would vary per chunk. ADR_002's diff engine and folder-selection UI filter on `origin`; ADR_006's retrieval layer filters on `tier` and `entry_type`.

---

## Consequences

**Enables:**
- Clean ingestion of curated, non-Drive corpora (A4M course, future clinical reference snapshots) without distorting the Drive lifecycle model.
- A coherent library-as-destination concept across both ingestion paths — libraries contain chunks regardless of byte source.
- A unified library inventory: with ADR_002's `origin` field in place, a single registry query can enumerate all content in a library across both ingestion paths. Today `a4m_course` is static-only; tomorrow a future admin view could show drive_walk + static_library content side-by-side for any hybrid library.
- CLI scripts stay purpose-built and pragmatic (one script can handle one source type, or multiple scripts can serve a single static library — A4M is the precedent).

**Constrains:**
- Static libraries cannot be managed through the folder-selection UI. Adding/removing/replacing them is a CLI + code-review operation, not a point-and-click one. This is intentional: static libraries change rarely, and the lifecycle does not benefit from a UI surface.
- All static-library loaders must produce chunks conforming to ADR_006's chunk reference contract, and file records conforming to ADR_002's file record schema as amended 2026-04-12. Loaders that predate either contract must be brought into compliance before the next static-library ingestion run.
- ADR_002's diff/manifest/walk machinery does not apply to static libraries. Deduplication, idempotency, and "what's already loaded?" semantics for static libraries are the loader script's responsibility. If a static library needs to be removed, it's a deliberate CLI unload operation — no soft-delete review queue (that path exists only for `drive_walk` origin records, per the ADR_002 addendum).
- **Static libraries are public-agent-eligible by default.** Because the Reference tier is accessible to the public sales agent (ADR_002 tier table), any content loaded into a Reference-tier static library flows through to the public agent. **Static-library loaders must verify that their source material contains no client-identifying data before ingesting.** A4M lecture content satisfies this trivially; future curated snapshots must be audited before loader scripts touch them. This is a soft guardrail, not enforced by schema — loader authors own it.
- ADR_006 must be read alongside this ADR. ADR_005 defines *the ingestion path*; ADR_006 defines *the output format*. A static-library loader that produces chunks not conforming to ADR_006 is non-compliant with ADR_005 §4.

**Out of scope (flagged for a later ADR):**
- How clone variants (content-gen, paid-client, public) declare which libraries they're allowed to draw from. This probably lives in agent YAML (`nashat_sales.yaml`, `nashat_coaching.yaml`, future content-gen config), not the UI. It touches ADR_005 only insofar as the chunk reference contract must carry enough metadata for variant-based retrieval routing — which ADR_006 addresses.

---

## Cross-references

- **ADR_002 (Continuous diff and registry):** Does not apply to static libraries in its original Drive-walk pipeline. ADR_002 governs the Drive-walk → manifest → diff → registry flow for living Drive content. Static libraries bypass this flow entirely and write registry entries through a separate code path with `origin: "static_library"`. The **2026-04-12 addendum to ADR_002** (added in the same session as this ADR) extends the file record schema with the `origin` field, the generalized `source_id` primary key, nullable Drive-specific fields for static records, and explicit rules for how the diff engine, folder-selection UI, and soft-delete machinery filter static-library records out. ADR_005 §5 now requires this addendum rather than treating the registry as aspirational.
- **ADR_004 (Folder selection UI):** The UI is Drive-only by design. See ADR_005 §3 for why static libraries are deliberately excluded from the UI surface. Libraries appear in the UI only as *destinations* that Drive folders get assigned to; static libraries populate those same destinations through CLI loaders. No UI changes required by ADR_005.
- **ADR_006 (Chunk reference contract):** Defines the per-chunk metadata contract that all loaders — Drive-walk and static-library alike — must produce. ADR_005 §4 mandates conformance but defers the field list to ADR_006. ADR_006 also extends BUILD_GUIDE §7's `entry_type` enum with `reference_transcript` and `reference_document` to accommodate static-library content.
- **VECTOR_DB_BUILD_GUIDE.md §3 (Data Source Map):** Does not currently list reference-library content. A recommended `3G. Reference Library Content (Non-Client-Linked)` addendum is flagged in `docs/BACKLOG.md` for a future session. This is a documentation-alignment item, not a blocker for A4M ingestion.
- **`docs/plans/2026-04-11-folder-selection-ui.md`:** The plan that confirmed libraries-as-destinations is the right shared abstraction for both ingestion paths.

---

*Originally drafted 2026-04-12 session 4. Amended same day (session 6) after BUILD_GUIDE review surfaced the registry-state misread, the client_id/correlation-field optionality issues, the orthogonality of tier × origin × entry_type, and the public-agent-eligibility guardrail. See `docs/HANDOVER.md` for the session trail.*
