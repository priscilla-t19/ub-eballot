# UB eBallot — Alpha Version
## Online Anonymous Voting System for University of Botswana SRC Elections

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Application
```bash
python run.py
```

Visit: http://localhost:5000

---

## Default Admin Credentials
- URL: http://localhost:5000/admin/login
- Username: `admin`
- Password: `admin1234`
⚠️ Change these before any real deployment!

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                 AUTHENTICATION MODULE                │
│  - Student pre-registration                          │
│  - Eligibility check vs UB Registry                  │
│  - UB email verification                             │
│  - Issues one-time anonymous voting pass             │
│  - NEVER touches ballot data                         │
└────────────────────┬────────────────────────────────┘
                     │ Anonymous Pass Only
                     ▼
┌─────────────────────────────────────────────────────┐
│                   VOTING MODULE                      │
│  - Accepts anonymous pass (no identity)              │
│  - Encrypts ballot with Fernet (AES-128)             │
│  - Stores in tamper-evident hash chain               │
│  - Issues receipt code                               │
│  - NEVER knows who voted                             │
└────────────────────┬────────────────────────────────┘
                     │ Receipt Hash
                     ▼
┌─────────────────────────────────────────────────────┐
│               VERIFICATION MODULE                   │
│  - Voter enters receipt code                         │
│  - Confirms ballot inclusion                         │
│  - Shows choices WITHOUT revealing voter identity    │
│  - Verifies chain integrity                          │
└─────────────────────────────────────────────────────┘
```

---

## Key Security Features

| Feature | Implementation |
|---------|---------------|
| Password Hashing | Argon2 |
| Ballot Encryption | Fernet (AES-128-CBC + HMAC) |
| Tamper Detection | SHA-256 hash chain |
| Anonymity | Architectural separation: auth ≠ voting |
| Double-vote prevention | Student `has_voted` flag + pass invalidation |
| Receipt verification | SHA-256 hashed receipt codes |

---

## Setup Workflow

### Step 1: Upload Student Registry (Admin)
1. Go to Admin → Registry
2. Upload `sample_registry.csv` or official UB CSV
3. Students can now register

### Step 2: Create an Election (Admin)
1. Go to Admin → New Election
2. Set title, start/end times
3. Add Positions (e.g., SRC President)
4. Add Candidates per position
5. Activate the election

### Step 3: Student Registration (Voter)
1. Visit /auth/register
2. Enter student number + UB email + password
3. Verify email (link shown in dev mode)

### Step 4: Voting
1. Login at /auth/login
2. Dashboard shows active elections
3. Click "Vote Now" → anonymous pass issued
4. Cast ballot in sandboxed voting module
5. Receive receipt code

### Step 5: Verification
1. Visit /verify/
2. Enter receipt code
3. Confirm vote was counted

---

## Project Structure

```
ub_eballot/
├── run.py              # Entry point
├── app.py              # Flask app factory
├── config.py           # Configuration
├── models.py           # Database models
├── crypto_utils.py     # Cryptographic utilities
├── email_utils.py      # Email sending
├── main_routes.py      # Home & dashboard routes
├── auth/               # Authentication module
│   └── routes.py
├── voting/             # Voting module (sandboxed)
│   └── routes.py
├── verification/       # Vote verification
│   └── routes.py
├── admin/              # Admin panel
│   ├── routes.py
│   └── seed.py
├── templates/          # Jinja2 HTML templates
├── static/             # CSS, JS, PWA assets
│   ├── css/main.css
│   ├── js/main.js
│   ├── js/sw.js        # Service Worker
│   └── manifest.json   # PWA manifest
└── requirements.txt
```

---

## Alpha Version Notes
- SQLite database (upgrade to PostgreSQL for production)
- Email verification shows link in flash messages when SMTP not configured
- Change SECRET_KEY and admin password before any live deployment
