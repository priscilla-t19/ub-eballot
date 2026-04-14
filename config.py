import os
from datetime import timedelta

class Config:
    # ────────────────────────────────────────
    # CORE FLASK CONFIG
    # ────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ub-eballot-alpha-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///ub_eballot.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    TESTING = os.environ.get('TESTING', 'False').lower() == 'true'
    ENVIRONMENT = os.environ.get('FLASK_ENV', 'production').lower()
    IS_LOCAL_DEV = DEBUG or TESTING or ENVIRONMENT == 'development'

    # ────────────────────────────────────────
    # CRYPTOGRAPHY
    # ────────────────────────────────────────
    # Encryption key for ballots (in production, generate and store separately from SECRET_KEY)
    BALLOT_ENCRYPTION_KEY = os.environ.get('BALLOT_ENCRYPTION_KEY') or None

    # Voter token pepper — HMAC key used to hash student IDs for anonymous vote deduplication.
    # CRITICAL: must never change after voting begins (changing invalidates all voter tokens).
    VOTER_PEPPER = os.environ.get('VOTER_PEPPER') or 'ub-eballot-voter-pepper-change-in-production'

    # ────────────────────────────────────────
    # SESSION & SECURITY
    # ────────────────────────────────────────
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_COOKIE_SECURE = os.environ.get(
        'SESSION_COOKIE_SECURE',
        'False' if IS_LOCAL_DEV else 'True'
    ).lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get(
        'SESSION_COOKIE_SAMESITE',
        'Lax' if IS_LOCAL_DEV else 'Strict'
    )
    SESSION_COOKIE_NAME = 'ub_eballot_session'

    # ────────────────────────────────────────
    # OTP CONFIG
    # ────────────────────────────────────────
    OTP_EXPIRY = int(os.environ.get('OTP_EXPIRY', 600))  # 10 minutes
    OTP_LENGTH = 6  # 6-digit OTP

    # ────────────────────────────────────────
    # RATE LIMITING
    # ────────────────────────────────────────
    RATELIMIT_OTP_ATTEMPTS = 5  # Max attempts before lockout
    RATELIMIT_OTP_WINDOW = 300   # Time window in seconds (5 minutes)
    RATELIMIT_LOGIN_ATTEMPTS = 10
    RATELIMIT_LOGIN_WINDOW = 900

    # ────────────────────────────────────────
    # MAIL CONFIG
    # ────────────────────────────────────────
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = (
        'UB eBallot',
        os.environ.get('MAIL_USERNAME', 'noreply@ub.ac.bw')
    )
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
    
    # ────────────────────────────────────────
    # SECURITY HEADERS
    # ────────────────────────────────────────
    PREFERRED_URL_SCHEME = os.environ.get(
        'PREFERRED_URL_SCHEME',
        'http' if IS_LOCAL_DEV else 'https'
    )
