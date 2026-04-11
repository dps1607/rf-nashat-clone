# Phase C — Create Service Account + Enable APIs on rf-rag-ingester-493016

**Status:** Walkthrough — ready to execute
**Date:** 2026-04-11
**Performed by:** `dan@reimagined-health.com` (Owner on `rf-rag-ingester-493016`)
**Estimated time:** 15-25 minutes
**Blocks:** Phase B (drive sharing) cannot proceed until this is done,
per the 2026-04-11 pilot discovery that Google Drive rejects shares to
non-existent service accounts.

---

## What this does

1. Enables the **Google Drive API** on the `rf-rag-ingester-493016` project
2. Enables the **Vertex AI API** on the same project
3. Creates the service account `rf-ingester`
4. Generates a JSON key for the service account
5. Uploads the key to Railway as `GOOGLE_SERVICE_ACCOUNT_JSON`
6. Deletes the local JSON copy

After Phase C is complete, the service account email
`rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com` will be a
real, existing Google account that Drive accepts as a share target.
Phase B (share the twelve Shared Drives) can then proceed.

---

## Critical credential hygiene rules

Before you start, read this. I am going to repeat these rules at the
moments they matter, but I want you to internalize them now.

1. **The JSON key file is a credential.** Anyone who has it can read
   everything the service account has been granted access to. Treat it
   the way you would treat a password — in fact, worse than most
   passwords because it doesn't expire on its own.

2. **Never paste the JSON contents into a chat window.** Not this
   conversation, not any other Claude session, not any other AI tool,
   not Slack, not an email. The key goes from the GCP console download
   directly to Railway's env var UI, and nowhere else. This has been a
   recurring failure mode on this project — two previous API key leaks
   have already required rotation — and I'm not going to be the third.

3. **Delete the downloaded JSON file immediately after uploading to
   Railway.** It lands in your Downloads folder by default. The file
   should exist on your laptop for under 60 seconds.

4. **Empty your Downloads folder trash** or at minimum confirm the file
   is gone after the delete, so it doesn't linger in macOS trash.

5. **If anything goes wrong during this phase and you're not sure
   whether the key has been exposed**, stop and tell me. We'll rotate
   it (delete + regenerate) and start over. Rotation is cheap; a leaked
   credential is expensive.

---

## Step 1 — Confirm the project

1. Go to https://console.cloud.google.com/
2. Make sure you're signed in as **dan@reimagined-health.com** (avatar
   top-right of the console)
3. In the project picker (top bar, next to "Google Cloud"), select
   **rf-rag-ingester-493016**. The header should show the project name.
4. Verify the project ID in the top bar matches `rf-rag-ingester-493016`.
   If you see `rf-rag-ingester` without the number suffix, you're on the
   wrong project — the one without the suffix was the failed attempt
   from the earlier session that never saved properly.

## Step 2 — Enable the Google Drive API

1. Left nav → **APIs & Services** → **Library**
2. In the search bar, type **Google Drive API**
3. Click the "Google Drive API" result
4. Click the blue **Enable** button
5. Wait for the confirmation (usually under 30 seconds). The button
   changes to "Manage" when enabled.

## Step 3 — Enable the Vertex AI API

1. Still in APIs & Services → Library
2. Search for **Vertex AI API** (exact name: "Vertex AI API", also
   shown as `aiplatform.googleapis.com`)
3. Click the result
4. Click **Enable**
5. Wait for confirmation. Same pattern.

**If you see a billing prompt** at any point in Step 2 or Step 3: that
means the trial billing account isn't properly linked to this project.
Stop and tell me — we'll fix it before proceeding. Per the 2026-04-11
session-close handover, billing was auto-linked at project creation, so
you shouldn't see this prompt.

## Step 4 — Create the service account

1. Left nav → **IAM & Admin** → **Service Accounts**
2. Click **+ Create Service Account** at the top of the page
3. Fill in the form:
   - **Service account name:** `rf-ingester` (lowercase, hyphen, no spaces)
   - **Service account ID:** should auto-populate to `rf-ingester`
   - **Service account description:** `Read-only Drive ingestion + Vertex AI
     vision for the RF RAG ingester. Non-PHI only.`
4. Click **Create and Continue**
5. On the "Grant this service account access to project" step, grant:
   - **Role 1:** `Vertex AI User` (search "Vertex AI User" in the role
     picker). This lets the service account call Vertex AI for vision
     enrichment.
   - **Do NOT grant any Drive-related project roles.** Drive access is
     granted per-drive in Phase B, not at the project level. This is
     the least-privilege shape from ADR-001.
