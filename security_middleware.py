"""
CSRF Protection and Security Middleware for UB eBallot
Implements additional security layers for production deployment.
"""

import secrets
from flask import request, session, abort, current_app, render_template
from functools import wraps
import hashlib
import hmac
from datetime import datetime, timezone, timedelta


# ────────────────────────────────────────
# CSRF PROTECTION
# ────────────────────────────────────────

def generate_csrf_token():
    """Generate a secure CSRF token."""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
        session['csrf_token_time'] = datetime.now(timezone.utc).isoformat()
    return session['csrf_token']


def validate_csrf_token(token):
    """Validate CSRF token with time-based expiration."""
    if not token or 'csrf_token' not in session:
        return False

    # Check token matches
    if not hmac.compare_digest(token, session['csrf_token']):
        return False

    # Check token age (30 minutes max)
    token_time_str = session.get('csrf_token_time')
    if token_time_str:
        try:
            token_time = datetime.fromisoformat(token_time_str)
            if datetime.now(timezone.utc) - token_time > timedelta(minutes=30):
                # Token expired, generate new one
                session.pop('csrf_token', None)
                session.pop('csrf_token_time', None)
                return False
        except (ValueError, TypeError):
            return False

    return True


def csrf_protect():
    """Decorator to require valid CSRF token for POST/PUT/DELETE requests.

    On the admin login route, a failed CSRF check redirects back to the login
    form with a fresh token rather than returning a raw 403, so the user can
    simply try again without confusion.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
                token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
                if not validate_csrf_token(token):
                    # Clear the stale token so a fresh one is generated on the
                    # next GET request.
                    session.pop('csrf_token', None)
                    session.pop('csrf_token_time', None)

                    # On the login page, redirect gracefully instead of 403.
                    if request.endpoint and 'login' in request.endpoint:
                        from flask import flash, redirect, url_for
                        flash(
                            'Your session expired or the form was reloaded. '
                            'Please try logging in again.',
                            'warning'
                        )
                        return redirect(url_for(request.endpoint))

                    abort(403)  # Forbidden for all other protected routes
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ────────────────────────────────────────
# REQUEST VALIDATION MIDDLEWARE
# ────────────────────────────────────────

def validate_request_size(max_size=10*1024*1024):  # 10MB default
    """Validate request size to prevent DoS attacks."""
    content_length = request.content_length or 0
    if content_length > max_size:
        abort(413)  # Payload Too Large
    return True


def validate_content_type(allowed_types=None):
    """Validate Content-Type header."""
    if allowed_types is None:
        allowed_types = ['application/x-www-form-urlencoded', 'multipart/form-data', 'application/json']

    content_type = request.content_type or ''
    if not any(allowed in content_type for allowed in allowed_types):
        abort(400)  # Bad Request
    return True


# ────────────────────────────────────────
# SECURE HEADERS MIDDLEWARE
# ────────────────────────────────────────

def add_secure_headers(response):
    """Add comprehensive security headers to responses."""
    # Security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

    # HTTPS-only in production
    if current_app.config.get('PREFERRED_URL_SCHEME') == 'https':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'

    # Content Security Policy
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "object-src 'none';"
    )
    response.headers['Content-Security-Policy'] = csp

    return response


# ────────────────────────────────────────
# REQUEST LOGGING MIDDLEWARE
# ────────────────────────────────────────

def log_request_info():
    """Log detailed request information for security monitoring."""
    from security import log_security_event

    # Log suspicious patterns
    user_agent = request.user_agent.string or ''
    if len(user_agent) > 500:  # Suspiciously long user agent
        log_security_event(
            'SUSPICIOUS_REQUEST',
            f'Long user agent detected: {len(user_agent)} chars',
            level='WARNING'
        )

    # Log requests to sensitive endpoints
    sensitive_paths = ['/admin', '/auth', '/vote']
    if any(path in request.path for path in sensitive_paths):
        log_security_event(
            'SENSITIVE_ENDPOINT_ACCESS',
            f'Access to {request.path} from {request.remote_addr}',
            level='INFO'
        )


# ────────────────────────────────────────
# RATE LIMITING ENHANCEMENT
# ────────────────────────────────────────

class EnhancedRateLimiter:
    """Enhanced rate limiter with different limits for different endpoints."""

    def __init__(self):
        self.attempts = {}

    def is_rate_limited(self, key: str, max_attempts: int, window_seconds: int) -> bool:
        """Check if a key exceeds rate limit."""
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

    def get_limits_for_endpoint(self, endpoint: str) -> tuple:
        """Get rate limits based on endpoint sensitivity."""
        limits = {
            'admin_login': (5, 300),    # 5 attempts per 5 minutes
            'otp_verify': (5, 300),     # 5 attempts per 5 minutes
            'vote_cast': (3, 60),       # 3 votes per minute (suspicious)
            'registry_upload': (2, 3600), # 2 uploads per hour
            'default': (100, 60),       # 100 requests per minute
        }

        for key, limit in limits.items():
            if key in endpoint:
                return limit

        return limits['default']


enhanced_rate_limiter = EnhancedRateLimiter()


def enhanced_rate_limit():
    """Dynamic rate limiting based on endpoint."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            endpoint = request.endpoint or 'unknown'
            max_attempts, window = enhanced_rate_limiter.get_limits_for_endpoint(endpoint)

            client_ip = request.remote_addr
            key = f"{client_ip}:{endpoint}"

            if enhanced_rate_limiter.is_rate_limited(key, max_attempts, window):
                from security import log_security_event
                log_security_event(
                    'RATE_LIMIT_EXCEEDED',
                    f'Rate limit exceeded for {endpoint} from {client_ip}',
                    level='WARNING'
                )
                abort(429)  # Too Many Requests

            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ────────────────────────────────────────
