# Google Cloud Organization Setup — Walkthrough for info@reimagined-health.com

**Audience:** the holder of the `info@reimagined-health.com` Google Workspace
super-admin account.

**Purpose:** establish a proper Google Cloud Platform (GCP) organization
under the `reimagined-health.com` Workspace domain, create an organization-
level billing account, grant `dan@reimagined-health.com` the IAM roles
needed to operate inside the org, and migrate the existing orphan
`rf-rag-ingester` project into the org so it inherits the new structure.

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

## Step 5 — Migrate the existing rf-rag-ingester project into the org

Right now `rf-rag-ingester` lives orphaned under Dan's account with no org
attachment. This step moves it into the new org so it inherits everything.

**Note:** this step requires Dan to be logged in (not info@), because the
project is currently owned by Dan. Dan should do this part. The
instructions are below for completeness, but please pass them to Dan
rather than doing them yourself.

---

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

## Step 6 — Verify

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
account, etc.).

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
