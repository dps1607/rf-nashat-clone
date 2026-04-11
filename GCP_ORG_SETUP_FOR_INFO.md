# Google Cloud Organization Setup — Walkthrough for info@reimagined-health.com

**Audience:** the holder of the `info@reimagined-health.com` Google Workspace
super-admin account.

**Purpose:** establish a proper Google Cloud Platform (GCP) organization
under the `reimagined-health.com` Workspace domain, create an organization-
level billing account, allow service accounts to be members of Shared
Drives, grant `dan@reimagined-health.com` the IAM roles needed to operate
inside the org, and migrate the existing orphan `rf-rag-ingester` project
into the org so it inherits the new structure.

**Why this matters:** the Reimagined Fertility RAG system processes
proprietary clinical methodology (the FKSP curriculum, the 25 QPTs,
coaching call material). Data security and the ability to claim a clean
audit trail are foundational to the B2B2C strategy with IVF clinics and
insurance companies. Doing the GCP setup at the organization level — rather
than on a personal account — is the difference between "we have receipts"
and "we hope you trust us."

**Time required:** 30-45 minutes for someone who has not done this before.

**Prerequisites:** you must be logged into Google as `info@reimagined-health.com`
and that account must have Workspace super-admin rights.

---

## Background you should know before you start

Google Cloud has a concept of an **Organization** that sits above projects.
Without an org, every GCP project lives orphaned under a personal account.
With an org, projects inherit IAM policies, billing policies, and audit
logging from a central place.

For a Workspace customer, the org is automatically tied to the Workspace
domain — meaning `reimagined-health.com` *can* have a GCP organization, but
only if someone with super-admin rights explicitly accepts the GCP Terms
of Service for the org. That's what step 1 is about.

There is currently a project named `rf-rag-ingester` that was created today
under `dan@reimagined-health.com` without an org attached. This walkthrough
will end with that project living inside the new org and pointing at a
new org-level billing account.

The Reimagined Fertility course content lives in **Workspace Shared Drives**
(not personal My Drive). That introduces one extra wrinkle that step 2.5
addresses — the default Workspace policy treats service accounts as
"external users," which can silently break the ingester later if it's not
fixed up front.

---

## Step 1 — Verify Cloud Identity is enabled on the Workspace

Most paid Google Workspace plans include Cloud Identity automatically, but
let's confirm.

1. Go to https://admin.google.com while logged in as `info@reimagined-health.com`
2. In the left sidebar, click **Account → Account settings**
3. Look for a section called **Legal and compliance** or **Cloud Identity**
4. Confirm it shows your domain (`reimagined-health.com`) as enrolled

If you don't see Cloud Identity at all, you may need to enable it:
- Go to https://admin.google.com/ac/billing/subscriptions
- Look for "Cloud Identity Free" — if it's not in the list, click "Get more services"
  and add Cloud Identity Free (no cost)

This is a no-op for most paid Workspace customers but worth checking.

---

## Step 2 — Accept the GCP Organization terms

1. Open a new tab and go to https://console.cloud.google.com/
2. The first time you visit as `info@`, Google may show a Terms of Service
   acceptance screen. Read it, check the boxes, and accept.
3. After accepting, look at the top-left project picker. Click it.
4. In the dialog, switch to the **ALL** tab (not "Recent" or "Starred").
5. You should now see an Organization entry called **reimagined-health.com**
   at the top of the resource tree. **If you see this, the org exists.**
   Click on `reimagined-health.com` to select it as your scope.
6. If you do NOT see an organization entry, stop and tell Dan. It means
   Cloud Identity needs additional setup steps that vary by Workspace
   plan, and we'll need to debug.

---

## Step 2.5 — Allow service accounts to be members of Shared Drives (CRITICAL)

The Reimagined Fertility course content lives in Google Workspace **Shared
Drives** (not personal My Drive). The ingester will access it via a Google
Cloud **service account** — a special non-human user that can be granted
read-only access to specific folders.

By default, many Workspace orgs treat service accounts as "external users"
because their email domain ends in `iam.gserviceaccount.com` rather than
`reimagined-health.com`. If external membership in Shared Drives is locked
down, the service account can be invited but its permissions will silently
fail to take effect, which is one of the most painful debugging experiences
in Google Cloud.

**Do this step before Dan tries to share any folder with the service account:**

