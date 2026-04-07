"""
CLI: Add or update an admin user.

Usage:
    python3 -m admin_ui.add_user <username>

Prompts for the password (hidden), hashes it, writes to admin_users.json.
"""
import getpass
import sys

from admin_ui.auth import add_user, list_users


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python3 -m admin_ui.add_user <username>", file=sys.stderr)
        return 2

    username = sys.argv[1]
    print(f"Adding admin user: {username}")
    pw1 = getpass.getpass("Password: ")
    pw2 = getpass.getpass("Confirm:  ")
    if pw1 != pw2:
        print("ERROR: passwords do not match", file=sys.stderr)
        return 1
    if len(pw1) < 8:
        print("ERROR: password must be at least 8 characters", file=sys.stderr)
        return 1
    add_user(username, pw1)
    print(f"OK — user '{username}' saved")
    print()
    print("Current admin users:")
    for u in list_users():
        print(f"  {u['username']} ({u['role']}) created {u['created']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
