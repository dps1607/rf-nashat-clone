#!/usr/bin/env bash
set -euo pipefail

# Bootstrap script — runs once at container start, before honcho.
# Idempotent: safe to run on every boot.

CONFIG_DIR="${CONFIG_DIR:-/data/config}"
SEED_DIR="/app/config"

# 1. Ensure CONFIG_DIR exists and is seeded with the YAMLs from the repo
#    on first deploy. After the first deploy, the volume's copies are the
#    source of truth and we leave them alone.
mkdir -p "$CONFIG_DIR"

for seed in "$SEED_DIR"/nashat_sales.yaml "$SEED_DIR"/nashat_coaching.yaml; do
    fname="$(basename "$seed")"
    if [ ! -f "$CONFIG_DIR/$fname" ]; then
        echo "[bootstrap] seeding $fname from repo to $CONFIG_DIR/"
        cp "$seed" "$CONFIG_DIR/$fname"
    else
        echo "[bootstrap] $fname already exists on volume, leaving alone"
    fi
done
# 1b. Bootstrap chroma_db on first deploy by downloading a tarball from a
#     URL specified via CHROMA_BOOTSTRAP_URL env var. On subsequent deploys,
#     volume's copy is source of truth and we leave it alone. Failure is
#     non-fatal — app still boots with empty chroma_db, which is the
#     current baseline state.
CHROMA_DB_PATH="${CHROMA_DB_PATH:-/data/chroma_db}"
CHROMA_BOOTSTRAP_URL="${CHROMA_BOOTSTRAP_URL:-}"

if [ -d "$CHROMA_DB_PATH" ] && [ -n "$(ls -A "$CHROMA_DB_PATH" 2>/dev/null)" ]; then
    echo "[bootstrap] chroma_db already populated at $CHROMA_DB_PATH, leaving alone"
elif [ -n "$CHROMA_BOOTSTRAP_URL" ]; then
    echo "[bootstrap] chroma_db empty, downloading bootstrap tarball..."
    mkdir -p "$(dirname "$CHROMA_DB_PATH")"
    TMPTAR="$(mktemp /tmp/chroma_bootstrap.XXXXXX.tar)"
    if curl -fsSL --retry 3 --retry-delay 5 -o "$TMPTAR" "$CHROMA_BOOTSTRAP_URL"; then
        TARSIZE="$(du -h "$TMPTAR" | cut -f1)"
        echo "[bootstrap] download complete ($TARSIZE), extracting..."
        if (cd "$(dirname "$CHROMA_DB_PATH")" && tar xf "$TMPTAR"); then
            FILECOUNT="$(find "$CHROMA_DB_PATH" -type f 2>/dev/null | wc -l | tr -d ' ')"
            FINALSIZE="$(du -sh "$CHROMA_DB_PATH" 2>/dev/null | cut -f1)"
            echo "[bootstrap] chroma_db extracted: $FINALSIZE, $FILECOUNT files"
        else
            echo "[bootstrap] ERROR: tar extraction failed"
        fi
        rm -f "$TMPTAR"
    else
        echo "[bootstrap] ERROR: download failed from $CHROMA_BOOTSTRAP_URL"
        rm -f "$TMPTAR"
    fi
else
    echo "[bootstrap] chroma_db empty and CHROMA_BOOTSTRAP_URL not set, skipping"
fi
# 2. Print whether admin_users.json exists — informational only, we never
#    create it automatically (security: requires manual setup via railway shell).
ADMIN_USERS_PATH="${ADMIN_USERS_PATH:-/data/admin_users.json}"
if [ -f "$ADMIN_USERS_PATH" ]; then
    echo "[bootstrap] admin_users.json found at $ADMIN_USERS_PATH"
else
    echo "[bootstrap] WARNING: no admin_users.json at $ADMIN_USERS_PATH"
    echo "[bootstrap] login will fail until you create one via:"
    echo "[bootstrap]   railway shell"
    echo "[bootstrap]   python3 -m admin_ui.add_user <username>"
fi

echo "[bootstrap] done"