6. Click **Continue**
7. On the "Grant users access to this service account" step, leave both
   fields empty and click **Done**
8. You should land on the Service Accounts list view, with `rf-ingester`
   appearing in the list. Its full email will be:
   `rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`

**Verify the email matches exactly.** The rest of the system (including
`ingester/config.py`'s `SERVICE_ACCOUNT_EMAIL` constant and the Phase B
walkthrough) assumes this exact string. If the email differs even by a
character, stop and tell me.

## Step 5 — Generate the JSON key

**⚠ Read the credential hygiene rules above one more time before this step.**

1. In the Service Accounts list, click the row for `rf-ingester` (click
   the email, not the checkbox)
2. On the service account detail page, click the **Keys** tab
3. Click **Add Key** → **Create new key**
4. Select key type **JSON**
5. Click **Create**
6. The browser will immediately download a JSON file to your Downloads
   folder. The filename will be something like
   `rf-rag-ingester-493016-abc123def456.json`
7. **Do NOT open the file. Do NOT `cat` it in terminal. Do NOT preview
   it in Finder (Quick Look reads the bytes). Do NOT drag it anywhere
   except Railway's env var UI.** Just note where it landed.

## Step 6 — Upload the key to Railway as an env var

This is the bridge where most credential leaks happen. Slow down.

1. Open a new tab: https://railway.com/
2. Sign in if needed
3. Navigate to the **rf-nashat-clone** project
4. Find the **ingester** service (or whatever the Railway service that
   will run the ingester is called). If it doesn't exist yet, see the
   "Railway service creation" section at the bottom of this doc.
5. Click the **Variables** tab
6. Click **+ New Variable**
7. Variable name: `GOOGLE_SERVICE_ACCOUNT_JSON`
8. Variable value: **open the downloaded JSON file in a text editor**
   (TextEdit, VS Code, whatever), **select all** (`cmd+A`), **copy**
   (`cmd+C`), switch to Railway, **paste into the value field**
   (`cmd+V`). The pasted value should start with `{` and end with `}`.
9. Click **Add** (or **Save**)
10. Railway will show the variable masked in the list. Confirm it's
    there with a name of `GOOGLE_SERVICE_ACCOUNT_JSON`.

**The text-editor step is the one most likely to go wrong.** If you
accidentally open the file in something that parses it (Python, a JSON
viewer, Preview), the file contents may end up in recently-opened lists
or thumbnails. TextEdit in plain-text mode is the safest choice on macOS.

## Step 7 — Delete the local JSON copy

Immediately after Railway confirms the variable is saved:

1. Close the text editor without saving (or quit it entirely if you
   used TextEdit — `cmd+Q`)
2. In Finder, go to Downloads
3. Right-click the `rf-rag-ingester-493016-*.json` file → **Move to
   Trash** (or select + `cmd+Delete`)
4. **Empty the Trash** (`cmd+shift+Delete` in Finder, confirm)
5. Optional but recommended: run this in Terminal to confirm no JSON
   keys are lingering in common places:

   ```bash
   find ~/Downloads ~/Desktop ~/Documents -name "rf-rag-ingester*.json" 2>/dev/null
   ```

   Should return nothing.

## Step 8 — Verify the credential is live

From the rf-nashat-clone repo root, run a smoke test:

```bash
cd "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone"
source ~/.zshrc
python3 -c "
from ingester.drive_client import DriveClient
client = DriveClient()
print('Drive client initialized OK')
print('Service account email:', client.service_account_email())
"
```

Expected output: no errors, the service account email prints. This
only validates that the JSON key parses locally — it does not validate
that the API call works, because Phase B hasn't shared any drives with
the service account yet.

**Note:** for this local smoke test to work, you need the
`GOOGLE_SERVICE_ACCOUNT_JSON` env var set locally *too*, not just on
Railway. The simplest path: also add it to your local `.env` file
(which is gitignored). If you skip this and just put it on Railway,
that's fine — you just won't be able to run the smoke test locally,
which is not a blocker.

## Step 9 — Go do Phase B

Once the service account exists and the JSON key is safely in Railway,
open `GCP_PHASE_B_SHARE_DRIVES.md` and run the drive-sharing walkthrough.
Now that the service account is a real Google account, Drive will
accept the shares without the "not yet supported" error.

---

## Railway service creation (optional, only if the ingester service
doesn't exist yet in Railway)

The master plan calls for a separate Railway service named
`rf-nashat-ingester` in the same Railway project as the existing admin
UI, sharing the ChromaDB volume. If that service doesn't exist yet:

1. In Railway, open the rf-nashat-clone project
2. Click **+ New** → **Empty Service**
3. Name it `rf-nashat-ingester`
4. In Settings → **Volumes**, mount the existing chroma_db volume at
   the same path the admin service mounts it at (e.g., `/data`)
5. Leave the service idle for now (no deployment source yet — we'll
   wire it up when we start running ingestion)
6. Proceed with Step 6 above to add the `GOOGLE_SERVICE_ACCOUNT_JSON`
   variable to this new service

Alternatively, you can add the variable to the **existing** admin
service if you'd rather not create a second service right now. The
ingester code will eventually need to run on Railway but for the
first inventory walk (Phase D-prime) it can run locally on your Mac,
so the Railway service topology decision can be deferred.

---

## Troubleshooting

**"This API is not enabled for this project."**
Step 2 or Step 3 didn't complete. Re-run the step.

**"Permission denied" during service account creation.**
`dan@` doesn't have the `Service Account Admin` or `Project IAM Admin`
role on the project. Per the 2026-04-11 session-close handover, dan@
is Owner of `rf-rag-ingester-493016`, which includes these roles — if
this error appears, something about the Owner grant didn't stick.
Fix: IAM & Admin → IAM → find your row → verify Owner is listed.

**"Vertex AI User" role is not in the dropdown.**
Vertex AI API is not enabled yet. Go back to Step 3 and enable it, then
return to the role dropdown.

**JSON download failed / file is empty.**
Delete the failed key from the Keys tab of the service account
(important — leaving broken keys around is a security smell) and try
Step 5 again.

---

*Walkthrough written 2026-04-11 after the Phase B pilot discovered that
Google Drive no longer accepts pending shares to non-existent service
accounts. Phase C now blocks Phase B.*

---

## Phase C completion log — 2026-04-11

Phase C was completed end-to-end on 2026-04-11 in the same session as
ADRs 001-004 and the Phase B pilot. Recording the actual outcomes here
so future readers know what landed and what didn't.

### What was done

- ✅ GCP Console verified on `rf-rag-ingester-493016`, project number
  `577782593839`, dan@reimagined-health.com, free trial active with
  $300 credit and 90 days remaining.
- ✅ Google Drive API enabled (`drive.googleapis.com`).
- ✅ Vertex AI API enabled (`aiplatform.googleapis.com`).
- ✅ Service account `rf-ingester` created with email
  `rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`
  (matches `config.py SERVICE_ACCOUNT_EMAIL` exactly).
- ✅ Vertex AI User role granted at the project level (no Drive-level
  project roles, per ADR-001 — Drive access is granted per-drive in
  Phase B).
- ✅ JSON key generated. Key ID:
  `5de3e05cec61ce7ece287364823074a99f190dc8` (this ID is a public
  identifier, not the key material).
- ✅ JSON key uploaded to Railway as `GOOGLE_SERVICE_ACCOUNT_JSON` env
  var on the rf-nashat-clone admin service.
- ✅ Local JSON file deleted from Downloads, Trash emptied.
- ✅ Daniel handled steps 5-7 (key generation, Railway upload, local
  delete) directly without Claude in Chrome being in the tab during
  any moment when key bytes could be on screen.

### What was deferred

- **Local smoke test of the credential.** The walkthrough's optional
  Step 8 (run a Python smoke test against `drive_client.py`) was not
  run during this session. Reason: it requires the env var to be set
  locally too, and Daniel only set it on Railway. Not a blocker —
  Phase D-prime (folder-walk inventory) will exercise the credential
  for real and is a more meaningful test than the smoke check.
- **Separate Railway ingester service.** The env var was added to the
  existing admin service rather than a new dedicated ingester service.
  When the actual ingester gets wired up to Railway later, the var
  may need to be copied to the new service or the services may end up
  sharing the var. Not a blocker for Phase B.

### Notes for future rotation

The key has no expiration (`Dec 31, 9999`). Per ADR-001's compensating
control, manual quarterly rotation is the plan. Next rotation due:
**~July 11, 2026** (90 days from creation).

To rotate:
1. GCP Console → Service Accounts → rf-ingester → Keys tab
2. Click "Add Key" → "Create new key" → JSON
3. Update Railway `GOOGLE_SERVICE_ACCOUNT_JSON` with the new key
4. Verify the ingester still works (run a quick Drive list)
5. Delete the OLD key from the Keys tab (the trash icon next to it)
6. Delete the new JSON file from local disk

### Phase B status after Phase C

Phase B is now **unblocked**. The service account exists as a real
Google account, so Drive will accept shares to its email. The Phase B
walkthrough can be run as-is without modification. The click sequence
was already validated during the 2026-04-11 pilot up to (but not
including) the final Share button.