# INPUT SANITIZATION
# ────────────────────────────────────────

def sanitize_html_input(text: str) -> str:
    """Sanitize HTML input to prevent XSS."""
    if not text:
        return text

    # Remove potentially dangerous HTML
    import re
    # Remove script tags and their contents
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    # Remove other dangerous tags
    dangerous_tags = ['iframe', 'object', 'embed', 'form', 'input', 'button']
    for tag in dangerous_tags:
        text = re.sub(f'<{tag}[^>]*>.*?</{tag}>', '', text, flags=re.IGNORECASE | re.DOTALL)

    # Remove event handlers
    text = re.sub(r'\bon\w+\s*=', '', text, flags=re.IGNORECASE)

    return text.strip()


def validate_file_upload(file, allowed_extensions=None, max_size=5*1024*1024):
    """Validate file uploads for security."""
    if allowed_extensions is None:
        allowed_extensions = ['.csv', '.txt']

    if not file or not file.filename:
        return False, "No file provided"

    # Check file extension
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        return False, f"File type not allowed. Allowed: {', '.join(allowed_extensions)}"

    # Check file size
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Reset to beginning

    if size > max_size:
        return False, f"File too large. Maximum size: {max_size/1024/1024:.1f}MB"

    # Check for suspicious content
    content = file.read(1024).decode('utf-8', errors='ignore').lower()
    suspicious_patterns = ['<script', 'javascript:', 'vbscript:', 'onload=', 'onerror=']
    if any(pattern in content for pattern in suspicious_patterns):
        return False, "File contains suspicious content"

    file.seek(0)  # Reset for actual processing
    return True, "File is valid"


# ────────────────────────────────────────
# SESSION SECURITY ENHANCEMENT
# ────────────────────────────────────────

def validate_session_integrity():
    """Validate session integrity and expiration."""
    if 'admin_logged_in' in session:
        # Check session age
        login_time_str = session.get('admin_login_time')
        if login_time_str:
            try:
                login_time = datetime.fromisoformat(login_time_str)
                session_age = datetime.now(timezone.utc) - login_time

                # Force logout after 8 hours
                if session_age > timedelta(hours=8):
                    session.clear()
                    return False

                # Force re-authentication after 2 hours of inactivity
                last_activity = session.get('last_activity')
                if last_activity:
                    last_activity_time = datetime.fromisoformat(last_activity)
                    inactive_time = datetime.now(timezone.utc) - last_activity_time
                    if inactive_time > timedelta(hours=2):
                        session.clear()
                        return False

                # Update last activity
                session['last_activity'] = datetime.now(timezone.utc).isoformat()

            except (ValueError, TypeError):
                session.clear()
                return False

    return True


# ────────────────────────────────────────
# INTEGRATION FUNCTIONS
# ────────────────────────────────────────

def init_security_middleware(app):
    """Initialize all security middleware for the Flask app."""

    @app.before_request
    def security_checks():
        """Run security checks before each request."""
        # Validate request size
        validate_request_size()

        # Validate content type for POST requests
        if request.method in ['POST', 'PUT', 'PATCH']:
            validate_content_type()

        # Log request info
        log_request_info()

        # Validate session integrity only for admin routes
        if request.path.startswith('/admin'):
            if not validate_session_integrity():
                from flask import flash, redirect, url_for
                flash('Session expired. Please log in again.', 'warning')
                return redirect(url_for('admin.admin_login'))

    @app.after_request
    def apply_security_headers(response):
        """Apply security headers to all responses."""
        return add_secure_headers(response)

    @app.errorhandler(429)
    def rate_limit_error(error):
        """Handle rate limiting errors."""
        return render_template('errors/429.html'), 429

    @app.errorhandler(403)
    def forbidden_error(error):
        """Handle CSRF/forbidden errors."""
        return render_template('errors/403.html'), 403

    @app.errorhandler(413)
    def payload_too_large(error):
        """Handle oversized payload errors."""
        return render_template('errors/413.html'), 413