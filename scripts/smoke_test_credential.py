#!/usr/bin/env python3
"""
Smoke test for the rf-ingester service account credential.

What this does:
  1. Reads GOOGLE_SERVICE_ACCOUNT_JSON from the environment
  2. Verifies it parses as valid JSON and has the expected service account email
  3. Builds a Google Drive API client from it
  4. Calls drive.about().get() — the cheapest authenticated call available
  5. Prints the authenticated identity (which is public information)

What this does NOT do:
  - Print any private key material
  - List drives, files, or any content
  - Modify anything

Run via:  railway run python3 scripts/smoke_test_credential.py
"""
import json
import os
import sys

EXPECTED_EMAIL = "rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com"
EXPECTED_PROJECT = "rf-rag-ingester-493016"


def main() -> int:
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        print("FAIL: GOOGLE_SERVICE_ACCOUNT_JSON not set in environment")
        return 1

    try:
        info = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"FAIL: env var is not valid JSON: {e}")
        return 1

    actual_email = info.get("client_email", "<missing>")
    actual_project = info.get("project_id", "<missing>")
    has_private_key = bool(info.get("private_key"))

    print(f"client_email:    {actual_email}")
    print(f"project_id:      {actual_project}")
    print(f"has private_key: {has_private_key}")

    if actual_email != EXPECTED_EMAIL:
        print(f"FAIL: client_email does not match expected {EXPECTED_EMAIL}")
        return 1
    if actual_project != EXPECTED_PROJECT:
        print(f"FAIL: project_id does not match expected {EXPECTED_PROJECT}")
        return 1
    if not has_private_key:
        print("FAIL: JSON has no private_key field")
        return 1

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as e:
        print(f"FAIL: missing google API libs ({e}). Install with:")
        print("  pip3 install --break-system-packages "
              "google-api-python-client google-auth")
        return 1

    try:
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
    except Exception as e:
        print(f"FAIL: could not build credentials from JSON: {e}")
        return 1

    try:
        drive = build("drive", "v3", credentials=creds, cache_discovery=False)
        about = drive.about().get(fields="user(emailAddress,displayName)").execute()
    except Exception as e:
        print(f"FAIL: drive.about().get() raised: {e}")
        return 1

    user = about.get("user", {})
    print(f"\nDrive API auth check: PASS")
    print(f"  Authenticated as:  {user.get('emailAddress', '<unknown>')}")
    print(f"  Display name:      {user.get('displayName', '<unknown>')}")
    print("\nCredential is live and Drive API accepts it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
