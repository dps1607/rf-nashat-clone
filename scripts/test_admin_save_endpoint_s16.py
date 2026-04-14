"""Step 11 endpoint smoke — direct invocation of api_folders_save via
the Flask test client, bypassing the normal session-cookie auth by
injecting a pre-authenticated session. Verifies the new two-bucket
save contract without needing a browser click.

This is a code-level check. The actual click-through still runs in
the browser on port 5052 — this just de-risks the endpoint logic so
we know any issues at click time are UI, not server.
"""
import os
import sys
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from dotenv import load_dotenv
load_dotenv(REPO / ".env")

from admin_ui.app import app

# Mint a test client and inject a session with a valid user (dict shape).
# auth.py's current_user() returns session.get("user"), which must be
# a dict for the login_required decorator's user.get(...) calls to work.
client = app.test_client()
with client.session_transaction() as sess:
    sess["user"] = {
        "username": "dan",
        "email": "dan@reimagined-health.com",
    }


def post(payload):
    return client.post(
        "/admin/api/folders/save",
        data=json.dumps(payload),
        content_type="application/json",
    )


passed = 0
failed = 0

def check(label, cond, detail=""):
    global passed, failed
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {label}" + (f"  — {detail}" if detail else ""))
    if cond: passed += 1
    else: failed += 1


# Test 1: Two-bucket valid payload (1 folder + 1 file, matches current selection)
payload_valid = {
    "selected_folders": ["18S1VfRyFdckGU_p15m3UmXS8cjHtMEKM"],
    "selected_files": ["1oJyksHGx9wo_44k31MD3nTnfxnBKBMlL"],
    "library_assignments": {
        "18S1VfRyFdckGU_p15m3UmXS8cjHtMEKM": "rf_reference_library",
        "1oJyksHGx9wo_44k31MD3nTnfxnBKBMlL": "rf_reference_library",
    },
    "timestamp": "2026-04-14T12:00:00Z",
}

resp = post(payload_valid)
body = resp.get_json()
check(f"valid two-bucket payload returns 200 (got {resp.status_code})",
      resp.status_code == 200)
if body:
    check("saved_folders=1 in response",
          body.get("saved_folders") == 1,
          f"got {body.get('saved_folders')}")
    check("saved_files=1 in response",
          body.get("saved_files") == 1,
          f"got {body.get('saved_files')}")
    check("response.ok=True", body.get("ok") is True)


# Test 2: Misclassified folder (file_id in selected_folders) → 400
payload_misfolder = {
    "selected_folders": ["1oJyksHGx9wo_44k31MD3nTnfxnBKBMlL"],  # a FILE id
    "selected_files": [],
    "library_assignments": {"1oJyksHGx9wo_44k31MD3nTnfxnBKBMlL": "rf_reference_library"},
    "timestamp": "2026-04-14T12:00:00Z",
}
resp = post(payload_misfolder)
body = resp.get_json() or {}
check(f"misclassified folder (file in folders bucket) rejected with 400 (got {resp.status_code})",
      resp.status_code == 400)
check("error message mentions 'not folders in the manifest'",
      "not folders in the manifest" in (body.get("error") or ""))


# Test 3: Folder-only payload (backward compat — selected_files omitted)
payload_folderonly = {
    "selected_folders": ["18S1VfRyFdckGU_p15m3UmXS8cjHtMEKM"],
    "library_assignments": {"18S1VfRyFdckGU_p15m3UmXS8cjHtMEKM": "rf_reference_library"},
    "timestamp": "2026-04-14T12:00:00Z",
}
resp = post(payload_folderonly)
body = resp.get_json() or {}
check(f"folder-only payload (no selected_files key) returns 200 (got {resp.status_code})",
      resp.status_code == 200)
check("saved_folders=1",
      body.get("saved_folders") == 1,
      f"got {body.get('saved_folders')}")
check("saved_files=0",
      body.get("saved_files") == 0,
      f"got {body.get('saved_files')}")


# Test 4: File-only payload (new path)
payload_fileonly = {
    "selected_folders": [],
    "selected_files": ["1oJyksHGx9wo_44k31MD3nTnfxnBKBMlL"],
    "library_assignments": {"1oJyksHGx9wo_44k31MD3nTnfxnBKBMlL": "rf_reference_library"},
    "timestamp": "2026-04-14T12:00:00Z",
}
resp = post(payload_fileonly)
body = resp.get_json() or {}
check(f"file-only payload returns 200 (got {resp.status_code})",
      resp.status_code == 200)
check("saved_folders=0 for file-only", body.get("saved_folders") == 0)
check("saved_files=1 for file-only", body.get("saved_files") == 1)


# Test 5: Missing library assignment → 400
payload_missing_lib = {
    "selected_folders": ["18S1VfRyFdckGU_p15m3UmXS8cjHtMEKM"],
    "selected_files": [],
    "library_assignments": {},
    "timestamp": "2026-04-14T12:00:00Z",
}
resp = post(payload_missing_lib)
body = resp.get_json() or {}
check("missing library assignment returns 400",
      resp.status_code == 400)
check("error mentions 'missing library assignment'",
      "missing library assignment" in (body.get("error") or ""))


# Test 6: Unknown library → 400
payload_bad_lib = {
    "selected_folders": ["18S1VfRyFdckGU_p15m3UmXS8cjHtMEKM"],
    "selected_files": [],
    "library_assignments": {"18S1VfRyFdckGU_p15m3UmXS8cjHtMEKM": "rf_evil_library"},
    "timestamp": "2026-04-14T12:00:00Z",
}
resp = post(payload_bad_lib)
body = resp.get_json() or {}
check("unknown library returns 400", resp.status_code == 400)
check("error mentions 'library not in allowed set'",
      "library not in allowed set" in (body.get("error") or ""))


print()
print(f"PASS: {passed}  FAIL: {failed}")

# Restore selection_state.json to the session 16 post-fix shape
# (the tests above overwrote it repeatedly; final state should be the 2-bucket valid payload)
final = {
    "selected_folders": ["18S1VfRyFdckGU_p15m3UmXS8cjHtMEKM"],
    "selected_files": ["1oJyksHGx9wo_44k31MD3nTnfxnBKBMlL"],
    "library_assignments": {
        "18S1VfRyFdckGU_p15m3UmXS8cjHtMEKM": "rf_reference_library",
        "1oJyksHGx9wo_44k31MD3nTnfxnBKBMlL": "rf_reference_library",
    },
    "timestamp": "2026-04-14T12:00:00Z",
}
sel_path = REPO / "data" / "selection_state.json"
sel_path.write_text(json.dumps(final, indent=2))
print(f"\nrestored {sel_path} to session 16 working state")

sys.exit(0 if failed == 0 else 1)
