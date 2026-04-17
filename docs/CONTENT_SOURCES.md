# CONTENT SOURCES — source-of-truth map for RAG ingestion

**Version:** 1.0 (session 28, 2026-04-16)
**Status:** active. Update via new BACKLOG entry whenever a domain is reassigned or a new domain surfaces.
**Closes:** BACKLOG #35

---

## How to read this doc

Each content domain below has:

- **Canonical source** — the file form that gets ingested. Everything else in that domain is skipped or declined.
- **Fallback** — what to ingest if the canonical form is unavailable for a specific item.
- **Form variants in Drive** — enumerated so a future maintainer knows what was declined and why.
- **Target collection** — which Chroma collection chunks land in (see "Collections" section below).
- **Gating notes** — handler, sensitivity, or cost blockers between decision and commit.
- **Status** — one of: ACTIVE (live in production), BLOCKED (waiting on infra), DEFER (decision captured, commit later), DEFERRED-DISCOVERY (sub-folder audit required before commit).

**This doc records decisions, not implementation timelines.** Adding a domain here does not commit to near-term ingestion; every commit follows the standard scope-and-halt flow per session prompt Operating Model.

---

## Framing — this is coaching, not medicine

Reimagined Fertility is a **coaching program**, not a medical practice. There is **no doctor-patient relationship** in this corpus, and therefore **no PHI** (Protected Health Information) in the legal/HIPAA sense.

Client-shared data (labs, MSQs, BBT charts, 1:1 session notes, Q&A chat questions) is **coaching data**, not clinical records. Access control is enforced by Cloudflare Access allowlist at the production edge (Dan + Dr. Nashat only), not by content redaction inside Chroma.

**Client-identity metadata.** Hardcoded-protected fields in `rf_coaching_transcripts` — `client_names`, `call_fksp_id`, `call_file` — are stored in chunk metadata but **never surfaced via YAML-configurable rendering** in agent responses. No knob can flip them. Every new coaching-data ingestion inherits this pattern.

**RFID status.** The existing `client_rfids` field is **not yet usable** — the RFID system is incomplete. Current values should be removed from chroma and reintroduced when the system is finalized. Once ready, RFID track-back is a desired capability (our own data, access-controlled, hardcoded-protected).

---

## Collections

Collections enforce access-tier boundaries (external vs public vs paywalled) at the retrieval layer. Each ingested file lives in exactly one primary collection; cross-references via metadata link to secondary retrieval surfaces.

| Collection | Status | Purpose |
|---|---|---|
| `rf_reference_library` | Active, 605 chunks (some misplaced — see Migration) | External-approved third-party content we're licensed to reference (A4M, DFH, future similar). Not our own content. |
| `rf_published_content` | Proposed | Our public-facing educational content: blogs, lead magnets, guides, email sequences. |
| `rf_curriculum_paywalled` | Proposed | Behind-paywall course material: FKSP/TFF/RH Detox lessons, FAQs, templates, bonus materials, Parenting Bundle (paid), Fertility Nutrition Materials. |
| `rf_coaching_transcripts` | Active, 9,224 chunks / 427 sources | Transcribed coaching-call content. `client_rfids` stale — remove pending RFID system completion. |
| `rf_coaching_visuals` | Proposed, blocked | BBT / MSQ / labs / slide captures from coaching-call videos, keyed by `call_fksp_id` + timestamp. |
| `rf_sales_playbook` | Proposed | Sales call transcripts (high-close + comparative low-close), IG DMs, prospect research. |
| `rf_marketing` | Proposed | Masterclasses, Dr. Meet & Greet, RF Meet the Doctors, Funnels copywriting. |
| `rf_testimonials` | Proposed | Testimonial images, videos, screenshots, text extractions. |
| `rf_visual_library` | Proposed | IG posts + Canva polished visuals. |
| `rf_internal_knowledge` | Proposed, conditional | Content-creation-tier only (not client-facing). Pending Dan two-tier decision per Domain 9. |
| `rf_supplements` | Proposed, defer | Product data for future Shopify supplements app. Handle with care. |
| `rf_lab_data` | Proposed, defer | Client lab results from all sources: Biocanic data downloads, client-provided labs (uploaded or shared in coaching), and Biocanic tool how-to content. |
| `rf_library_index` | ADR_002 design, backfill pending | Metadata-only retrieval index. |

