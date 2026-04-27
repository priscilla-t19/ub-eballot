"""
Cryptographic utilities for UB eBallot.
Handles ballot encryption, hashing, voter token generation, and receipt codes.
"""

import hashlib
import hmac
import json
import secrets
import string
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from flask import current_app

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

_ph = PasswordHasher()


# ── Ballot encryption ─────────────────────

def get_fernet_key() -> bytes:
    """Return the Fernet encryption key for ballot storage.

    Preference order:
    1. BALLOT_ENCRYPTION_KEY in .env — must be a Fernet-generated key
       (use: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    2. Derived from SECRET_KEY via PBKDF2 — alpha fallback only.

    The Fernet key must be exactly 32 url-safe base64-encoded bytes.
    """
    stored_key = current_app.config.get('BALLOT_ENCRYPTION_KEY')
    if stored_key:
        # Accept str (from .env) or bytes; do NOT double-encode.
        key_bytes = stored_key.encode() if isinstance(stored_key, str) else stored_key
        try:
            # Validate the key by instantiating Fernet — raises ValueError if malformed.
            Fernet(key_bytes)
        except Exception as exc:
            raise ValueError(
                "BALLOT_ENCRYPTION_KEY in .env is not a valid Fernet key. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            ) from exc
        return key_bytes

    # Derive from SECRET_KEY (alpha fallback — not for production use).
    current_app.logger.warning(
        "BALLOT_ENCRYPTION_KEY not set — deriving from SECRET_KEY. "
        "Set BALLOT_ENCRYPTION_KEY in .env before production deployment."
    )
    secret = current_app.config['SECRET_KEY'].encode()
    salt = b'ub_eballot_salt_v1'
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret))


def encrypt_ballot(ballot_data: dict) -> str:
    """Encrypt ballot dictionary to a Fernet token string."""
    f = Fernet(get_fernet_key())
    return f.encrypt(json.dumps(ballot_data).encode()).decode()


def decrypt_ballot(encrypted_data: str) -> dict:
    """Decrypt a Fernet-encrypted ballot."""
    f = Fernet(get_fernet_key())
    return json.loads(f.decrypt(encrypted_data.encode()).decode())


# ── Voter token (anonymous duplicate-vote prevention) ──

def compute_voter_token(student_number: str, election_id: int) -> str:
    """
    Compute HMAC-SHA256(key=VOTER_PEPPER, msg='STUDENT_NUMBER:election_id').

    Creates a deterministic, unlinkable token per (student, election).
    Stored in the voter_tokens table to detect duplicate votes without ever
    storing the student number inside the voting module.

    Security properties:
    - Without VOTER_PEPPER the token cannot be reversed to the student ID.
    - Different election_id values produce completely different tokens, so
      cross-election linkage is not possible.
    """
    pepper = current_app.config['VOTER_PEPPER']
    message = f"{student_number.strip().upper()}:{election_id}".encode()
    return hmac.new(pepper.encode(), message, hashlib.sha256).hexdigest()


# ── Receipt codes ────────────────────────

def generate_receipt_code() -> str:
    """Generate a unique receipt code for vote verification."""
    return secrets.token_hex(16).upper()


def hash_receipt(receipt_code: str) -> str:
    return hashlib.sha256(receipt_code.encode()).hexdigest()


# ── Tamper-evident ballot chain ───────────

def compute_chain_hash(encrypted_data: str, prev_hash: str | None) -> str:
    """Tamper-evident chain: SHA-256(encrypted_data + prev_hash)."""
    combined = encrypted_data + (prev_hash or '')
    return hashlib.sha256(combined.encode()).hexdigest()


def get_last_chain_hash(election_id: int) -> str | None:
    """Get the most recent ballot's chain hash for a given election."""
    from models import EncryptedBallot
    last = (EncryptedBallot.query
            .filter_by(election_id=election_id)
            .order_by(EncryptedBallot.id.desc())
            .first())
    return last.chain_hash if last else None


def verify_ballot_chain(election_id: int) -> bool:
    """
    Verify tamper-evident chain integrity for all ballots in an election.
    Returns True if chain is intact, False if tampering is detected.
    """
    from models import EncryptedBallot
    ballots = (EncryptedBallot.query
               .filter_by(election_id=election_id)
               .order_by(EncryptedBallot.id.asc())
               .all())
    prev_hash = None
    for ballot in ballots:
        expected = compute_chain_hash(ballot.encrypted_data, prev_hash)
        if ballot.chain_hash != expected:
            return False
        prev_hash = ballot.chain_hash
    return True


# ── OTP generation ───────────────────────

def generate_otp() -> str:
    """
    Generate a cryptographically secure 6-digit numeric OTP.
    Uses secrets.choice to guarantee uniform distribution — random.randint
    is NOT used because it is not cryptographically secure.
    """
    return ''.join(secrets.choice(string.digits) for _ in range(6))


def hash_otp(raw_otp: str) -> str:
    """
    SHA-256 hash of the raw OTP for safe database storage.
    The raw code is never persisted — only the hash is stored.
    """
    return hashlib.sha256(raw_otp.encode()).hexdigest()


# ── Admin password hashing (Argon2) ──────

def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _ph.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