1. Go to https://admin.google.com while logged in as `info@`
2. Hamburger menu → **Apps → Google Workspace → Drive and Docs**
3. Click **Sharing settings**
4. Find the section **Sharing options** (the org-wide defaults for Drive sharing)
5. Look at **Sharing outside of reimagined-health.com**:
   - Should be **ON**, with **"Allow users to receive files from outside
     reimagined-health.com"** enabled
   - **"Warn when files owned by users or shared drives in
     reimagined-health.com are shared outside of reimagined-health.com"**
     should also be enabled
   - This is a sensible default — allows the service account as a member
     without making the org wide open
6. Find **Access Checker** and set it to **"Recipients only, or
   reimagined-health.com"** (the most common safe setting)
7. Save changes

**Additional controls to verify on the same page (depending on Workspace plan):**

8. Look for **"Allow members with manager access to share folders with
   people outside their organization"** — should be ON
9. Look for **"Distributing content outside of reimagined-health.com"** —
   should allow it, ideally with the warning enabled

**If you cannot find these settings, or they look different from what's
described, do NOT change anything. Stop and message Dan.** Drive sharing
settings affect every user in the org, and a wrong toggle can either
lock down legitimate sharing or open up unintended exposure.

**Why this matters in plain language:** without this step, when Dan tries
to share the FKSP Shared Drive folder with the service account, one of
two bad things happens. Either Google rejects the share outright with a
"this user is outside your organization" error, or — worse — Google
*accepts* the share, the service account appears in the member list,
but the API calls fail with `403 insufficientFilePermissions` because
the membership wasn't actually applied. The latter is a confusing 30-
minute debugging session that this 2-minute admin step prevents.

---

## Step 3 — Create an organization-level billing account

This is the billing account the company will use for all GCP services
going forward, not just this one project.

1. With the `reimagined-health.com` org selected at the top, click the
   hamburger menu (☰) → **Billing**
2. If you see "This organization has no billing accounts," click
   **CREATE ACCOUNT** (or **MANAGE BILLING ACCOUNTS → CREATE ACCOUNT**)
3. **Account name:** `Reimagined Health — Primary` (or similar — pick a
   name that signals "this is the main company billing account")
4. **Country:** United States
5. **Currency:** USD
6. **Organization:** should auto-fill to `reimagined-health.com`. Confirm.
7. Click **CONTINUE**
8. **Billing profile:**
   - **Account type:** Business
   - **Business name:** Reimagined Health (or the legal entity name)
   - **Tax info:** fill in as appropriate for the entity
9. **Payment method:** add a company credit card. **Important:** this
   should be a corporate card, not Dan's personal card. If RH does not yet
   have a corporate card, this is a good moment to get one — having
   personal cards on company cloud bills is a recurring pain point.
10. Submit. The billing account will be created in a few seconds.

**Take note of the Billing Account ID** — it looks like
`01ABCD-234567-89EFGH`. You'll need it (or Dan will) to link projects to
this account later.

---

## Step 4 — Grant dan@reimagined-health.com the right IAM roles at the org level

This is the step that lets Dan create projects, use billing, and enable
APIs inside the org without needing super-admin rights.

1. With the `reimagined-health.com` org selected at top, hamburger menu
   (☰) → **IAM & Admin → IAM**
2. Confirm at the top of the page it says you're viewing IAM at the
   **Organization** level (not at a project level). The breadcrumb should
   show `reimagined-health.com`, not a project name.
3. Click **+ GRANT ACCESS** (top of the page)
4. **New principals:** type `dan@reimagined-health.com`
5. **Assign roles** — add ALL of the following (click "Add another role"
   between each):
   - **Project Creator** (`roles/resourcemanager.projectCreator`)
     — lets Dan create new GCP projects inside the org
   - **Billing Account User** (`roles/billing.user`)
     — lets Dan link projects to billing accounts (BUT NOT modify the
     billing accounts themselves)
   - **Service Usage Admin** (`roles/serviceusage.serviceUsageAdmin`)
     — lets Dan enable and disable APIs on projects he owns
6. **Optional but recommended** — also add:
   - **Organization Viewer** (`roles/resourcemanager.organizationViewer`)
     — lets Dan see the org structure (read-only). Useful for debugging.
7. Click **SAVE**

**Important: do NOT grant Dan `Billing Account Administrator`.** That role
would let Dan modify or delete the billing account, which is super-admin
territory. `Billing Account User` is the right level — Dan can spend from
the account but not change it.

---

## Step 5 — Add the service account as a member of the FKSP Shared Drive

