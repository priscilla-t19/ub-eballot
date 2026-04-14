"""
Security Hardening Module for UB eBallot
Implements OWASP best practices and election-specific security measures.
"""

from flask import request, abort, flash, redirect, url_for
from functools import wraps
from datetime import datetime, timezone, timedelta
import logging
from app import db
from models import AuditLog

logger = logging.getLogger(__name__)


# ────────────────────────────────────────
# RATE LIMITING (prevent brute force attacks)
# ────────────────────────────────────────

class RateLimiter:
    """Simple in-memory rate limiter for auth endpoints."""
    
    def __init__(self):
        self.attempts = {}
    
    def is_rate_limited(self, key: str, max_attempts: int = 5, window_seconds: int = 300) -> bool:
        """Check if a key exceeds rate limit in time window."""
        now = datetime.now(timezone.utc)
        
        if key not in self.attempts:
            self.attempts[key] = []
        
        # Remove old attempts outside window
        self.attempts[key] = [
            ts for ts in self.attempts[key] 
            if (now - ts).total_seconds() < window_seconds
        ]
        
        if len(self.attempts[key]) >= max_attempts:
            return True
        
        self.attempts[key].append(now)
        return False
    
    def reset(self, key: str):
        """Reset attempts for a key."""
        self.attempts.pop(key, None)


rate_limiter = RateLimiter()


def rate_limit(max_attempts: int = 5, window_seconds: int = 300):
    """
    Decorator for rate limiting auth endpoints.
    Usage: @rate_limit(max_attempts=5, window_seconds=300)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Rate limit by IP + endpoint
            client_ip = request.remote_addr
            endpoint = request.endpoint
            key = f"{client_ip}:{endpoint}"
            
            if rate_limiter.is_rate_limited(key, max_attempts, window_seconds):
                log_security_event(
                    'RATE_LIMIT_EXCEEDED',
                    f'High OTP attempts from {client_ip}',
                    level='WARNING'
                )
                abort(429)  # Too Many Requests
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ────────────────────────────────────────
# AUDIT LOGGING
# ────────────────────────────────────────

def log_security_event(event_type: str, description: str, level: str = 'INFO', user_id: str = None):
    """
    Log security-relevant events to both file and database.
    
    Event types:
    - VOTE_CAST: ballot encrypted and stored
    - OTP_SENT: OTP generated and sent
    - OTP_VERIFIED: student passed authentication
    - DUPLICATE_VOTE_BLOCKED: attempted double voting
    - RATE_LIMIT_EXCEEDED: brute force attempt
    - INVALID_BALLOT: malformed ballot submission
    - ADMIN_LOGIN: admin login attempt
    - REGISTRY_IMPORTED: student registry uploaded
    """
    log_entry = AuditLog(
        event_type=event_type,
        description=description,
        user_id=user_id,
        ip_address=request.remote_addr if request else None,
        user_agent=request.user_agent.string if request else None,
        timestamp=datetime.now(timezone.utc)
    )
    try:
        db.session.add(log_entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Failed to persist audit log entry for %s", event_type)
    
    # Also log to application logger
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(f"[{event_type}] {description} | IP: {request.remote_addr if request else 'N/A'}")


# ────────────────────────────────────────
# INPUT VALIDATION & SANITIZATION
# ────────────────────────────────────────

def validate_student_number(student_id: str) -> bool:
    """Validate student number format (alphanumeric, 3-20 chars)."""
    student_id = student_id.strip().upper()
    return bool(student_id) and 3 <= len(student_id) <= 20 and student_id.isalnum()


def validate_email(email: str) -> bool:
    """Basic email validation."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def sanitize_csv_input(filename: str) -> bool:
    """Prevent malicious filenames in CSV uploads."""
    import os
    if '..' in filename or filename.startswith('/'):
        return False
    return filename.endswith('.csv')


def validate_otp_code(code: str) -> bool:
    """Validate OTP code format (6 digits)."""
    return bool(code) and code.isdigit() and len(code) == 6


# ────────────────────────────────────────
# SESSION SECURITY
# ────────────────────────────────────────

def configure_session_security(app):
    """
    Configure Flask session security settings.
    Call this in create_app() after Flask initialization.
    """
    app.config.update(
        SESSION_COOKIE_SECURE=app.config.get('SESSION_COOKIE_SECURE', True),
        SESSION_COOKIE_HTTPONLY=app.config.get('SESSION_COOKIE_HTTPONLY', True),
        SESSION_COOKIE_SAMESITE=app.config.get('SESSION_COOKIE_SAMESITE', 'Strict'),
        PERMANENT_SESSION_LIFETIME=app.config.get(
            'PERMANENT_SESSION_LIFETIME',
            timedelta(minutes=30)
        ),
        SESSION_COOKIE_NAME=app.config.get('SESSION_COOKIE_NAME', 'ub_eballot_session'),
    )


