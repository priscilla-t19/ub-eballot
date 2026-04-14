# UB eBallot - Security Hardening & Database Inspection Guide

## Part 1: Using the Database Inspection Tools

### Quick Start - View Database Content

#### Option 1: Interactive Inspector (Recommended for beginners)
```bash
python database_admin.py
```
This opens an interactive menu where you can:
- View quick database summary
- Browse student registry
- Check election details & positions
- Monitor voting statistics
- View OTP attempt logs
- Check audit trails
- Sample encrypted ballots (decrypt them to see actual votes - DEMO ONLY!)

#### Option 2: Flask CLI Commands
```bash
# Quick summary
flask db-summary

# Interactive inspector
flask db-inspect

# Full inspection report (long output)
flask db-full

# Specific views
flask db-registry      # Show student registry
flask db-elections     # Show elections & positions
flask db-voting        # Show voting statistics
```

#### Option 3: Direct Python Script
```bash
# Full inspection
python database_admin.py --full

# Quick summary
python database_admin.py --quick
```

---

## Part 2: Security Hardening Features Implemented

### ✅ What's Been Added

#### 1. **Rate Limiting** (`security.py`)
Prevents brute force attacks on authentication endpoints:
- OTP verification: max 5 attempts per 5 minutes
- Login attempts: configurable rate limits
- Tracked by IP address + endpoint

```python
from security import rate_limit

@auth_bp.route('/verify-otp/<int:election_id>', methods=['POST'])
@rate_limit(max_attempts=5, window_seconds=300)
def verify_otp(election_id):
    # Your code here
```

#### 2. **Audit Logging** (`security.py`)
Records all security events to database:
- Vote casting
- OTP generation/verification
- Duplicate vote attempts
- Admin logins
- Registry uploads
- Rate limit violations

```python
from security import log_security_event

log_security_event(
    event_type='VOTE_CAST',
    description='Ballot encrypted and submitted',
    user_id=student_number
)
```

#### 3. **Input Validation & Sanitization** (`security.py`)
Validates all critical inputs:
- Student IDs (alphanumeric, 3-20 chars)
- Email addresses (regex validation)
- OTP codes (6 digits only)
- CSV uploads (prevent path traversal)

```python
from security import validate_student_number, validate_email, validate_otp_code

if not validate_student_number(student_id):
    flash('Invalid student number format', 'danger')
```

#### 4. **Session Security** (`security.py`)
Hardened session configuration:
- HTTPS-only cookies (`Secure` flag)
- JavaScript-proof cookies (`HttpOnly` flag)
- CSRF protection via Same-Site policy
- 30-minute session timeout
- Non-default cookie name

```python
configure_session_security(app)  # Call in create_app()
# Results in:
# - SESSION_COOKIE_SECURE = True
# - SESSION_COOKIE_HTTPONLY = True
# - SESSION_COOKIE_SAMESITE = 'Strict'
# - 30-minute expiration
```

#### 5. **Security Headers** (`security.py`)
Automatic HTML security headers on all responses:
```
X-Content-Type-Options: nosniff          # Prevent MIME type sniffing
X-Frame-Options: DENY                    # Prevent clickjacking
X-XSS-Protection: 1; mode=block          # Enable browser XSS filter
Strict-Transport-Security: ...           # Force HTTPS
Content-Security-Policy: ...             # Control resource loading
```

#### 6. **Ballot Chain Verification** (`security.py`)
Verify ballot tamper-detection chain:
```python
from security import verify_ballot_chain_integrity

result = verify_ballot_chain_integrity(election_id=1)
# Returns: {
#   'is_valid': True,
#   'issues': [],
#   'ballots_verified': 42,
#   'timestamp': datetime.now()
# }
```

#### 7. **Audit Log Viewing** (`database_admin.py`)
View all security events:
```bash
flask db-summary    # Shows event counts
flask db-inspect    # Interactive audit log viewer
```

#### 8. **Admin Authentication Hardening** (`security.py`)
Protects admin routes:
```python
from security import require_admin_session

@admin_bp.route('/manage-election')
@require_admin_session()
def manage_election():
    # Only accessible if admin_authenticated in session
```

---

