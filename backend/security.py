"""Password hashing and verification.

Stored format: "pbkdf2_sha256$<salt>$<hash_hex>" (matches the format already
used by the seeded rows in users.password_hash).

The iteration count is NOT encoded in the stored string (the seeded rows only
have algo$salt$hash), so it must be a fixed constant shared by signup and
login: 120,000 iterations of PBKDF2-HMAC-SHA256, confirmed by the user as
what the seed script used.
"""
import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 120_000  # matches the seed script's PBKDF2-HMAC-SHA256 setting
SALT_BYTES = 16


def _derive(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), ITERATIONS
    )
    return digest.hex()


def hash_password(password: str) -> str:
    """Hash a new password with a freshly generated salt."""
    salt = secrets.token_hex(SALT_BYTES)
    return f"{ALGORITHM}${salt}${_derive(password, salt)}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored 'algo$salt$hash' string.

    Never un-hashes the stored value: pulls the salt back out, re-hashes the
    candidate password with that same salt and iteration count, and compares
    the two hashes in constant time.
    """
    parts = stored.split("$")
    if len(parts) != 3:
        return False
    algorithm, salt, expected_hash = parts
    if algorithm != ALGORITHM:
        return False
    candidate_hash = _derive(password, salt)
    return hmac.compare_digest(candidate_hash, expected_hash)
