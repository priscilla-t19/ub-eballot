#  UB eBallot
### Secure Online Voting System for University of Botswana SRC Elections

**UB eBallot** is a functional, web-based electronic voting system developed and presented as a final-year Computer Science project at the University of Botswana.

The system was designed to modernize Student Representative Council (SRC) elections by providing a digital voting platform that prioritizes voter accessibility, ballot confidentiality, election integrity, and transparent ballot verification.

It combines full-stack web development with applied cryptographic techniques, including ballot encryption, password hashing, and tamper-evident vote records.

**Project Status:** Completed — Functional Academic Prototype  
**Project Type:** Final-Year Computer Science Project  
**Institution:** University of Botswana  
**Developer:** Priscilla Botsheleng

---

##  Problem Statement

Traditional SRC elections can involve long voting queues, manual voter verification, paper ballots, and time-consuming vote counting.

UB eBallot addresses these challenges through a digital election management and voting platform designed to:

- Improve voting accessibility for students.
- Reduce dependence on manual electoral processes.
- Authenticate eligible voters.
- Protect ballot confidentiality.
- Prevent duplicate voting.
- Support ballot inclusion verification.
- Improve the efficiency of election administration.

##  Key Features

### Student Authentication
- Student registration and login.
- UB email verification.
- Student eligibility checks against an imported registry.
- Secure password hashing using Argon2.
- One-time anonymous voting passes.

### Electronic Voting
- Digital ballots for SRC elections.
- Candidate selection by position.
- Encrypted ballot storage using Fernet.
- Separation of voter authentication and ballot processing.
- Duplicate-vote prevention through eligibility tracking and pass invalidation.

### Ballot Verification
- Unique receipt codes generated after voting.
- Receipt verification using SHA-256 hashing.
- Ballot inclusion confirmation.
- Tamper-evident ballot records using a cryptographic hash chain.

### Election Administration
- Student registry uploads.
- Election creation and scheduling.
- Candidate and position management.
- Election activation and management.
- Election results functionality.

### Responsive Interface
- Mobile-friendly web design.
- Progressive Web App (PWA) components.
- Accessible through supported desktop and mobile browsers.

##  Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, Flask |
| Frontend | HTML, CSS, JavaScript |
| Template Engine | Jinja2 |
| Database | SQLite |
| Password Hashing | Argon2 |
| Ballot Encryption | Fernet (AES-128-CBC + HMAC) |
| Cryptographic Hashing | SHA-256 |
| Mobile Support | Progressive Web App (PWA) |
| Version Control | Git & GitHub |

##  System Architecture

UB eBallot uses a modular architecture consisting of three main components.

**1. Authentication Module**

Handles student registration, email verification, voter eligibility checks, and one-time voting pass issuance.

**2. Voting Module**

Processes ballot selections separately from authentication, encrypts submitted ballots, maintains tamper-evident records, and generates voting receipts.

**3. Verification Module**

Allows voters to verify ballot inclusion and supports integrity checking through cryptographic hashes.

This separation is intended to minimize direct links between voters' identities and their submitted ballots.

##  Security Implementation

The system incorporates several security-focused mechanisms:

- **Argon2:** Secure password hashing.
- **Fernet:** Authenticated ballot encryption.
- **SHA-256:** Tamper-evident hash chaining and receipt hashing.
- **Single-Use Voting Passes:** Prevention of voting pass reuse.
- **Modular Separation:** Separation of authentication and voting responsibilities.

These features demonstrate the application of cybersecurity principles in an electronic voting system.

Further independent security assessment would be required before using the platform in official elections.

##  Installation and Setup

### Prerequisites
- Python 3
- pip
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
```

Activate the environment on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Start the Application

```bash
python run.py
```

Access the application at:

`http://localhost:5000`

### 5. Configure an Election

1. Access the administrative dashboard.
2. Upload a student registry CSV.
3. Create an election.
4. Add positions and candidates.
5. Activate the election.
6. Register and verify a test student account.
7. Cast a ballot and obtain a receipt.
8. Verify ballot inclusion using the receipt code.

##  Project Structure

```text
ub_eballot/
├── run.py
├── app.py
├── config.py
├── models.py
├── crypto_utils.py
├── email_utils.py
├── main_routes.py
├── auth/
│   └── routes.py
├── voting/
│   └── routes.py
├── verification/
│   └── routes.py
├── admin/
│   ├── routes.py
│   └── seed.py
├── templates/
├── static/
│   ├── css/
│   ├── js/
│   └── manifest.json
└── requirements.txt
```

##  Scalability and Future Deployment

UB eBallot was successfully developed and presented as a functional academic project.

The core voting functionality is implemented. However, transitioning the system into a university-wide electoral platform would require additional infrastructure and security improvements.

**1. Integration with the University of Botswana Student Registry**

Connect the platform to UB's official student information systems, subject to institutional approval, to enable automated eligibility verification and reduce dependence on manually uploaded student records.

**2. Advanced Security Hardening**

Strengthen authentication, ballot privacy, voting-pass handling, encryption key management, and resistance to potential attacks. Independent security auditing and testing would also be necessary.

**3. Database and Infrastructure Scalability**

Migrate from SQLite to PostgreSQL and introduce production-grade infrastructure capable of supporting larger numbers of concurrent voters.

These improvements represent production-readiness and scalability requirements rather than incomplete core project functionality.

##  About the Developer

**Priscilla Botsheleng**  
Computer Science Student | University of Botswana

UB eBallot was developed as my final-year Computer Science project, bringing together my experience in software engineering, backend development, database systems, and cybersecurity principles.

The project reflects my interest in building technology that addresses real-world challenges while incorporating security and data protection into system design.

##  Disclaimer

UB eBallot is an independently developed academic project and is not an official University of Botswana election system.

The completed prototype demonstrates electronic voting functionality but would require institutional integration, further security validation, and production infrastructure before official deployment.

---
