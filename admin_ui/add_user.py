"""
CLI: Add or update an admin user.

Two modes depending on CLOUDFLARE_ACCESS_ENABLED:

Cloudflare Access mode (production):
    python3 -m admin_ui.add_user dan@reimagined-health.com --name "Dan Smith"

Local bcrypt mode (dev):
    python3 -m admin_ui.add_user dan
    (prompts for password)
"""
import argparse
import getpass
import os
import sys

from admin_ui.auth import (
    CLOUDFLARE_ACCESS_ENABLED,
    add_user, add_email_user, list_users,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add or update an admin user for the Nashat admin panel."
    )
    parser.add_argument(
        "identifier",
        help="Email address (Cloudflare mode) or username (local dev mode)",
    )
    parser.add_argument(
        "--name",
        default="",
        help="Display name (Cloudflare mode only). Defaults to the email localpart.",
    )
    parser.add_argument(
        "--role",
        default="admin",
        help="Role for this user. Default: admin.",
    )
    args = parser.parse_args()

    if CLOUDFLARE_ACCESS_ENABLED:
        if "@" not in args.identifier:
            print(
                "ERROR: in Cloudflare Access mode, the identifier must be an email address.",
                file=sys.stderr,
            )
            return 2
        add_email_user(args.identifier, args.name or args.identifier.split("@")[0], args.role)
        print(f"OK — email user '{args.identifier}' added with role '{args.role}'")
    else:
        if not args.identifier.isidentifier():
            print(
                f"ERROR: username must be a valid identifier: {args.identifier!r}",
                file=sys.stderr,
            )
            return 2
        print(f"Adding local-dev admin user: {args.identifier}")
        pw1 = getpass.getpass("Password: ")
        pw2 = getpass.getpass("Confirm:  ")
        if pw1 != pw2:
            print("ERROR: passwords do not match", file=sys.stderr)
            return 1
        if len(pw1) < 8:
            print("ERROR: password must be at least 8 characters", file=sys.stderr)
            return 1
        add_user(args.identifier, pw1, args.role)
        print(f"OK — local user '{args.identifier}' saved")

    print()
    print("Current admin users:")
    for u in list_users():
        print(f"  {u['key']}  ({u['role']})  {u['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
