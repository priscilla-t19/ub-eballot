"""
Models for UB eBallot
Designed with strict separation between identity verification and voting data.
"""

from app import db
from datetime import datetime, timezone
import hashlib


# ──────────────────────────────────────────
# IDENTITY MODULE — eligibility data only
# ──────────────────────────────────────────

class UBStudentRegistry(db.Model):
    """
    Official UB registered students dataset.
    Pre-loaded by admin and persisted in the database.
    This is the single source of truth for voter eligibility.
    """
    __tablename__ = 'ub_student_registry'

    id = db.Column(db.Integer, primary_key=True)
    student_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(200), nullable=False)
    ub_email = db.Column(db.String(120), nullable=True)   # UB institutional email for OTP delivery
    programme = db.Column(db.String(200), nullable=True)
    year_of_study = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    imported_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<UBStudentRegistry {self.student_number}>'


class OTPCode(db.Model):
    """
    One-time password sent to a student's UB email to prove ownership of the
    student number. Prevents voting with stolen/guessed student IDs.

    Security properties:
    - The raw OTP is never stored — only SHA-256(otp) is kept.
    - Expires after OTP_EXPIRY seconds (default 10 minutes).
    - Single-use: is_used flag set on first successful verification.
    - Attempt counter: invalidated after 5 failed attempts.
    - Tied to (student_number, election_id) — cannot be reused across elections.
    """
    __tablename__ = 'otp_codes'

    id = db.Column(db.Integer, primary_key=True)
    student_number = db.Column(db.String(20), nullable=False, index=True)
    election_id = db.Column(db.Integer, db.ForeignKey('elections.id'), nullable=False)
    code_hash = db.Column(db.String(64), nullable=False)   # SHA-256 of the 6-digit code
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    attempts = db.Column(db.Integer, default=0)

    @property
    def is_expired(self):
        now = datetime.now(timezone.utc)
        exp = self.expires_at.replace(tzinfo=timezone.utc) if self.expires_at.tzinfo is None else self.expires_at
        return now > exp

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired and self.attempts < 5

    def __repr__(self):
        return f'<OTPCode student={self.student_number} election={self.election_id}>'


# ──────────────────────────────────────────
# VOTING MODULE MODELS (sandboxed)
# ──────────────────────────────────────────

class Election(db.Model):
    """Represents an SRC election."""
    __tablename__ = 'elections'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    results_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    positions = db.relationship('Position', backref='election', lazy=True,
                                cascade='all, delete-orphan')
    voter_tokens = db.relationship('VoterToken', backref='election', lazy=True,
                                   cascade='all, delete-orphan')
    ballots = db.relationship('EncryptedBallot', backref='election', lazy=True,
                              cascade='all, delete-orphan')

    @property
    def is_open(self):
        now = datetime.now(timezone.utc)
        start = (self.start_time.replace(tzinfo=timezone.utc)
                 if self.start_time.tzinfo is None else self.start_time)
        end = (self.end_time.replace(tzinfo=timezone.utc)
               if self.end_time.tzinfo is None else self.end_time)
        return self.is_active and start <= now <= end


class Position(db.Model):
    """SRC position being contested."""
    __tablename__ = 'positions'

    id = db.Column(db.Integer, primary_key=True)
    election_id = db.Column(db.Integer, db.ForeignKey('elections.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)

    candidates = db.relationship('Candidate', backref='position', lazy=True,
                                 cascade='all, delete-orphan')


class Candidate(db.Model):
    """Candidate running for a position."""
    __tablename__ = 'candidates'

    id = db.Column(db.Integer, primary_key=True)
    position_id = db.Column(db.Integer, db.ForeignKey('positions.id'), nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    student_number = db.Column(db.String(20), nullable=False)
    party = db.Column(db.String(200), nullable=True)
    manifesto = db.Column(db.Text, nullable=True)
    photo_filename = db.Column(db.String(200), nullable=True)


class VoterToken(db.Model):
    """
    Hashed voter commitment — proves a vote was cast for an election without
    revealing who cast it.

    token_hash = HMAC-SHA256(key=VOTER_PEPPER, msg='STUDENT_NUMBER:election_id')

    The student number is NEVER stored here. Only the irreversible HMAC is kept.
    The unique DB constraint provides race-condition-safe duplicate vote prevention.
    """
    __tablename__ = 'voter_tokens'

    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    election_id = db.Column(db.Integer, db.ForeignKey('elections.id'), nullable=False)
    voted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<VoterToken election={self.election_id}>'


class EncryptedBallot(db.Model):
    """
    Encrypted ballot — never linked to a voter identity.
    Stored in a tamper-evident chain via prev_hash.
    """
    __tablename__ = 'encrypted_ballots'

    id = db.Column(db.Integer, primary_key=True)
    election_id = db.Column(db.Integer, db.ForeignKey('elections.id'), nullable=False)
    encrypted_data = db.Column(db.Text, nullable=False)      # AES-encrypted ballot JSON
    receipt_code = db.Column(db.String(64), unique=True, nullable=False)
    receipt_hash = db.Column(db.String(256), nullable=False)  # SHA-256 of receipt_code
    prev_hash = db.Column(db.String(256), nullable=True)      # Hash chain for tamper detection
    chain_hash = db.Column(db.String(256), nullable=False)    # SHA-256(encrypted_data + prev_hash)
    cast_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def compute_chain_hash(self):
        data = (self.encrypted_data or '') + (self.prev_hash or '')
        return hashlib.sha256(data.encode()).hexdigest()


# ──────────────────────────────────────────
# ADMIN MODULE
# ──────────────────────────────────────────

class AdminUser(db.Model):
    __tablename__ = 'admin_users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<AdminUser {self.username}>'


class ReceiptBallot(db.Model):
    """
    Maps receipt codes to ballots for verification.
    Stores the hashed receipt code only — never the plaintext code.
    """
    __tablename__ = 'receipt_ballots'

    id = db.Column(db.Integer, primary_key=True)
    ballot_id = db.Column(db.Integer, db.ForeignKey('encrypted_ballots.id'), nullable=False)
    receipt_hash = db.Column(db.String(256), unique=True, nullable=False, index=True)
    verified_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<ReceiptBallot ballot_id={self.ballot_id}>'


class AuditLog(db.Model):
    """
    Audit trail for all security-relevant events.
    Immutable log for accountability and investigation.
    """
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.String(100), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 compatible
    user_agent = db.Column(db.String(500), nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def __repr__(self):
        return f'<AuditLog {self.event_type} @ {self.timestamp}>'
