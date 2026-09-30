"""Print an argon2id hash for VIEWER_PASSWORD_HASH / ADMIN_PASSWORD_HASH.

Usage: ``python -m sunday_clays.auth.hashpw``. The password is read twice from the terminal
with getpass and is never accepted on the command line.
"""

import argparse
import getpass
import sys
from collections.abc import Sequence

from sunday_clays.auth.passwords import hash_password


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sunday_clays.auth.hashpw",
        description="Print an argon2id hash of a password typed at the prompt.",
    )
    parser.parse_args(argv)
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if not password:
        print("error: the password is empty", file=sys.stderr)
        return 1
    if password != confirm:
        print("error: the passwords do not match", file=sys.stderr)
        return 1
    print(hash_password(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
