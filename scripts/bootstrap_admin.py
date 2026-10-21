"""Create the first administrator in the running Docker Compose stack (E2.12).

1. ``auth-service`` creates (or finds) the account and returns its id.
2. ``role-service`` assigns the seeded ``admin`` role to that id.

The password is read with ``getpass`` (or from ``BOOTSTRAP_ADMIN_PASSWORD`` for
automation) and sent through stdin, so it never appears in a command line.
"""

import argparse
import getpass
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _compose_exec(service: str, *command: str, stdin: str | None = None) -> str:
    completed = subprocess.run(
        ["docker", "compose", "exec", "-T", service, *command],
        cwd=_REPO_ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
        raise SystemExit(f"{service}: command failed ({completed.returncode})")
    return completed.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD") or getpass.getpass(
        f"Password for {args.email}: "
    )
    account_id = _compose_exec(
        "auth-service",
        "python",
        "bootstrap_account.py",
        "--email",
        args.email,
        "--password-stdin",
        stdin=password + "\n",
    ).splitlines()[-1]
    print(f"account: {account_id}")
    print(
        _compose_exec(
            "role-service", "python", "bootstrap_admin.py", "--account-id", account_id
        )
    )
    print("log in again to receive a token with the admin role")
    return 0


if __name__ == "__main__":
    sys.exit(main())
