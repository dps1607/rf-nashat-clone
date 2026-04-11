# Phase B — Share Shared Drives with the RF Ingester Service Account

**Status:** Walkthrough — ready to execute
**Date:** 2026-04-11
**Performed by:** `dan@reimagined-health.com` (Workspace admin, drive Manager)
**Estimated time:** 15-25 minutes via Claude in Chrome, ~30 minutes manual

---

## What this does

Grants the RF ingester service account read access to the twelve Reimagined
Fertility Workspace Shared Drives so the folder-selection UI (ADR-004) can
walk and ingest content from them.

This is the rescoped Phase B from ADR-001 — the original "create dedicated
drive + populate shortcuts" approach was replaced by behavioral scoping via
the selection UI. The dedicated-drive pattern is reserved for the eventual
Clinical tier when PHI arrives.

---

## What you need before starting

- **Phase C must be complete first.** The service account must already
  exist as a real Google account. Google Drive rejects shares to email
  addresses that do not correspond to existing Google accounts with the
  error *"Sharing to email addresses without a Google account is not yet
  supported."* (This was discovered the hard way during the 2026-04-11
  pilot — the original version of this doc incorrectly claimed pending
  shares would work.)
- Logged into Chrome as `dan@reimagined-health.com`
- Confirmed `dan@` has **Manager** role on each of the twelve Shared Drives
  (NOT Content Manager — Manager. Check via: gear icon → Manage members on
  any one drive, look for your role next to your name)
- The service account email (already known and locked in `ingester/config.py`):

  ```
  rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com
  ```

  Per the above, this account must exist before Phase B begins. See
  `GCP_PHASE_C_SERVICE_ACCOUNT.md`.

---

## The twelve drives

For each drive, grant the service account **Viewer** at the drive level
(NOT folder level). Viewer is read-only — the service account cannot
modify, delete, or share any content.

| # | Drive | Sensitive flag | What's in it (per Daniel) |
|---|-------|----------------|---------------------------|
| 0 | `0-Shared Drive Content Outline` | No | Index/metadata |
| 1 | `1. Operations` | No | Internal operations |
| 2 | `2. Sales & Relationships` | No | FKSP / FF / Detox program content + coaching calls |
| 3 | `3. Marketing` | No | Blogs, lead magnets, masterclasses, IG content |
| 4 | `4. Finance` | **YES** | Sensitive financial data |
| 5 | `5. HR & Legal` | **YES** | Personnel + legal data |
| 6 | `6. Ideas, Planning & Research` | No | Research material, possibly external_research library |
| 7 | `7. Supplements` | No | Protocol references |
| 8 | `8. Labs` | **YES** | PHI-adjacent — future Clinical tier |
| 9 | `9. Biocanic` | No | (To be determined at click-time) |
| 10 | `10. External Content` | No | Reference material (A4M, external sources) |
| 11 | `11. RH Transition` | No | (To be determined at click-time) |

**Important note about the flagged drives:** The "Sensitive flag" column does
NOT change what we do in Phase B. We share all twelve at Viewer level,
including the flagged ones. The flag is metadata that lives in the registry
(per ADR-001) and triggers a confirmation modal in the UI later (per
ADR-004) when the user tries to *check* a folder inside a flagged drive.
The credential reach and the UI selection are separate things.

If you're uncomfortable sharing `4. Finance`, `5. HR & Legal`, or `8. Labs`
even at Viewer level, you can skip those three drives. The cost of skipping:
they won't appear in the folder-selection UI later. You can always add them
back manually if a need surfaces.

---

## The click sequence (per drive)

For each drive in the table above, perform this sequence:

1. Open Google Drive: https://drive.google.com/
2. Click **Shared drives** in the left sidebar
3. Click on the drive name (e.g., `2. Sales & Relationships`)
4. Click the gear icon in the top-right of the drive view
5. Click **Manage members**
6. In the "Add people, groups, and calendar events" field, paste the
   service account email:
   `rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`
7. Set the role dropdown to **Viewer** (NOT Manager, NOT Content Manager,
   NOT Commenter — **Viewer**)
8. UNCHECK "Notify people" (the service account has no inbox; the email
   would bounce or vanish)
9. Click **Send** (or **Share**, depending on Drive's current button label)
10. Verify the service account email now appears in the members list with
    role "Viewer"

---

## Failure modes to watch for

**"You don't have permission to share this drive."**
You are not a Manager on this drive — only Content Manager or below. Either
have someone with Manager role do it, or have a Workspace admin promote
your role on the drive first.

**"This email address isn't valid."**
Drive sometimes rejects service account emails on first attempt. Try again,
or paste the email in two parts and confirm. If it persistently rejects,
check that you typed the email exactly:
`rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`

**"Pending — user has not joined yet." / "Sharing to email addresses without a Google account is not yet supported."**
Google no longer accepts pending shares to email addresses without
existing Google accounts. This means the service account MUST exist before
Phase B can begin. If you see this error, the fix is to complete Phase C
first (create the service account in GCP), then return to Phase B.

**The "Notify people" checkbox is on by default and you can't uncheck it.**
Some Drive UIs hide the checkbox. Click "Send" anyway — Drive will try to
notify, the email will bounce silently, no harm done. The share itself
still goes through.

---

## Verification (after Phase C)

Once the service account is created in Phase C, run a Drive API smoke test
to verify the shares actually work. From the project root:

```bash
source ~/.zshrc
cd "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone"
python3 -m ingester.main inventory --dry-run
```

Expected output: a list of the twelve drives, showing the service account
can see each one. Any drive that fails to appear means the share didn't
land for that drive — re-check membership manually.

---

## Pilot order (recommended for the Claude in Chrome run)

Doing all twelve in one run is fine but if anything goes sideways we want
to know early. Recommended order:

1. **Drive #0** (`0-Shared Drive Content Outline`) — pilot. Lowest stakes.
   If this works, the click sequence is right.
2. **Drive #2** (`2. Sales & Relationships`) — most important drive for the
   build. Worth confirming early.
3. **Drives #1, #3, #6, #7, #9, #10, #11** — non-flagged remainder
4. **Drives #4, #5, #8** — flagged drives, last (so you can stop here if
   you change your mind about including them)

---

## What happens after Phase B

- **Phase C** — Create the service account in GCP, enable Drive API and
  Vertex AI API on `rf-rag-ingester-493016`. The pending shares from Phase B
  activate the moment the service account is created.
- **Phase D-prime** — Run the folder-walk inventory pass. This is the first
  time the ingester actually talks to Drive. Output is a JSON dump of the
  folder tree across all twelve drives, used to design the selection UI
  against real data.
- **Phase D** — First FKSP pilot ingestion (CLI-driven, hardcoded folder
  IDs, one short video + one PDF, master plan Session 2 pattern).
- **Phase D-post** — Build the folder-selection UI (per ADR-004).
- **Phase E** — All subsequent ingestion through the UI.

---

*Walkthrough written 2026-04-11. Phase B is the first phase of actual
execution after the Phase A design pass closed.*
