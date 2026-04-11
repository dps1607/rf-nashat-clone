"""
rf_internal_education + rf_published_content ingester.

This package walks Google Drive source folders, extracts content from videos
and PDFs, enriches with vision-LLM descriptions, chunks, embeds, and writes
to ChromaDB.

See HANDOVER_INTERNAL_EDUCATION_BUILD.md at the repo root for the full
architecture and session-by-session build plan.
"""

__version__ = "0.1.0"
