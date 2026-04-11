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
