# RF Nashat RAG — Decisions log (append-only)

Completed decisions with rationale. Never re-litigated in chat; read from here if needed.

---

### 2025 — Self-hosted RAG over Delphi.ai
Delphi.ai platform update broke the existing Digital Mind. Self-hosting is the deliberate replacement to own the IP and infrastructure end-to-end.

### 2025 — LLM-powered chunking (Haiku) over rule-based
Rule-based chunking couldn't detect topic shifts within speaker turns in coaching transcripts. Haiku-driven context-aware chunking produced v3: 9,224 chunks, 573-word mean. This is the proven approach and the one future ingestions should follow.

### 2025 — Railway over Vercel for deployment
Vercel's serverless model is incompatible with long-lived Flask + persistent ChromaDB. Railway supports both. Not revisiting.

### 2025 — Two-agent architecture with HIPAA boundary
Public sales agent and internal coaching agent are separate by design. Public agent never touches `rf_coaching_transcripts`. This is the architectural HIPAA boundary regardless of whether coaching data is technically HIPAA-regulated.

### 2025 — Clue deprioritized, Flo as engagement benchmark, NC as BBT benchmark
- Clue: only its structured clinical intake concept is worth emulating. UX/engagement model explicitly deprioritized.
- Flo: primary engagement/recommendation benchmark to match and surpass. Confirmed zero coverage in BBT interpretation, root-cause analysis, lab education, supplements — that's Nashat's gap to own.
- Natural Cycles: BBT algorithm benchmark. Nashat adds root-cause interpretation, lab integration, AI assistance, B2B strategy that NC lacks.

### 2025 — Client coaching data: discretion, not HIPAA
Requires professional discretion but is not HIPAA-regulated. HIPAA boundary is enforced at the two-agent architecture level by design choice, not legal requirement.

### 2026 — Zoom pipeline: hybrid client ID + episode-chunk unit
Client ID = transcript content + Zoom tile labels, RFID resolved via Haiku. Chunk unit = "interaction episode" on one clinical topic, with metadata (qpt_tags, scene_type, visual_artifact_id, client_rfid). Pilot one call end-to-end before batch. Full design in BACKLOG.md.

### 2026 — Ambiguous chunk disambiguation: Zoom labels + scene changes, not pattern matching
Future disambiguation of remaining ambiguous transcript chunks should use Zoom participant labels and scene-change data. Do not add more pattern-matching rules.

### 2026 — Local Drive credentials via service account
Service account JSON at `/Users/danielsmith/.config/gcloud/rf-service-account.json` (chmod 600). Project `rf-rag-ingester-493016`. Client email `rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`. Enables local iteration without Railway round-trip. Previously deferred; now resolved.