This step happens **after** Dan creates the service account inside the
`rf-rag-ingester` GCP project, so it's a future step but it belongs in
this doc because it's a Workspace admin action that `info@` (or another
Shared Drive Manager) needs to do.

**Dan will give you the service account email when the time comes.** It
will look like:
`rf-ingester@rf-rag-ingester.iam.gserviceaccount.com`
(possibly with extra digits in the project ID).

When Dan asks you to do this:

1. Open https://drive.google.com while logged in as `info@`
2. In the left sidebar, click **Shared drives**
3. Find and double-click the Shared Drive that contains the FKSP folder
   (the one Dan referenced — folder ID `1b_HQqzLCXfOjMXSDB_W2sUF9loJziZ2b`)
4. At the top right of the Shared Drive view, click **Manage members**
   (the people-icon button)
5. In the "Add people and groups" field, paste the service account email
   Dan gave you
6. Set the role to **Viewer** (NOT Manager, NOT Content Manager — Viewer
   is read-only and is exactly what we want)
7. **Uncheck** "Notify people" (the service account can't read email anyway)
8. Click **Send** (or **Share**)

**Verification:** the service account should now appear in the member
list with a Viewer badge. If it shows a warning about external users,
that's expected — you allowed external sharing in step 2.5, so this is
the warning firing as designed.

**Why this matters:** the ingester walks the FKSP folder tree using the
service account's credentials. Without Viewer membership on the Shared
Drive, the API calls return empty file lists with no error — another
silent failure mode that's painful to debug.

---

## Step 6 — Migrate the existing rf-rag-ingester project into the org

Right now `rf-rag-ingester` lives orphaned under Dan's account with no org
attachment. This step moves it into the new org so it inherits everything.

**Note:** this step requires Dan to be logged in (not info@), because the
project is currently owned by Dan. **Dan will do this part himself.**
The instructions are below for completeness, but please pass them to Dan
rather than doing them yourself.

### Instructions for DAN to run after info@ finishes steps 1-4

1. Log into https://console.cloud.google.com/ as `dan@reimagined-health.com`
2. At the top, switch the project picker to `rf-rag-ingester`
3. Hamburger menu (☰) → **IAM & Admin → Settings**
4. Look for a section called **Migrate** or a button called **MIGRATE**
   near the top of the project settings page. Click it.
5. You should now see the `reimagined-health.com` org as a destination.
   Select it and confirm the migration.
6. Wait ~30 seconds for the migration to complete.

After migration:
7. Hamburger menu → **Billing** → **LINK A BILLING ACCOUNT**
8. Select the **Reimagined Health — Primary** billing account that
   `info@` created in step 3
9. Confirm

The project is now: inside the org, billed to the company account,
inheriting org-level IAM, and ready to have APIs enabled.

---

## Step 7 — Verify the whole thing

After all of the above, confirm the following from `dan@`'s account:

1. https://console.cloud.google.com/ shows `rf-rag-ingester` under the
   `reimagined-health.com` org in the project picker (not under "No
   organization")
2. Hamburger → **Billing** on the project shows it's linked to
   "Reimagined Health — Primary"
3. Hamburger → **IAM & Admin → IAM** at the org level shows
   `dan@reimagined-health.com` with the four roles from step 4

If all three check out, the GCP foundation is in place and Dan can resume
the ingester build (enabling Drive API + Vertex AI, creating the service
account, sharing the FKSP Shared Drive, and so on).

---

## What this enables, in plain language

Once this walkthrough is complete, the following becomes true:

- Every GCP cost goes on the company's billing account, not anyone's
  personal card
- Every API call made by the ingester is auditable in Cloud Logging
  under the org
- If Dan ever loses access to his account, the projects don't get
  orphaned — they're owned by the org, and a new admin can take over
- When IVF clinics ask "where does our patient educational content go
  when your AI processes it," the answer is "into a single Google Cloud
  project owned by Reimagined Health, with Vertex AI's no-training
  contractual guarantee, and we can show you the audit logs"
- HIPAA compliance becomes a paperwork exercise (sign Google's BAA at
  the org level) rather than an architectural rebuild

---

## Questions or issues

If anything in this walkthrough doesn't match what you see on screen,
stop and message Dan. Google Cloud's UI shifts around and the exact
button names occasionally change. Better to pause and confirm than to
click something unexpected.

---

*Document written 2026-04-11 for the Reimagined Fertility RAG system
build. See HANDOVER_INTERNAL_EDUCATION_BUILD.md for the broader
project context.*
