import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "dev-secrets.sh"
FAILS = "#!/usr/bin/env bash\necho 'stub: simulated failure' >&2\nexit 1\n"
PRINTS_NOTHING = "#!/usr/bin/env bash\nexit 0\n"
NAMES = [
    "admin_password_hash",
    "database_url",
    "db_password",
    "session_secret",
    "viewer_password_hash",
]


def run_in_copy(root: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Runs a copy of dev-secrets.sh from <root>/scripts so it writes <root>/secrets."""
    (root / "scripts").mkdir(exist_ok=True)
    shutil.copy2(SCRIPT, root / "scripts" / "dev-secrets.sh")
    full_env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ.get("HOME", str(root)),
        **(env or {}),
    }
    return subprocess.run(
        ["bash", str(root / "scripts" / "dev-secrets.sh")],
        env=full_env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def argon2_verifies(hashed: str, password: str) -> bool:
    code = (
        "import sys\nfrom argon2 import PasswordHasher\n"
        "print(PasswordHasher().verify(sys.argv[1], sys.argv[2]))"
    )
    result = subprocess.run(
        [
            "uv",
            "run",
            "--quiet",
            "--no-project",
            "--with",
            "argon2-cffi",
            "python",
            "-c",
            code,
            hashed,
            password,
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    return result.stdout.strip() == "True"


def test_writes_every_secret_with_the_given_passwords(tmp_path: Path) -> None:
    result = run_in_copy(tmp_path, {"VIEWER_PASSWORD": "e2e-viewer", "ADMIN_PASSWORD": "e2e-admin"})

    assert result.returncode == 0, result.stderr
    secrets = tmp_path / "secrets"
    assert sorted(p.name for p in secrets.iterdir()) == NAMES
    viewer_hash = (secrets / "viewer_password_hash").read_text()
    assert viewer_hash.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    assert argon2_verifies(viewer_hash, "e2e-viewer")
    assert argon2_verifies((secrets / "admin_password_hash").read_text(), "e2e-admin")
    db_password = (secrets / "db_password").read_text()
    assert len(db_password) == 64
    assert (secrets / "database_url").read_text() == (
        f"postgresql+psycopg://sunday:{db_password}@db:5432/sunday_clays"
    )
    assert len((secrets / "session_secret").read_text()) == 64
    assert stat.S_IMODE(secrets.stat().st_mode) == 0o700
    assert "shown once" not in result.stdout


def test_never_overwrites_existing_secrets(tmp_path: Path) -> None:
    run_in_copy(tmp_path, {"VIEWER_PASSWORD": "first", "ADMIN_PASSWORD": "first"})
    before = {p.name: p.read_text() for p in (tmp_path / "secrets").iterdir()}

    result = run_in_copy(tmp_path, {"VIEWER_PASSWORD": "second", "ADMIN_PASSWORD": "second"})

    assert result.returncode == 0, result.stderr
    assert {p.name: p.read_text() for p in (tmp_path / "secrets").iterdir()} == before


def test_generates_and_prints_passwords_when_unset(tmp_path: Path) -> None:
    result = run_in_copy(tmp_path)

    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if "shown once" in line]
    assert len(lines) == 2
    viewer_password = next(line for line in lines if "viewer" in line).rsplit(": ", 1)[1]
    assert argon2_verifies(
        (tmp_path / "secrets" / "viewer_password_hash").read_text(), viewer_password
    )


def stub_first_on_path(root: Path, name: str, body: str) -> str:
    """A PATH whose first entry holds an executable stub called ``name``."""
    bin_dir = root / "stub-bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / name
    stub.write_text(body)
    stub.chmod(0o755)
    return f"{bin_dir}{os.pathsep}{os.environ['PATH']}"


@pytest.mark.parametrize("uv", [FAILS, PRINTS_NOTHING], ids=["uv-fails", "uv-prints-nothing"])
def test_a_failed_password_hash_stops_before_any_secret_is_written(
    tmp_path: Path, uv: str
) -> None:
    path = stub_first_on_path(tmp_path, "uv", uv)

    result = run_in_copy(tmp_path, {"PATH": path, "VIEWER_PASSWORD": "v", "ADMIN_PASSWORD": "a"})

    assert result.returncode != 0
    assert sorted(p.name for p in (tmp_path / "secrets").iterdir()) == []


@pytest.mark.parametrize(
    "openssl", [FAILS, PRINTS_NOTHING], ids=["openssl-fails", "openssl-prints-nothing"]
)
def test_a_failed_random_value_is_never_written(tmp_path: Path, openssl: str) -> None:
    path = stub_first_on_path(tmp_path, "openssl", openssl)

    result = run_in_copy(tmp_path, {"PATH": path, "VIEWER_PASSWORD": "v", "ADMIN_PASSWORD": "a"})

    assert result.returncode != 0
    written = {p.name: p.stat().st_size for p in (tmp_path / "secrets").iterdir()}
    assert "session_secret" not in written
    assert all(size > 0 for size in written.values()), written