def configure_security_headers(app):
    """
    Add security headers to all responses.
    Call this in create_app() after Flask initialization.
    """
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        if app.config.get('SESSION_COOKIE_SECURE') or app.config.get('PREFERRED_URL_SCHEME') == 'https':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "  # Allow inline for now; move to external scripts later
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none';"
        )
        return response


# ────────────────────────────────────────
# ADMIN AUTHENTICATION HARDENING
# ────────────────────────────────────────

def require_admin_session():
    """Decorator to protect admin routes."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import session
            
            if 'admin_logged_in' not in session or not session['admin_logged_in']:
                log_security_event(
                    'UNAUTHORIZED_ADMIN_ACCESS',
                    f'Unauthorized admin access attempt',
                    level='WARNING'
                )
                if request.method in ('GET', 'HEAD'):
                    flash('Please log in to access the admin panel.', 'warning')
                    next_target = request.full_path.rstrip('?') if request.query_string else request.path
                    return redirect(url_for('admin.admin_login', next=next_target))
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ────────────────────────────────────────
# BALLOT CHAIN VERIFICATION
# ────────────────────────────────────────

def verify_ballot_chain_integrity(election_id: int) -> dict:
    """
    Verify that the ballot chain has not been tampered with.
    Returns: {is_valid: bool, issues: [str]}
    """
    from models import EncryptedBallot
    from crypto_utils import compute_chain_hash
    
    issues = []
    ballots = (EncryptedBallot.query
               .filter_by(election_id=election_id)
               .order_by(EncryptedBallot.id.asc())
               .all())
    
    prev_hash = None
    for ballot in ballots:
        expected_hash = compute_chain_hash(ballot.encrypted_data, prev_hash)
        if ballot.chain_hash != expected_hash:
            issues.append(f"Ballot {ballot.id}: chain hash mismatch (tampering detected)")
        prev_hash = ballot.chain_hash
    
    return {
        'is_valid': len(issues) == 0,
        'issues': issues,
        'ballots_verified': len(ballots),
        'timestamp': datetime.now(timezone.utc)
    }


# ────────────────────────────────────────
# DEPLOYMENT SECURITY CHECKLIST
# ────────────────────────────────────────

DEPLOYMENT_CHECKLIST = {
    'environment': [
        '[ ] Change SECRET_KEY',
        '[ ] Change BALLOT_ENCRYPTION_KEY',
        '[ ] Change VOTER_PEPPER',
        '[ ] Change default admin credentials',
        '[ ] Set DATABASE_URL to production database',
        '[ ] Enable HTTPS/SSL certificates',
        '[ ] Configure MAIL_SERVER / MAIL_USERNAME / MAIL_PASSWORD',
    ],
    'flask_config': [
        '[ ] Set DEBUG=False',
        '[ ] Set TESTING=False',
        '[ ] Configure secure session cookies',
        '[ ] Enable CSRF protection on all forms',
        '[ ] Configure CORS appropriately',
    ],
    'database': [
        '[ ] Run database migrations',
        '[ ] Create automated backups (at least daily)',
        '[ ] Enable database encryption at rest',
        '[ ] Restrict direct database access to app server only',
        '[ ] Set database password to strong random value',
    ],
    'infrastructure': [
        '[ ] Use firewall to restrict access by IP',
        '[ ] Run behind reverse proxy (nginx/Apache)',
        '[ ] Enable logging and monitoring',
        '[ ] Configure log rotation',
        '[ ] Set up uptime monitoring',
        '[ ] Use strong TLS configuration (TLS 1.2+)',
    ],
    'application': [
        '[ ] Verify rate limiting is working',
        '[ ] Test ballot encryption/decryption',
        '[ ] Verify chain integrity checks',
        '[ ] Test OTP system end-to-end',
        '[ ] Audit all admin endpoints',
        '[ ] Run security penetration test',
    ],
}


def print_deployment_checklist():
    """Print security deployment checklist."""
    print("\n" + "="*60)
    print("DEPLOYMENT SECURITY CHECKLIST")
    print("="*60)
    for category, items in DEPLOYMENT_CHECKLIST.items():
        print(f"\n{category.upper()}:")
        for item in items:
            print(f"  {item}")
    print("\n" + "="*60)