**Migration needed for `rf_reference_library`.** Current composition: 584 A4M chunks (fit), 13 DFH Google Doc chunks (fit), 8 v3 chunks (partial misfit — Sugar Swaps is our lead magnet, not external). The misplaced 8 v3 chunks migrate to `rf_published_content` on creation. Per-chunk review required.

**Naming open:** the paywalled curriculum may consolidate as one collection (`rf_curriculum` with a `modality` metadata field) or split (text vs multi-modal). Resolution at first ingestion commit.

**Admin UI surface.** These collections become the selection targets in the admin UI `library_assignments`. Per-folder / per-file selection, per-item review workflows (Domains 4c / 7a / 8a), PDF polish-check gates (Domain 2), and two-tier access allow-lists (Domain 9) all surface here. Significant UI expansion work required — see BACKLOG #21 (folder-selection redesign) + the collection-expansion follow-up item.

---

## Domain 1 — Blog posts

**Canonical source:** Published HTML on the website.
**Secondary source:** Email broadcast form of the same blog content, if recoverable from the email platform (currently unknown whether archived in Drive; discovery task).
**Fallback:** Google Doc monthly compilations in `3-marketing/4. Blogs/` (39 docs organized by year/quarter; each doc contains multiple weekly blog posts for that month).
**Target collection:** `rf_published_content` (our public-facing educational output — not `rf_reference_library` which is for external content only).
**Status:** BLOCKED.
**Gating notes:**
- No HTML handler exists in v3 (current support: pdf, v2_google_doc, docx).
- No HTML dump of the blog currently in Drive.
- The session-18 dry-run against `April-May 2023 Blogs.docx` (BACKLOG #36) is **not** a commit path — docx is not canonical.
- Cross-domain dedup with Domain 3 (Email sequences) is a **hard requirement** — blog content was emailed, so the same material will surface via two canonical sources.

**Anti-ingestion within this domain:** docx exports, email broadcast copies once canonical HTML ships, any Kajabi HTML course-backup folders (those are curriculum, not blog).

---

## Domain 2 — Lead magnets

**Canonical source:** The `[RF] <Name>.pdf` delivered to customers.
**Fallback:** The `[RH] <Name>` Google Doc working copy (only for items that don't yet have a finalized PDF, e.g. `[RF] 7-Day Sleep Reset` currently has only a Google Doc).
**Target collection:** `rf_published_content` (our public-facing educational output — Sugar Swaps is currently misplaced in `rf_reference_library`, see Migration below).
**Status:** ACTIVE (Sugar Swaps currently ingested as Google Doc in wrong collection; see Migration below).
**Upgrade rule:** when a finalized PDF becomes available for a lead magnet currently ingested in a fallback form, re-ingest as PDF.

**PDF polish-check gate (required before any commit).** A provision must exist to confirm the PDF being ingested is a polished final, not a shared interim draft. Interim PDFs are unusual in the `3-marketing/7. Lead Magnets/[RF] <Name>/` folders (by convention the `[RF] <Name>.pdf` naming signals "delivered version"), but the check needs to exist. Implementation options pending a future BACKLOG item:
- Filename convention check (require exact `[RF] <Name>.pdf` pattern inside a `[RF] <Name>/` folder).
- Pre-ingest admin UI "confirm final" flag per file.
- Visual spot-check workflow with sign-off by Dan.

**Migration:** Sugar Swaps chunk (currently `v3_category=v2_google_doc`, len=3737, strip-ON) should be (a) moved out of `rf_reference_library` to `rf_published_content` when that collection exists, and (b) replaced with the PDF form. Combined migration work tracked as a new BACKLOG item at session 28 close.

**Scope of this domain (12 folders in `3-marketing/7. Lead Magnets/`):**
- `[RF] Thyroid Guide`, `[RF] 7-Day Sleep Reset`, `[RF] 4-Week Fertility Action Plan`, `[RF] Sugar Swaps Guide`, `[RF] Daily Fertility Checklist`, `[RF] FKSP Pre Call Guide`, `[RF] Low AMH Guide`, `[RF] Optimizing Sperm Health Guide & Checklist`, `[RF] Optimizing Egg Health Guide & Checklist`.
- In-progress (empty or no PDF yet): `[RF] Mini-Course`, `[RF] Post-Miscarriage Care Guide`.
- `[RF] How to Optimize Egg & Sperm Health funnel` (30 files) is **not a single lead magnet** — it's a complete funnel and belongs in a future sub-domain decision.

---

## Domain 3 — Email sequences

**Canonical source:** Email platform exports (Kajabi / ActiveCampaign / Mailchimp — specific platform source TBD).
**Fallback:** Google Doc copy decks in `3-marketing/5. Email Campaigns/Automations/` (88 docs organized by sequence: FKSP Sales Funnel, Fertility Formula Sales Funnel, RH Detox, FKSP Weekly Newsletters, Warm Up Sequences, etc.).
**Target collection:** `rf_published_content` (our own email output is public-facing educational, not external reference).
**Status:** BLOCKED.
**Gating notes:**
- Email platform export mechanism not yet built. Need to identify which platform is authoritative (Kajabi is most likely for current-era sequences) and build an export pipeline.
- No email-send handler exists.
- The 7 `.eml` files currently in `3-marketing/5. Email Campaigns/Automations/Reimagined Health - 4 Week Detox/` are all `TEST:` prefixed — test sends, **not canonical**.

**Cross-domain dedup with Domain 1 (Blogs).** Blog content was emailed (confirmed). Same material will surface via two canonical sources. Existing stage-2 content_hash dedup may cover trivial cases; canonical-beat rule across lineages needs explicit design before either source ships. Tracked as a BACKLOG item to be opened at session 28 close.

---

## Domain 4 — Program explainers, FAQs, program collateral

Broken into four sub-lanes because the `2-sales-relationships/` drive contains fundamentally different data types under one umbrella.

### 4a. Program explainers / FAQs / sales collateral (behind paywall)

**Canonical source:** PDF where present.
**Fallback:** Google Doc.
**Target collection:** `rf_curriculum_paywalled` (behind-paywall members-only — not `rf_published_content` which is public-facing, and not `rf_reference_library` which is external).
**Status:** ACTIVE (per-item commits follow lead-magnet pattern, but gate on paywall-collection creation).
**Scope:**
- `2-sales-relationships/FAQs/` (2 GDoc)
- `2-sales-relationships/2. TFF Enrollment/TFF Sales Call Collateral/` (2 pdf + 1 GDoc)
- `2-sales-relationships/2. TFF Enrollment/Bonus Materials upon enrollment/` (2 pdf)
- `2-sales-relationships/1. FKSP Enrollment/Templates/` (2 GDoc)
- ~~`2-sales-relationships/Live Dr Meet & Greet Sessions/`~~ — **moved to Domain 11 (Marketing).** Dr. Meet & Greet calls are public marketing content (like masterclasses), not paywalled curriculum.

### 4b. Coaching data (client-shared materials)

**Canonical source:** per-file (PDF where final, otherwise Google Doc).
**Target collection:** `rf_coaching_transcripts` for transcribed coaching-call material (already live); a future `rf_reference_library` or dedicated coaching-data collection for non-transcript coaching materials (TBD via ingestion behavior).
**Status:** ACTIVE (transcripts layer) + DEFER (non-transcript materials — per-folder selection via admin UI `selection_state`).
**Client-identity handling:** inherits the hardcoded-protected metadata pattern from `rf_coaching_transcripts` (`client_names`, `call_fksp_id`, `call_file`). **`client_rfids` should NOT be populated on new ingestion** — the RFID system is not yet finalized (s28 correction). Re-introduction of `client_rfids` deferred until the RFID system is complete. See Framing section above.

**Scope (per-folder selection enforced in admin UI, not content redaction):**
- `2-sales-relationships/1. FKSP Enrollment/!MEMBERSHIP/` — enrollment + membership coaching data
- `2-sales-relationships/1. FKSP Enrollment/!ACTIVE PROGRAM/` — active program coaching data
- `2-sales-relationships/1. FKSP Enrollment/!COMPLETED/` — post-program coaching data
- `2-sales-relationships/1. FKSP Enrollment/Coaching 1:1 Session Notes/` — 17 GDoc + 1 sheet
- `2-sales-relationships/1. FKSP Enrollment/FKSP Bonus Lab Reviews/` — 4 GDoc + 1 sheet
- `2-sales-relationships/1. FKSP Enrollment/Fertility Assessment Calls (Recorded)/` — 100 files (36 mp4 + 35 m4a + 20 docx). Audio/video portions gated on transcription pipeline; docx portions ingest now.
- `10-external-content/*Nikki's Projects/1:1 Client summary/Urvi & Nitesh Patel 11_17_25.docx.pdf` — individual 1:1 client summary
- `10-external-content/Zoom Chat Transcripts/` — 2 GDoc of chat-sidebar text from Weekly Q&A calls. High-value pedagogical content with real client questions.

**Gating notes:** every candidate file within these folders must be reviewed for managerial-vs-coaching disambiguation before commit. Managerial admin (enrollment paperwork, billing records, membership logistics paperwork) remains excluded even when it lives in the same folder as coaching data.

### 4c. Sales playbook / IG DMs / recorded sales calls

**Canonical source:** per-item review for PII-sensitive items; blanket-ingest for IG DMs + Nashat's high-close accelerator calls.
**Target collection:** `rf_sales_playbook`.
**Status:** DEFER.
**Scope:**
- IG DMs — Nashat's marketing/listening/closing conversations. Source: Nashat's IG account; export mechanism TBD.
- Fertility Accelerator calls — Nashat's high-close-% sales call transcripts (closing model).
- Prior salespeople's lower-close-% calls (20-30%) — comparative data. **Discovery needed** — likely in Taylor's or other shared Drives not in current walk.
- `2-sales-relationships/- Prospect & Sales Documentation/FKSP Call Research/` (85 files, mostly docx).
- `2-sales-relationships/Audits & Admin/Program Audits & Feedback/` (4 items).
- `10-external-content/Curated Sales Call List for May 2024/` (22 files: 11 mp4 + 11 otter_ai zip transcripts).

**Gating notes:** IG DM export pipeline, discovery of sales-call archives in Taylor's drives, and per-item admin-UI review workflow all required before commit.

### 4d. Fertility Nutrition Materials (course material, behind paywall)

**Canonical source:** PDF where present.
**Fallback:** Google Doc.
**Target collection:** `rf_curriculum_paywalled` (course material, members-only — per Dan s28: "course materials. behind paywall.").
**Status:** ACTIVE for decision; commit gated on paywall-collection creation.
**Scope:** `2-sales-relationships/Fertility Nutrition Materials/`
- `Fertility Reboot Guide & Resources/` (6 pdf)
- `Functional Nutrition Handouts/` (61 items: 54 pdf + 7 GDoc)
- `Module 2: Understanding Your Labs and Fertility Reboot/` (12 items: 9 pdf + 3 GDoc)

### 4-OUT — Anti-ingestion within `2-sales-relationships/`

**Confirmed OUT:**
- `Audits & Admin/Client Complaints and Disputes/` (252 files, 169 pdf) — legal/managerial exposure risk.

**IN (enables client-timeline linkage to coaching data):**
- `2. TFF Enrollment/TFF Program Contracts/` (46 pdf) — program-participation dates for lab-test-to-program alignment, first-name identification on call transcripts.
- `2. TFF Enrollment/TFF Program <date>/` cohort spreadsheets — same rationale.
- `1. FKSP Enrollment/!MEMBERSHIP`, `!ACTIVE PROGRAM`, `!COMPLETED` — covered by Domain 4b.

Target: client-timeline metadata surface (exact collection TBD). Hardcoded client-identity protection per Domain 4b.

---

## Domain 5 — Course curriculum

Four distinct sub-lanes because curriculum content exists in multiple forms with different canonical answers.

### 5a. Coaching call transcripts (textual layer)

**Canonical source:** `rf_coaching_transcripts` collection (9,224 chunks from 427 source mp4s).
**Status:** ACTIVE. No re-ingest.
**Gating notes:** any new coaching-call content follows the same transcription + diarization + topic-tagging pipeline. The reconcile-and-select source-of-truth for which calls were transcribed is at `https://docs.google.com/spreadsheets/d/1b6jPtWFKQUW-5qHUQgj37xVTV4Z6n2PGS_qD4xajHzQ/edit?gid=138019414#gid=138019414`.

### 5b. Coaching call visuals (BBT charts, MSQ, labs, shared screens)

**Canonical source:** NEW collection (proposed name `rf_coaching_visuals`) keyed by `call_fksp_id` + timestamp range.
**Status:** BLOCKED.
**Gating notes:**
- Source video reprocessing audit required — how many mp4s would need frame extraction.
- Cost model for frame extraction + OCR per minute of video.
- Scene-change-detection artifact discovery — existing transcription pipeline may already have this.
- **Critical for RF 2.0 app BBT-trends feature.**

### 5c. Kajabi course lesson mp4s — FULL RE-INGEST with multi-modal pipeline

**Canonical source:** multi-modal combination of:
- Option β (preferred): **pull slides directly from the PPTX/slide-deck source** + align with voiceover transcript of the video. Cleaner + cheaper + more accurate where PPTX exists.
- Option α (fallback): frame-capture of slide visuals + transcript of voiceover. Used only when no PPTX source exists.
**Target collection:** `rf_curriculum_multimodal` (proposed).
**Status:** BLOCKED.
**Scope:** **FKSP-family programs (FKSP, RH Detox, RH Preconception Detox — these three are the same content per Dan)** + **TFF (The Fertility Formula — the 6-week paid intro program, separate content)**. Source folder: `10-external-content/Kajabi Backups/` (confirmed as the live course).
**Gating notes:**
- Multi-modal handler design (not yet built).
- `10-external-content/Kajabi Backups/1. Fertility Kickstart Program/FKSP Lesson Slides/` has 32 PPTX alongside 42 mp4 — **the Option β alignment input** for FKSP-family.
- TFF slide-deck source: discovery pending — may or may not have PPTX in Drive.
- **Existing coaching transcripts do NOT cover these** — the course-lesson videos are separate from the live Q&A calls in 5a.
- Multi-modal re-ingest only needs **two distinct programs** (FKSP-family + TFF), not four — major scope reduction versus original framing.

**TFF client-access screening (optional future feature).** Filter TFF-paid content to TFF clients only (TFF = intro-level paid program; clients at higher tiers get broader access). Scope decision + implementation deferred to future session. See BACKLOG seed.

### 5d. A4M Fertility Course

**Canonical source:** existing 584 pre-scrub Lineage B chunks in `rf_reference_library`.
**Status:** GRANDFATHERED — no re-ingest unless doing so materially helps.
**Decision precedent:** BACKLOG #6b declined scrub retrofit s23. Reopen triggers: (a) future model that surfaces raw chunk text directly to users, OR (b) logging change that exposes former-collaborator refs in production responses. Neither trigger has fired.

**Collection fit:** External approved CME — fits the tightened `rf_reference_library` definition. Future external-approved content (other CME, licensed educational, partner-contributed) lands in the same collection.

### 5e. `Reimagined_Fertility_Docs_PDF_DOCX` (11-rh-transition, 26 files)

**Canonical source:** unknown.
**Status:** DEFERRED-DISCOVERY. Park until a future session determines what this folder contains (likely an export pairing of some existing program material; 13 pdf + 13 docx matched pairs suggests a packaged deliverable).

---

## Domain 6 — Coaching transcripts (rolled into Domain 5a above)

No separate ruling. Covered by 5a.

---

## Domain 7 — 1:1 Zoom recordings in `10-external-content/`

### 7a. Named-client zoom recordings (Shana, Kim, Nicole, Melissa, Jen, Erika, `1:1`)

**Canonical source:** whatever subset is already in `rf_coaching_transcripts` per the reconcile spreadsheet at `https://docs.google.com/spreadsheets/d/1b6jPtWFKQUW-5qHUQgj37xVTV4Z6n2PGS_qD4xajHzQ/edit?gid=138019414#gid=138019414`.
**Status:** DEFER — reconcile-and-select per spreadsheet before any further ingestion.
**Scope:** 240 mp4 files across named sub-folders. The core coaching content is already mostly captured in 5a; this domain exists to handle additions/corrections.

### 7b. Transkriptor Assets

**Anti-ingestion.** Deprecated/incorrect transcripts. **SKIP.** Retained in Drive for historical reference only.

### 7c. `10-external-content/Kajabi Backups/`

Covered by Domain 5c (this is the canonical source for curriculum multi-modal re-ingest).

### 7d. `Parenting Bundle - Nichole Morris` (62 files, 61 pdf)

**Canonical source:** PDF where present, Google Doc fallback.
**Target collection:** `rf_curriculum_paywalled` (paid content — RF-owned multi-author summit bundle).
**Status:** Decision active; commit gated on paywall-collection creation.

### 7e. `Curated Sales Call List for May 2024`

Covered by Domain 4c.

### 7f. `*Nikki's Projects`

- `RH Clients Audits` spreadsheet — **SKIP** (managerial).
- `1:1 Client summary/Urvi & Nitesh Patel 11_17_25.docx.pdf` — Domain 4b (coaching data).

### 7g. `Zoom Chat Transcripts` (2 GDoc)

Covered by Domain 4b (coaching data — high-value pedagogical content with real client questions).

### 7h. Minor folders parked for future discovery

`*Nikki's Projects` audit spreadsheet, no canonical beyond what's above.

---

## Domain 8 — Dr. Nashat + Dr. Christina Zoom recordings (`11-rh-transition/`)

### 8a. `Dr. Christina's Zoom Call Recordings` (407 files)

**Canonical source:** coverage already in `rf_coaching_transcripts` per reconcile spreadsheet. Items beyond that need individual categorization.
**Status:** DEFER — reconcile-and-select per spreadsheet + intelligent scan (see below).

**Intelligent-scan requirement.** Volume (551 combined recordings across Christina + Nashat) makes per-file human review impractical. Need an LLM classifier to categorize each recording (coaching / sales / marketing / business-ops / unknown) before review. See BACKLOG seed.

### 8b. `Dr. Nashat's Zoom Recordings/` — per-sub-folder rulings

| Sub-folder | Ruling |
|---|---|
| `The Fertility Formula 2.0` (4 mp4) | → Domain 5c (TFF curriculum re-ingest) |
| `RH: Sales and Operation Meeting` (3) | **SKIP** (managerial) |
| `RH: January Detox Call 2024` (8) | Domain 5a — reconcile w/ `rf_coaching_transcripts` |
| `Masterclass Recording 2025` (6) | → Domain 11 (marketing content) |
| `Masterclass Recordings 2024` (3) | → Domain 11 (marketing content) |
| `RF Meet the Doctors` (1) | → Domain 11 (marketing content) |
| `Ignite Marketing + Reimagined Health` (1) | **SKIP** (business event) |
| `My Meeting` (1) | **SKIP** (unknown, low-value) |

---

## Domain 9 — Operational content (`1-operations/`)

**Status:** DEFERRED-DISCOVERY.

**Default posture:** client-facing agents do not retrieve from `1-operations/`. SOPs, systems, training, website dev, teams etc. are internal operational content.

**Two-tier access question (guidance requested).** Some operational content (EHT Summit Blueprints, strategic frameworks, internal playbooks) is valuable for a *content-creation* agent Dan/Nashat/team uses internally, but must never surface to client-facing agents. Target: `rf_internal_knowledge` collection with agent-level allow-list. Dan decision pending.

**Known exceptions:**
- `1-operations/FKSP Transcript Repository/` — historical source of the 427 mp4s in `rf_coaching_transcripts`. Reference only; no re-ingest.
- `1-operations/EHT Summit Blueprints/` — strong candidate for content-creation-tier `rf_internal_knowledge`.
- `1-operations/Parenting Bundle - Nichole Morris/` (if present) — covered by Domain 7d.

**Future session:** per-sub-folder audit of Masterfiles / SOPS / Training / Systems / Website Dev / Teams / etc. + Dan decision on two-tier framing. See BACKLOG.

---

## Domain 10 — Drives not shared / not-for-ingestion

**Hard anti-ingestion.**
- `4-finance` — not shared with service account, sensitive flag set, anti-ingestion even if ever shared.
- `5-hr-legal` — not shared with service account, sensitive flag set, anti-ingestion even if ever shared.
- `0-shared-drive-content-outline` — not shared (phase-B pending), scope decision deferred to whenever it becomes visible.

---

## Domain 11 — Marketing content

**Target collection:** `rf_marketing` (primary) + `rf_testimonials` (split for testimonials).
**Status:** BLOCKED on multi-modal handler + per-asset discovery.

### 11a. Masterclasses + Meet & Greet (video teaching)

Free front-of-paywall teaching. Canonical: mp4 + multi-modal transcript + visual extraction (Domain 5c pipeline).
**Scope:**
- Dr. Nashat's masterclass recordings 2024 + 2025 (9 mp4)
- RF Meet the Doctors (1 mp4)
- Live Dr Meet & Greet Sessions (7 items, moved from 4a)

### 11b. Testimonials & Case Studies

Multi-modal testimonial assets — images, videos, screenshots, text extractions. Used by sales agent, content-creation, and website/Shopify surfaces.
**Target collection:** `rf_testimonials` (split from `rf_marketing`).
**Scope:** `3-marketing/9. Testimonials & Case Studies/` (inventory needed).

### 11c. Funnels copywriting

Landing pages, email copy tied to funnels, ad copy, sales pages. High-value costly-to-produce copy.
**Target collection:** `rf_marketing`.
**Scope:** `3-marketing/3. Funnels/` (inventory needed).

### 11d. Other `3-marketing/` candidates (future discovery)

`11. Summit`, `2. Social Media`, `12. Affiliates`, `8. Collabs`, `6. Facebook Ads`, `1. Brand Assets`. Per-folder audit needed before routing.

**Gating notes:** cross-domain dedup with Blogs (thematic overlap) and Visual Library (IG/FB asset overlap).

---

## Domain 12 — Supplements (`7-supplements/`)

**Canonical source:** TBD (per-item mix of PDF product sheets, Google Docs, product images).
**Target collection:** `rf_supplements` (proposed).
**Status:** DEFER — discovery + design work needed.
**Rationale:** future Shopify supplements app sells supplements to clients. Recommendation accuracy directly affects client outcomes and revenue.
**Handle-with-care requirements:** product-data validation (doses, brands, SKU linkage), dedicated review workflow, strict separation from educational collections so general queries don't surface specific product recommendations without proper sourcing.
**Gating notes:** distinct retrieval surface from educational content. Handler design + dedicated workflow required before any commit.

---

## Domain 13 — Lab data library

Client lab data from all sources. Biocanic is one source among several — clients also provide labs directly (uploads, coaching-call shares, email attachments).

### 13a. Biocanic lab-results data download

Bulk extract of client lab results from the Biocanic tool.
**Target collection:** `rf_lab_data`.
**Status:** DEFERRED-DISCOVERY — planned for later in the build.

### 13b. Client-provided lab results

Lab results clients share directly — uploaded via admin UI, shared during coaching calls, emailed in, etc.
**Target collection:** `rf_lab_data`.
**Status:** DEFER — intake pipeline design needed (upload UI, parser for common lab PDF formats, PII handling consistent with Domain 4b).

### 13c. Biocanic tool how-to tutorials

**Canonical source:** tutorial videos + onboarding forms in `9-biocanic/Biocanic Client Tutorials/` and `9-biocanic/Biocanic Onboarding Forms/`.
**Target collection:** `rf_lab_data` (supporting documentation — how to read/interpret labs via the tool) or fold into `rf_curriculum_paywalled` if tutorials are part of FKSP paid program.
**Status:** DEFER.

---

## Domain 14 — Visual content library (IG posts + Canva)

Polished visual repo supporting all published/marketing surfaces. Distinct retrieval intent from marketing ("find a visual to reuse" vs "find teaching/copy content").

**Canonical source:** IG post files (image + caption) and Canva document exports (PNG + PDF + editable sources).
**Target collection:** `rf_visual_library`.
**Status:** DEFERRED-DISCOVERY.
**Scope sources:**
- Nashat's IG account archive
- Canva corporate account
- `3-marketing/1. Brand Assets/` and `3-marketing/2. Social Media/`

**Gating notes:** IG archive export + Canva export pipelines both need design. Cross-collection overlap expected with `rf_testimonials`, `rf_published_content`, `rf_marketing` — primary placement here, cross-refs via metadata.

---

## Anti-ingestion — consolidated list

For quick reference, content that should **never be ingested into any RAG collection**, regardless of future decisions:

- **Legal exposure:** `2-sales-relationships/Audits & Admin/Client Complaints and Disputes/` — probably blocked (legal/managerial). TFF Program Contracts + cohort spreadsheets **were previously on this list but are now IN scope** per Dan s28 (see Domain 4-OUT reversal); they move to Domain 4b/4c-paywalled-curriculum surface.
- **Not-shared sensitive drives:** `4-finance/`, `5-hr-legal/`.
- **Deprecated artifacts:** `10-external-content/Assets/Transkriptor Transcriptions/` and `Transkriptor_Combined_Files/` — old transcripts, incorrect.
- **Internal business events (need per-item review or default-skip):** `11-rh-transition/Dr. Nashat's Zoom Recordings/RH: Sales and Operation Meeting/`, `.../Ignite Marketing + Reimagined Health/`, `.../My Meeting/`. The Domain 8 intelligent-scan (s28) may re-categorize some of these once run.
- **Test artifacts:** any `TEST:` prefixed `.eml` files in `3-marketing/5. Email Campaigns/Automations/`.

---

## Cross-cutting rules

1. **Hardcoded-protected client-identity metadata.** Any new collection that ingests client-linked content inherits `client_rfids` / `client_names` / `call_fksp_id` / `call_file` as hardcoded-protected metadata fields — never surfaced via YAML-configurable rendering. Matches `rf_coaching_transcripts` precedent.

2. **PDF polish-check (Domain 2).** No PDF enters a lead-magnet-style ingestion without confirming it's a final, not an interim shared draft. Implementation pending future BACKLOG.

3. **Per-item review workflow (Domain 4c, 7a, 8a).** Some domains require Dan-level review of every candidate file before ingestion. Needs admin UI support for review-and-select alongside the existing folder-level selection. Pending future BACKLOG.

4. **Cross-domain dedup (Domains 1 + 3, and 11 + 1).** Content that was authored once and distributed in multiple forms (blog-then-email, masterclass-referenced-in-blog) must be dedup'd at ingestion. Existing stage-1 md5 + stage-2 content_hash cover the trivial cases; canonical-beat rules across lineages need explicit design. Pending future BACKLOG.

5. **Multi-modal pipeline (Domains 5b, 5c, 11).** Slide-deck alignment (Option β) is preferred over frame-capture-plus-OCR (Option α) where PPTX sources exist. Accuracy is non-negotiable — the whole RF 2.0 BBT-trends feature depends on correct visual extraction.

6. **Access control, not content redaction.** The RAG system is access-controlled at the Cloudflare Access edge. Content redaction inside chunks is not the privacy mechanism; access control is. This frees ingestion to preserve client-linked context needed for longitudinal features.

7. **Update protocol.** Any session that reassigns a canonical source, adds a domain, or promotes a DEFER to an ACTIVE ingestion must update this doc in the same commit per the Operating Model governance trigger.

8. **Domain overlap is expected.** A testimonial quote may live in `rf_testimonials` (primary), be referenced in a masterclass (`rf_marketing`), and quoted in a blog (`rf_published_content`). Framework: **one primary collection per asset, cross-refs via metadata.** Dedup at query time, not at ingestion.

9. **Two-tier access (pending decision per Domain 9).** Some collections may be retrievable only by internal content-creation agents, not client-facing ones. Agent-level YAML allow-list enforces. `rf_internal_knowledge` is the proposed internal-only collection.

---

## Open follow-up BACKLOG items to open at session 28 close

Tactical items to open as BACKLOG entries:

- Create `rf_published_content` + migrate misplaced chunks (Sugar Swaps confirmed; 7 other v3 chunks need per-chunk review)
- Create `rf_curriculum_paywalled` (gated on paywall-access-enforcement design)
- Create `rf_sales_playbook` (gated on IG DMs export + sales-call discovery)
- Create `rf_marketing`, `rf_testimonials`, `rf_visual_library` (each gated on its handler/export)
- Create `rf_lab_data` + design client-lab-upload intake pipeline (admin UI upload, PDF lab-report parser, PII handling per Domain 4b)
- Create `rf_internal_knowledge` (conditional on Dan two-tier decision)
- Sugar Swaps PDF re-ingest + move to `rf_published_content`
- Remove stale `client_rfids` from `rf_coaching_transcripts`
- HTML blog-scraping / export (Domain 1)
- Email platform export mechanism (Domain 3)
- Multi-modal ingestion handler, slide-deck alignment preferred (Domains 5b / 5c / 11a)
- IG DMs export mechanism (Domain 4c / 14)
- Canva export pipeline (Domain 14)
- IG posts archive export (Domain 14)
- Testimonial multi-modal handler (Domain 11b)
- Per-item review-and-select admin UI workflow (Domains 4c / 7a / 8a)
- PDF polish-check gate (Domain 2)
- Find high-close accelerator + comparative prior-salesperson calls in Taylor's / other shared drives (Domain 4c)
- 1-operations sub-folder audit (Domain 9)
- 6-ideas-planning-research sub-folder audit (Domain 10 / drive 6)
- TFF slide-deck source discovery (Domain 5c)
- 3-marketing sub-folder inventory — Testimonials / Funnels / Summit / Collabs / Affiliates / Facebook Ads (Domain 11b-d)
- Cross-domain dedup canonical-beat rules (Domains 1 + 3 + 11 + 14)
- Intelligent-scan classifier for zoom recordings (Domain 8a)
- Two-tier access framing decision (Domain 9)
- TFF client-access screening feature decision (Domain 5c)
- Paywalled curriculum collection naming — single vs split for text-vs-multimodal
- Ingest TFF Program Contracts + cohort spreadsheets (4-OUT reversal)
- Collection-expansion admin UI work — all 11+ collections as `library_assignments` targets (tied to BACKLOG #21 folder-selection redesign)

---

## End of CONTENT_SOURCES.md
