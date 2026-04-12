# INCIDENTS.md — Credential Exposures and Rotations

Audit log of credential exposure incidents on the rf-nashat-clone project.
Timestamps in local time. No credential values are ever recorded here —
only the fact that rotation occurred and when.

---

## 2026-04-11 — Railway CLI variable dump exposure

**Severity:** High (multiple production credentials)
**Detection:** Assistant self-reported during the Phase C smoke-test setup
**Root cause:** Claude ran `railway variables` with no output flags, which
prints all environment variable values in plaintext in the CLI output.
Five credentials were captured in the assistant's context window as a
result.

**Credentials exposed:**

1. `ANTHROPIC_API_KEY` — full value
2. `OPENAI_API_KEY` — full value
3. `ADMIN_PASSWORD` — full value (`Creation2025!`)
4. `ADMIN_SESSION_SECRET` — full value (Flask session signing key)
5. `CLOUDFLARE_ACCESS_AUD` — application audience tag (lower severity;
   not a bearer credential on its own)

Configuration values (non-secrets) also seen but not requiring rotation:
`ADMIN_USERS_PATH`, `AUDIT_LOG_PATH`, `CHROMA_DB_PATH`, `CLOUDFLARE_ACCESS_ENABLED`,
`CLOUDFLARE_ACCESS_TEAM_DOMAIN`, `CONFIG_DIR`, `DEFAULT_AGENT`, `RAG_SERVER_URL`.

**Rotation timeline (2026-04-11 evening):**

1. ✅ Anthropic API key — revoked in Anthropic Console, new key issued,
   Railway `ANTHROPIC_API_KEY` updated
2. ✅ OpenAI API key — revoked in OpenAI Platform, new key issued,
   Railway `OPENAI_API_KEY` updated
3. ✅ `ADMIN_SESSION_SECRET` — new value generated (not shown in chat),
   Railway variable updated. All existing admin sessions invalidated.
4. ✅ `ADMIN_PASSWORD` — new random value set in Railway. Note:
   `CLOUDFLARE_ACCESS_ENABLED=true` means the production admin console
   authenticates via Cloudflare Access, not the bcrypt password. The
   leaked `ADMIN_PASSWORD` was not in the active auth path, but rotation
   was done anyway for defense in depth.
5. ⏭️ `CLOUDFLARE_ACCESS_AUD` — deferred. The AUD is an identifier, not
   a bearer credential; knowing it does not grant access without a
   Cloudflare-signed JWT from the team domain. Will be rotated during
   the next Cloudflare Access review cycle.

**Contributing factors / what made this possible:**

- Assistant used the Railway CLI in a way that outputs all variable
  values. The command `railway variables` (no flags) is documented to
  print values in plaintext in its table output.
- Assistant had an explicit commitment to avoid credential handling in
  the Phase C walkthrough but did not apply that commitment to `railway
  variables` because the command was being used "just to check whether
  a variable existed."
- The project has prior credential leak history (two earlier incidents
  in the session memory); additional safeguards on how Claude interacts
  with Railway were not in place.

**Corrective actions for future sessions:**

- Never run `railway variables` bare. Acceptable alternatives:
  * `railway variables --kv 2>&1 | cut -d'=' -f1` (names only)
  * `railway variables --json 2>&1 | jq 'keys'` (names only, JSON)
  * Check the Railway dashboard manually rather than via CLI
- Treat the Railway CLI output surface as equivalent to reading a
  `.env` file: never do it casually, always with an explicit operational
  need and explicit user heads-up.
- Added to next-session handover as a persistent reminder.

**New credential creation timestamps (for rotation tracking):**

- GCP `rf-ingester` service account JSON key: created 2026-04-11
  (key ID `5de3e05cec61ce7ece287364823074a99f190dc8`). **Not affected**
  by this incident — the new GCP credential was never in the exposed
  output.
- Rotated Anthropic / OpenAI / session secret / admin password:
  all created 2026-04-11 evening.
- Next rotation due for GCP service account key: ~July 11, 2026
  (quarterly per ADR-001).

---


---

## 2026-04-11 night — Near-miss: staged-but-not-deployed Railway variable

**Severity:** Low (near-miss, no credential exposure)
**Detection:** Smoke test failure during 2026-04-11 night session
**Root cause:** Railway UI distinguishes staged variables (purple) from
deployed variables (white) by color only. During the evening Phase C
upload, `GOOGLE_SERVICE_ACCOUNT_JSON` was pasted into the Variables tab
and appeared in the list. The evening Claude and Dan both saw it and
logged Phase C as complete. The **Deploy** button at the top of the
page was never clicked, so the variable sat in draft state. The CLI
could not see it. `railway run` could not inject it. The JSON key
itself in GCP was fine — it just was not actually attached to any
runtime environment in Railway.

**Impact:** Zero. The key is not in any untrusted location. No
ingestion runs were attempted against the non-deployed credential.
The only cost was time spent debugging during the night session (and
a brief moment where rotation was being considered before the real
cause was found).

**How it was caught:** Smoke test `scripts/smoke_test_credential.py`
ran via `railway run` and failed at the first check:
`FAIL: GOOGLE_SERVICE_ACCOUNT_JSON not set in environment`. A long
diagnostic trail followed (see `HANDOVER_SESSION_20260411_NIGHT.md`)
before Dan noticed that pending variables in the Railway UI show
purple while deployed ones show white.

**Resolution:** Dan clicked **Deploy** in the Railway Variables tab.
Purple entries turned white. Smoke test was re-run and returned PASS.
No rotation, no GCP work, no new key.

**Corrective actions:**

1. `GCP_PHASE_C_SERVICE_ACCOUNT.md` Step 6 needs a new sub-step:
   "After clicking Add/Save, look for a Deploy button at the top of
   the page. Click it. Wait for the deploy to finish. Confirm the
   variable is shown in white (not purple) before considering the
   upload complete." (Not yet applied — deferred to next session.)

2. Future Phase C walkthroughs and similar credential uploads should
   always finish with the smoke test, not merely with "variable
   appears in UI." The smoke test caught this in one shot.

3. `railway variables --kv | cut -d'=' -f1` is unreliable for
   variables whose values contain `=` signs or newlines (e.g., a
   service account JSON with an embedded PEM private key). The `cut`
   command mis-splits the JSON content and can silently drop the
   variable name from the output. Safe alternatives for name-only
   checks of multi-line values:
   - `railway variables --json 2>&1 | jq -r 'keys[]'`
   - `railway run --service <n> python3 -c "import os; [print(k) for k in sorted(os.environ)]"`
