"""
Ingester configuration constants.

This is the single source of truth for:
  - ChromaDB collection names
  - Program identifiers and their Google Drive folder IDs
  - Model names (embedding, vision, chunking)
  - Path conventions on the Railway shared volume

Environment-dependent values (credentials, API keys, the mounted data root)
are read from env vars at runtime, NEVER hardcoded.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# ChromaDB collections
# ---------------------------------------------------------------------------
COLLECTION_INTERNAL_EDUCATION = "rf_internal_education"
COLLECTION_PUBLISHED_CONTENT = "rf_published_content"

# ---------------------------------------------------------------------------
# Program registry
#
# Each program has:
#   - a short slug used as the `program` metadata field on every chunk
#   - the Google Drive folder ID (NOT the full URL) of its top-level folder
#
# The service account must be shared as "Viewer" on each of these folders
# before drive_client.py can list them.
# ---------------------------------------------------------------------------
PROGRAMS = {
    "fksp": {
        "name": "Fertility Kickstart Program",
        "duration_weeks": 12,
        "drive_folder_id": "1b_HQqzLCXfOjMXSDB_W2sUF9loJziZ2b",
        "is_flagship": True,
    },
    "fertility_formula": {
        "name": "Fertility Formula",
        "duration_weeks": 6,
        "drive_folder_id": "1_mQFLQS1poldEOfaU1LZC1KnY3dYcgpZ",
        "is_flagship": False,
    },
    "preconception_detox": {
        "name": "Preconception Detox",
        "duration_weeks": 4,
        "drive_folder_id": "1ux8JELm29CTsSEPwyC5GM1H4jCVJ7GQU",
        "is_flagship": False,
    },
}

# ---------------------------------------------------------------------------
# Models — kept consistent with existing collections for retrieval compatibility
# ---------------------------------------------------------------------------
EMBEDDING_MODEL = "text-embedding-3-large"      # OpenAI, 3072-dim
EMBEDDING_DIMENSIONS = 3072
VISION_MODEL = "gemini-2.5-flash"               # Google, for slide + PDF enrichment
CHUNKING_CONTEXT_MODEL = "claude-haiku-4-5-20251001"  # Anthropic, for context-aware chunk wrapping

# ---------------------------------------------------------------------------
# Paths
#
# DATA_ROOT is the mounted Railway volume in production (/data) and falls back
# to a local dev path. All ingester output goes under DATA_ROOT so both the
# admin UI and the ingester worker see the same files on the shared volume.
# ---------------------------------------------------------------------------
DATA_ROOT = Path(os.environ.get("INGESTER_DATA_ROOT", "/data"))
CHROMA_DB_PATH = Path(os.environ.get("CHROMA_DB_PATH", str(DATA_ROOT / "chroma_db")))
ASSETS_ROOT = DATA_ROOT / "assets"
MANIFESTS_ROOT = DATA_ROOT / "manifests"
INVENTORY_ROOT = DATA_ROOT / "inventories"

# ---------------------------------------------------------------------------
# Google Drive MIME types we care about (used for routing to pipelines)
# ---------------------------------------------------------------------------
MIME_FOLDER = "application/vnd.google-apps.folder"
MIME_PDF = "application/pdf"
MIME_GOOGLE_DOC = "application/vnd.google-apps.document"
MIME_GOOGLE_SLIDES = "application/vnd.google-apps.presentation"

# Video mimetypes — Drive returns these for uploaded Zoom recordings
VIDEO_MIMES = {
    "video/mp4",
    "video/quicktime",
    "video/x-matroska",
    "video/webm",
    "video/x-msvideo",
}

# Image mimetypes — for standalone assets in rf_published_content
IMAGE_MIMES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}

# ---------------------------------------------------------------------------
# Google Cloud project configuration
#
# These values identify the GCP project that hosts the service account
# (Drive read access) AND the Vertex AI region we call for vision
# enrichment. Keeping them as constants here means the ingester code
# never has to guess which project it's in.
#
# Created 2026-04-11 inside the drnashatlatib.com Workspace org.
# Project lives under the org-level billing account (currently on the
# $300 GCP free trial credit).
# ---------------------------------------------------------------------------
GCP_PROJECT_ID = "rf-rag-ingester-493016"
GCP_PROJECT_NUMBER = "577782593839"
GCP_ORG_DOMAIN = "drnashatlatib.com"

# Vertex AI region for vision calls. us-central1 is the most-supported
# region for Gemini models on Vertex; we can change this later if data
# residency requirements push us elsewhere.
VERTEX_AI_REGION = "us-central1"

# Service account email — populated AFTER the service account is created
# in Session 2 (see HANDOVER_INTERNAL_EDUCATION_BUILD.md). This is the
# expected pattern; the actual email will match this exactly because the
# service account name is fixed at "rf-ingester".
SERVICE_ACCOUNT_EMAIL = f"rf-ingester@{GCP_PROJECT_ID}.iam.gserviceaccount.com"

# Trial billing account ID. Auto-linked to rf-rag-ingester-493016 at
# project creation because the org has only one billing account at this
# point. When the trial expires (~90 days from 2026-04-11) or runs out
# of the $300 credit, this is replaced by a real org-level paid billing
# account. Tracked in ADR-001 / GCP_ORG_SETUP_FOR_INFO.md.
#
# Read from env vars (NOT hardcoded) so the actual ID never lives in
# the repo. Set GCP_BILLING_ACCOUNT_ID in your local .env (gitignored)
# and in Railway env vars when the ingester service is created.
# Returns None if unset; most ingester code paths do not need this
# value at all (it exists for future Vertex AI billing routing and
# audit log queries).
GCP_BILLING_ACCOUNT_ID = os.environ.get("GCP_BILLING_ACCOUNT_ID")
GCP_BILLING_ACCOUNT_NAME = os.environ.get(
    "GCP_BILLING_ACCOUNT_NAME", "My Billing Account (free trial)"
)

# ---------------------------------------------------------------------------
# Shared Drive IDs (Phase D-prime — folder-walk inventory)
#
# Maps slug → Google Drive ID for every Shared Drive the ingester needs to
# walk. IDs are populated after the first --discover run.  If a drive is
# not visible to the service account (Phase B sharing incomplete), its ID
# will remain "" and the walk will mark it as "not_shared".
# ---------------------------------------------------------------------------
SHARED_DRIVE_IDS: dict[str, str] = {
    "0-shared-drive-content-outline": "",                # not shared with SA
    "1-operations": "0AFn8_syivpiXUk9PVA",
    "2-sales-relationships": "0AGG6os8UbberUk9PVA",
    "3-marketing": "0AG5ixXZq2uo_Uk9PVA",
    "4-finance": "",                                     # not shared with SA
    "5-hr-legal": "",                                    # not shared with SA
    "6-ideas-planning-research": "0AAsWNXUSwHmLUk9PVA",
    "7-supplements": "0AH-CpaRZmgt0Uk9PVA",
    "8-labs": "0AKCrxYWgoQIRUk9PVA",
    "9-biocanic": "0APUPrV2jG6k6Uk9PVA",
    "10-external-content": "0ANGL6R04Te5gUk9PVA",
    "11-rh-transition": "0APsPzGypws_jUk9PVA",
}

# Drives that contain sensitive data (finance, HR/legal, labs).
# The folder-walk still reads metadata from these drives (read-only),
# but downstream selection UIs will require an extra confirmation step.
SENSITIVE_DRIVE_SLUGS: set[str] = {"4-finance", "5-hr-legal", "8-labs"}
