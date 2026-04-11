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
