# ADR 003 — Canva design library deduplication mechanism

**Date:** 2026-04-11
**Status:** PROPOSED — design deferred
**Proposer:** Daniel Smith
**Context:** Phase A design pass for the RF RAG build. Locked
structurally as part of ADR-002 Q1 (library taxonomy). Detailed
deduplication mechanism deferred to its own ADR to avoid burying a
non-trivial design inside the taxonomy ADR.

---

## Status note

This ADR is a STUB. The structural decision (Canva is its own
Reference-tier library; channel libraries reference it rather than
re-ingesting visuals) is **locked** as part of ADR-002. The actual
deduplication mechanism — how we detect that two files in different
folders are the "same" Canva design — is **not yet designed** and is
captured here as open questions for a future design pass.

---

## The problem in one paragraph

The Reimagined Fertility Canva account contains a large body of
on-brand visual assets (carousels, infographics, lead magnets, blog
graphics, IG content, masterclass slides, etc.). The canonical
versions live inside Canva. Exported copies — PNGs, JPGs, PDFs — get
copied out of Canva and into Google Drive, where the same design
ends up in multiple folders: an IG carousel folder, a lead magnets
folder, a blog post folder, possibly inside a course module's
materials. **The same underlying Canva design exists in Drive as
many distinct files**, with different names, in different folders,
with different file IDs. Naive ingestion would treat each copy as a
separate asset, run vision enrichment on each, embed each, and store
near-identical chunks across multiple libraries — wasting Vertex AI
budget, polluting retrieval with duplicates, and lying to the agent
about how much distinct content it actually has.

---

## The structural decision (locked in ADR-002)

- A single Reference-tier library, **`canva_design_library`**, is
  the canonical home for every distinct Canva design.
- Each entry in the library represents one **distinct design**, not
  one file. A design that exists in Drive as 5 exported copies is
  *one* entry, not five.

- Channel libraries (`ig_content`, `lead_magnets`, `blog_posts`,
  potentially others) **reference Canva entries by ID** rather than
  re-ingesting the visual content. They store channel-specific
  metadata (caption, post date, campaign tag, engagement metrics if
  available) and a pointer to the underlying Canva entry.
- The registry tracks the `distribution` of each Canva entry: a
  pipe-delimited list of `(channel_library, channel_asset_id,
  first_seen_date)` records showing every place a design has appeared.
- Vision enrichment runs **once per distinct design**, not once per
  file copy.

This is locked. The deduplication mechanism that makes it work is
what this ADR will design.

---

## What "the same design" means (and why it's hard)

Detecting that two files are the same Canva design is harder than it
sounds because there are several distinct cases:

1. **Byte-identical exports.** Same Canva file, exported once,
   copied to two folders. MD5 of file bytes is identical. Easy.
2. **Re-exports of the same Canva design.** Same source, exported
   twice on different days. May be byte-identical or may differ in
   metadata bytes. Often easy, sometimes not.

3. **Same design exported at different resolutions.** Common — IG
   wants one size, blog wants another, lead magnet wants print
   resolution. Bytes are completely different. Visually identical
   when normalized.
4. **Same design with one element changed.** A color tweak, a text
   edit, a logo update. 95% visually identical, 5% different.
   Probably should be treated as "the same design, version 2."
5. **A new "version 4" of an existing design.** Conceptually a
   continuation of an existing series, visually quite different.
   Probably should be a different entry but linked to its predecessors.
6. **A genuinely new design that happens to use the same template.**
   Same brand colors, same fonts, same layout — different content.
   Should be a different entry.
7. **A Canva file vs. an exported PNG of the same Canva file.**
   Same conceptual design, completely different file representations.

A useful deduplication mechanism handles cases 1, 2, 3, and 4
correctly, treats 5 as a versioning question, and correctly
identifies 6 as distinct.

---

## Open questions for the design pass

1. **Hashing strategy.** Exact-byte hashing (MD5/SHA-256) handles
   only case 1 reliably and case 2 sometimes. Perceptual hashing
   (pHash, dHash, aHash via the `imagehash` library) handles cases
   1 through 4. Content-based hashing for PDFs (text + image
   extraction + normalized hash) might handle PDF exports better
   than perceptual hashing alone. Current lean: exact-byte for fast
   initial pass, perceptual hash for the slower deeper pass.

2. **The Canva API as canonical source.** The cleanest long-term
   answer is to ingest directly from Canva via the Canva API,
   treating each exported copy in Drive as a "distribution record"
   pointing back to the canonical Canva entry. This eliminates the
   need to dedupe across Drive at all. Question: does Canva's API
   give us enough access to make this practical? At what cost? With
   what auth model?

3. **Match threshold for perceptual hashing.** Perceptual hashes
   produce a similarity score, not a boolean. What threshold counts
   as "same design"? Likely needs empirical tuning against a sample
   of real RF Canva content.

4. **Versioning behavior for near-matches.** When the dedup engine
   detects a near-match (cases 4 and 5): treat as new entry linked
   to predecessor, replace predecessor entirely, or flag for human
   review? Daniel's call, probably the third option for safety.

5. **Backfill vs. greenfield.** Probably both: a one-time pass to
   deduplicate the existing Canva-export sprawl, then ongoing
   operation as part of the diff engine.

6. **Distribution record schema.** What exactly is stored in the
   `distribution` field on a Canva entry? At minimum:
   `(channel_library, channel_asset_id, first_seen_date,
   file_size_at_export)`. Possibly also: which file was the original
   source, which is the highest-resolution version, which is the
   most recently re-exported version.

7. **Channel-library schemas need a `canva_entry_id` field.**
   `ig_content`, `lead_magnets`, `blog_posts` records need to point
   at a Canva library entry. A small but real schema addition.

8. **Non-Canva visual assets.** Photos, screenshots, stock images,
   hand-drawn illustrations. Same dedup treatment, or only Canva-
   sourced content? Probably the same treatment, but the library
   name `canva_design_library` might need to broaden to
   `visual_asset_library`.

---

## What this ADR commits to

Even though the mechanism is deferred, this ADR commits to:

1. **Dedup is required.** Naive ingestion of duplicate Canva
   exports is not acceptable. The build does not ship without a
   deduplication strategy of some form.
2. **Exact-byte hashing is the floor.** At minimum, the system must
   detect byte-identical files and dedupe them. Trivial to implement
   and catches case 1.
3. **Perceptual hashing is the goal.** The full mechanism aims to
   handle cases 1 through 4 via perceptual hashing of rendered images.
4. **Canva API exploration is on the table.** Before finalizing the
   mechanism, it is worth investigating whether the Canva API can
   provide canonical-source access. If yes, it changes the design
   significantly.
5. **Dedup happens before vision enrichment.** Dedup must run *before*
   the expensive Vertex AI vision call, or the cost-saving benefit is
   lost. Pipeline order: download → hash → check registry → if
   duplicate, link and skip vision; if novel, vision + embed + store
   as new entry.

---

## Next-session agenda for ADR-003

1. Investigate Canva API capabilities and pricing
2. Pick a hashing combination (exact + perceptual, with thresholds)
3. Decide versioning behavior for near-matches
4. Specify the distribution record schema in detail
5. Decide whether the library is  (Canva only)
   or  (broader)
6. Promote ADR-003 from PROPOSED to DECIDED
7. Update the registry schema in ADR-002 to include any new fields
   this ADR introduces

---

*ADR stub written 2026-04-11 at the close of the Phase A design
pass. Locked structurally as part of ADR-002 Q1. Detailed mechanism
design deferred to a focused future session.*
