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
