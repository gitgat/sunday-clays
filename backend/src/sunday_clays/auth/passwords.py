"""argon2id password hashing and verification."""

import logging
from typing import Final

from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import InvalidHashError, VerificationError

from sunday_clays.auth.sessions import Role
from sunday_clays.config import Settings

log = logging.getLogger(__name__)

# OWASP argon2id profile; scripts/dev-secrets.sh (Plan 01 T4) uses the same parameters.
MEMORY_COST_KIB: Final = 19_456
TIME_COST: Final = 2
PARALLELISM: Final = 1
# verify() runs with the parameters stored in the hash; refuse any hash that would cost more
# memory than hashpw produces, so the 4 concurrent verifies of routes/auth.py stay near 80 MiB.
MAX_VERIFY_MEMORY_KIB: Final = MEMORY_COST_KIB

_HASHER: Final = PasswordHasher(
    time_cost=TIME_COST, memory_cost=MEMORY_COST_KIB, parallelism=PARALLELISM, type=Type.ID
)


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        params = extract_parameters(password_hash)
    except InvalidHashError:
        log.error("configured password hash is not a valid argon2 hash")
        return False
    if params.memory_cost > MAX_VERIFY_MEMORY_KIB:
        log.error(
            "configured password hash needs %d KiB (cap %d KiB); regenerate it with hashpw",
            params.memory_cost,
            MAX_VERIFY_MEMORY_KIB,
        )
        return False
    try:
        return _HASHER.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def match_role(settings: Settings, password: str) -> Role | None:
    """Admin is checked first, so a password matching both hashes logs in as admin."""
    if verify_password(settings.admin_password_hash.get_secret_value(), password):
        return "admin"
    if verify_password(settings.viewer_password_hash.get_secret_value(), password):
        return "viewer"
    return None