## Part 3: Security Configuration (.env File)

Create a `.env` file in the project root with:

```bash
# Flask Config
DEBUG=False
TESTING=False
SECRET_KEY=your-random-secret-key-here-min-32-chars
PREFERRED_URL_SCHEME=https

# Database
DATABASE_URL=postgresql://user:password@localhost/ub_eballot

# Cryptography (CRITICAL - never change after voting begins!)
BALLOT_ENCRYPTION_KEY=your-base64-encoded-32-byte-key
VOTER_PEPPER=your-random-pepper-string-never-change

# Session Security
SESSION_COOKIE_SECURE=True

# Rate Limiting
OTP_EXPIRY=600
RATELIMIT_OTP_ATTEMPTS=5
RATELIMIT_OTP_WINDOW=300

# Email (Gmail example)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-specific-password
```

### Generating Secure Keys

**In Python:**
```python
import secrets
import base64

# Generate random SECRET_KEY (32 bytes = 256 bits)
SECRET_KEY = secrets.token_urlsafe(32)

# Generate BALLOT_ENCRYPTION_KEY
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(key.decode())  # Use this value in .env

# Generate VOTER_PEPPER
VOTER_PEPPER = secrets.token_urlsafe(32)
```

**In Terminal (Linux/Mac):**
```bash
openssl rand -base64 32  # For SECRET_KEY or VOTER_PEPPER
```

---

## Part 4: Database Models for Audit Trail

The system now includes:

### `AuditLog` Table
```sql
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,          -- VOTE_CAST, OTP_SENT, etc
    description TEXT NOT NULL,
    user_id VARCHAR(100),                      -- Student number or admin username
    ip_address VARCHAR(45),                    -- IPv4 or IPv6
    user_agent VARCHAR(500),                   -- Browser info
    timestamp DATETIME NOT NULL                -- When event occurred
);
```

### `ReceiptBallot` Table
```sql
CREATE TABLE receipt_ballots (
    id INTEGER PRIMARY KEY,
    ballot_id INTEGER NOT NULL,                -- Link to encrypted ballot
    receipt_hash VARCHAR(256) NOT NULL,        -- SHA-256 of receipt code
    verified_at DATETIME                       -- When voter verified receipt
);
```

### Updated `AdminUser` Table
```sql
CREATE TABLE admin_users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME NOT NULL,
    last_login DATETIME                        -- Track logins
);
```

---

## Part 5: Deployment Security Checklist

Run this command to display the full checklist:
```bash
flask security-checklist
```

**OR view it directly:**
```python
from security import print_deployment_checklist
print_deployment_checklist()
```

Key categories to verify:

### Environment Variables ⚙️
- [ ] Change SECRET_KEY to random 32+ char string
- [ ] Change BALLOT_ENCRYPTION_KEY to secure value
- [ ] Change VOTER_PEPPER (CRITICAL - never change after voting!)
- [ ] Change default admin credentials
- [ ] Configure HTTPS/SSL certificates

### Flask Configuration 🔧
- [ ] Set DEBUG=False
- [ ] Set TESTING=False
- [ ] Verify session cookies are Secure + HttpOnly
- [ ] Enable CSRF protection (already enabled)

### Database 🗄️
- [ ] Use PostgreSQL or MySQL (NOT SQLite in production)
- [ ] Set strong database password
- [ ] Enable database backups (daily minimum)
- [ ] Restrict database access to app server only
- [ ] Enable encryption at rest (if supported)

### Infrastructure 🏗️
- [ ] Use HTTPS everywhere (TLS 1.2+)
- [ ] Run behind reverse proxy (nginx/Apache)
- [ ] Enable firewall rules
- [ ] Configure logging & monitoring
- [ ] Set up email alerts for security events

### Application Testing ✅
- [ ] Test rate limiting (try 6+ wrong OTPs)
- [ ] Verify ballot encryption works
- [ ] Test chain integrity verification
- [ ] Verify OTP expiration
- [ ] Test double-vote prevention
- [ ] Audit all admin endpoints
- [ ] Run security penetration test

---

## Part 6: Using the Database Inspector During Demos

### Show database state to stakeholders:

```bash
# Terminal 1: Run the Flask app
python run.py

# Terminal 2: Open database inspector while app is running
flask db-inspect

# Shows:
# - Number of registered students
# - Elections created
# - Votes cast (should match ballot count)
# - Recent audit logs
# - OTP attempts
# - Admin users
```

### Sample Encrypted Ballots (DEMO ONLY!)

In `db-inspect`, select option 7 to decrypt and view sample ballots:
```
Enter election ID: 1
Enter sample size: 3

Ballot ID 42:
  Timestamp: 2026-04-12 14:30:45 UTC
  Receipt hash: abc123def456...
  DECRYPTED BALLOT:
    Choices: {'1': 5, '2': 8}    # Position 1 → Candidate 5, Position 2 → Candidate 8
    Voted at: 2026-04-12T14:30:45.123456+00:00
```

⚠️ **SECURITY WARNING**: Never decrypt ballots in production! This feature is for demo/development only.

---

## Part 7: Integration with Routes

### In `auth/routes.py`:
```python
from security import rate_limit, log_security_event, validate_student_number

@auth_bp.route('/verify-otp/<int:election_id>', methods=['POST'])
@rate_limit(max_attempts=5, window_seconds=300)  # Add this decorator
def verify_otp(election_id):
    # ... existing code ...
    
    # Log successful verification
    log_security_event(
        'OTP_VERIFIED',
        f'Student {student_number} verified OTP for election {election_id}',
        user_id=student_number
    )
```

### In `voting/routes.py`:
```python
from security import log_security_event

@voting_bp.route('/cast/<int:election_id>', methods=['POST'])
def cast_vote(election_id):
    # ... existing code ...
    
    # After ballot is saved
    log_security_event(
        'VOTE_CAST',
        f'Encrypted ballot #{ballot.id} stored for election {election_id}',
        user_id=session.get('voting_election_id')
    )
```

### In `admin/routes.py`:
```python
from security import require_admin_session, log_security_event

@admin_bp.route('/new-election', methods=['POST'])
@require_admin_session()
def create_election():
    # ... existing code ...
    
    log_security_event(
        'ELECTION_CREATED',
        f'Admin created election: {election.title}',
        user_id=admin_username
    )
```

---

## Part 8: Testing Security Features

### Test Rate Limiting:
```bash
# Try 6 wrong OTP codes in a row
# Should block on 6th attempt with 429 Too Many Requests
```

### Test Chain Integrity:
```python
from security import verify_ballot_chain_integrity

result = verify_ballot_chain_integrity(election_id=1)
assert result['is_valid'], "Chain tampered with!"
```

### Test Audit Logging:
```bash
flask db-inspect
# Select option 6 (View Audit Log)
# Should show recent events: OTP_SENT, OTP_VERIFIED, VOTE_CAST
```

---

## Part 9: Production Deployment Checklist

Before going live:

1. **Change all default values** ✅
2. **Enable HTTPS** ✅
3. **Use PostgreSQL database** ✅
4. **Run automated backups** ✅
5. **Set up monitoring/alerts** ✅
6. **Test rate limiting** ✅
7. **Test ballot chain verification** ✅
8. **Review audit logs** ✅
9. **Run security penetration test** ✅
10. **Document incident response procedures** ✅

---

## Quick Reference: Database Inspector Commands

```bash
# View all options
flask db-inspect

# Direct views
flask db-summary      # Count of everything
flask db-registry     # Student registry
flask db-elections    # Elections & candidates
flask db-voting       # Vote counts & timing
flask db-full         # Complete report (long!)

# Direct Python
python database_admin.py          # Interactive
python database_admin.py --quick  # Quick summary
python database_admin.py --full   # Full report
```

---

## Troubleshooting

### "ImportError: No module named security"
Make sure `security.py` is in the same directory as `app.py`

### "AuditLog table doesn't exist"
Run `flask db upgrade` or restart the app (it auto-creates on startup)

### Can't decrypt ballots
Ensure `BALLOT_ENCRYPTION_KEY` is correctly set in `.env`

### Rate limiter not working
Check that `@rate_limit()` decorator is added to the endpoint

---

**Last Updated:** April 12, 2026
**Status:** Ready for demo and production hardening
