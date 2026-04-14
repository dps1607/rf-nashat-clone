"""
Diagnostic: prompt for a password in the terminal (getpass, not echoed),
then run it through the exact same authenticate() path the admin_ui login uses.

Prints PASS or FAIL. Does not log the password anywhere.

Added in session 14 to rule out a password-vs-hash mismatch during a login
debugging session. The real bug turned out to be SESSION_COOKIE_SECURE=True
dropping cookies over localhost HTTP — see admin_ui/app.py
ADMIN_DEV_INSECURE_COOKIES env var for the fix.

Usage:
  cd /path/to/rf-nashat-clone
  ./venv/bin/python scripts/test_login_dan.py

Kept for future login debugging. Generalize to arbitrary usernames if needed.
"""
import getpass
import os
import sys

# sys.path shim (session 15): let this script run without PYTHONPATH=.
# Prepend the repo root (parent of scripts/) so `from admin_ui.auth import ...`
# resolves when invoked as `./venv/bin/python scripts/test_login_dan.py`.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from admin_ui.auth import authenticate, _load_users

users = _load_users()
if "dan" not in users:
    print("FAIL: user 'dan' not in admin_users.json")
    sys.exit(1)

rec = users["dan"]
print(f"user 'dan' present, created={rec.get('created')}, hash_prefix={rec.get('password_hash','')[:7]}")

pw = getpass.getpass("Enter the password you are typing into the login form: ")
print(f"(received {len(pw)} characters)")

result = authenticate("dan", pw)
if result is None:
    print("FAIL: authenticate() returned None — password does not match stored hash.")
    print("     Most likely: a typo in either the rotation or the login form.")
else:
    print(f"PASS: authenticate() returned {result}")
    print("     Password is correct. If login form still fails, the bug is in the route, not auth.")
