"""
Database Administration Tool for UB eBallot
Allows inspection of database contents during development/demo.
"""

import os
import sqlite3
import json
from datetime import datetime, timezone
from flask import Flask
from app import db, create_app
from models import (
    UBStudentRegistry, OTPCode, Election, Position, Candidate,
    VoterToken, EncryptedBallot, ReceiptBallot, AuditLog, AdminUser
)
from crypto_utils import decrypt_ballot


def init_db_inspector():
    """Initialize database inspector in Flask context."""
    app = create_app()
    return app


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def count_records(model_class, **filters):
    """Count records in a model."""
    query = model_class.query
    for key, value in filters.items():
        if hasattr(model_class, key):
            query = query.filter(getattr(model_class, key) == value)
    return query.count()


# ────────────────────────────────────────
# DATABASE INSPECTION FUNCTIONS
# ────────────────────────────────────────

def inspect_student_registry():
    """Show student registry status."""
    print_section("STUDENT REGISTRY")
    
    total = count_records(UBStudentRegistry)
    active = count_records(UBStudentRegistry, is_active=True)
    
    print(f"Total students: {total}")
    print(f"Active students: {active}")
    print(f"Inactive students: {total - active}")
    
    if total > 0:
        print("\nSample records (first 5):")
        students = UBStudentRegistry.query.limit(5).all()
        for s in students:
            print(f"  {s.student_number:15} | {s.full_name:25} | {s.ub_email or 'N/A'}")


def inspect_elections():
    """Show election details."""
    print_section("ELECTIONS")
    
    elections = Election.query.all()
    
    if not elections:
        print("No elections found.")
        return
    
    for election in elections:
        print(f"\nElection ID {election.id}: {election.title}")
        print(f"  Status: {'ACTIVE' if election.is_active else 'INACTIVE'}")
        print(f"  Open: {election.is_open}")
        print(f"  Results published: {'Yes' if election.results_published else 'No'}")
        print(f"  Start: {election.start_time}")
        print(f"  End: {election.end_time}")
        
        positions = Position.query.filter_by(election_id=election.id).count()
        ballots = EncryptedBallot.query.filter_by(election_id=election.id).count()
        votes = VoterToken.query.filter_by(election_id=election.id).count()
        
        print(f"  Positions: {positions}")
        print(f"  Total votes cast: {votes}")
        print(f"  Encrypted ballots stored: {ballots}")


def inspect_positions_and_candidates():
    """Show positions and candidates."""
    print_section("POSITIONS & CANDIDATES")
    
    elections = Election.query.all()
    
    if not elections:
        print("No elections found.")
        return
    
    for election in elections:
        print(f"\nElection: {election.title}")
        positions = Position.query.filter_by(election_id=election.id).all()
        
        if not positions:
            print("  (no positions)")
            continue
        
        for position in positions:
            print(f"  Position: {position.title}")
            candidates = Candidate.query.filter_by(position_id=position.id).all()
            for candidate in candidates:
                print(f"    - {candidate.full_name:30} ({candidate.student_number})" + 
                      (f" [{candidate.party}]" if candidate.party else ""))


def inspect_voting_status():
    """Show voting statistics."""
    print_section("VOTING STATUS & STATISTICS")
    
    elections = Election.query.all()
    
    if not elections:
        print("No elections found.")
        return
    
    for election in elections:
        print(f"\nElection: {election.title} (ID: {election.id})")
        
        votes = VoterToken.query.filter_by(election_id=election.id).count()
        ballots = EncryptedBallot.query.filter_by(election_id=election.id).count()
        
        print(f"  Votes cast: {votes}")
        print(f"  Ballots stored: {ballots}")
        print(f"  Data integrity: {'✓ MATCH' if votes == ballots else '✗ MISMATCH'}")
        
        if votes > 0:
            earliest = db.session.query(VoterToken).filter_by(
                election_id=election.id
            ).order_by(VoterToken.voted_at.asc()).first()
            latest = db.session.query(VoterToken).filter_by(
                election_id=election.id
            ).order_by(VoterToken.voted_at.desc()).first()
            
            print(f"  First vote: {earliest.voted_at}")
            print(f"  Last vote: {latest.voted_at}")


def inspect_ballot_sample(election_id: int, sample_size: int = 3):
    """
    Show sample of encrypted + decrypted ballots.
    WARNING: Only for development/demo! Never do this in production.
    """
    print_section(f"BALLOT SAMPLE (Election {election_id})")
    
    ballots = (EncryptedBallot.query
               .filter_by(election_id=election_id)
               .order_by(EncryptedBallot.id.desc())
               .limit(sample_size)
               .all())
    
    if not ballots:
        print("No ballots found for this election.")
        return
    
    for ballot in ballots:
        print(f"\nBallot ID {ballot.id}:")
        print(f"  Timestamp: {ballot.created_at}")
        print(f"  Receipt hash: {ballot.receipt_hash[:16]}...")
        print(f"  Chain hash: {ballot.chain_hash[:16]}...")
        
        try:
            decrypted = decrypt_ballot(ballot.encrypted_data)
            print(f"  DECRYPTED BALLOT:")
            print(f"    Choices: {decrypted.get('choices', {})}")
            print(f"    Voted at: {decrypted.get('timestamp', 'N/A')}")
        except Exception as e:
            print(f"  ERROR decrypting: {e}")


def inspect_audit_log():
    """Show audit log entries."""
    print_section("AUDIT LOG (Last 20 entries)")
    
    logs = (AuditLog.query
            .order_by(AuditLog.timestamp.desc())
            .limit(20)
            .all())
    
    if not logs:
        print("No audit logs found.")
        return
    
    for log in logs:
        print(f"\n{log.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Event: {log.event_type}")
        print(f"  Description: {log.description}")
        print(f"  IP: {log.ip_address or 'N/A'}")
        if log.user_id:
            print(f"  User: {log.user_id}")


def inspect_otp_attempts():
    """Show recent OTP generation/verification attempts."""
    print_section("OTP ATTEMPTS (Last 20)")
    
    otps = (OTPCode.query
            .order_by(OTPCode.created_at.desc())
            .limit(20)
            .all())
    
    if not otps:
        print("No OTP records found.")
        return
    
    for otp in otps:
        status = "USED" if otp.is_used else ("EXPIRED" if otp.is_expired else "VALID")
        print(f"\n  Student: {otp.student_number}")
        print(f"    Election: {otp.election_id}")
        print(f"    Status: {status}")
        print(f"    Attempts: {otp.attempts}/5")
        print(f"    Created: {otp.created_at}")
        print(f"    Expires: {otp.expires_at}")


def inspect_admin_users():
    """Show admin users (password hashes not shown for security)."""
    print_section("ADMIN USERS")
    
    admins = AdminUser.query.all()
    
    if not admins:
        print("No admin users found.")
        return
    
    for admin in admins:
        print(f"\n  Username: {admin.username}")
        print(f"    Created: {admin.created_at}")
        print(f"    Last login: {admin.last_login or 'Never'}")
        print(f"    Active: {admin.is_active}")


def full_database_inspection():
    """Run complete database inspection."""
    app = init_db_inspector()
    
    with app.app_context():
        print("\n" + "#"*70)
        print("# UB EBALLOT - FULL DATABASE INSPECTION")
        print("#"*70)
        
        inspect_student_registry()
        inspect_elections()
        inspect_positions_and_candidates()
        inspect_voting_status()
        inspect_otp_attempts()
        inspect_admin_users()
        inspect_audit_log()
        
        print("\n" + "#"*70)
        print("# END OF INSPECTION")
        print("#"*70 + "\n")


def quick_database_summary():
    """Print a quick summary."""
    app = init_db_inspector()
    
    with app.app_context():
        print("\n" + "="*70)
        print("  QUICK DATABASE SUMMARY")
        print("="*70)
        
        print(f"\nStudents registered: {count_records(UBStudentRegistry)}")
        print(f"Elections created: {count_records(Election)}")
        print(f"Total votes cast: {count_records(VoterToken)}")
        print(f"Total ballots stored: {count_records(EncryptedBallot)}")
        print(f"Audit log entries: {count_records(AuditLog)}")
        print(f"Admin users: {count_records(AdminUser)}")
        
        print("\n" + "="*70 + "\n")


# ────────────────────────────────────────
# CLI INTERFACE
# ────────────────────────────────────────

def print_menu():
    """Print interactive menu."""
    print("\n" + "="*70)
    print("  UB EBALLOT DATABASE INSPECTOR")
    print("="*70)
    print("\n1. Quick summary")
    print("2. View student registry")
    print("3. View elections & positions")
    print("4. View voting statistics")
    print("5. View OTP attempts")
    print("6. View audit log")
    print("7. View sample ballots (DEMO ONLY!)")
    print("8. View admin users")
    print("9. Full inspection report")
    print("0. Exit")
    print("\n" + "="*70)


def interactive_inspector():
    """Interactive database inspector."""
    app = init_db_inspector()
    
    with app.app_context():
        while True:
            print_menu()
            choice = input("Enter choice (0-9): ").strip()
            
            if choice == '0':
                print("Exiting...\n")
                break
            elif choice == '1':
                quick_database_summary()
            elif choice == '2':
                inspect_student_registry()
            elif choice == '3':
                inspect_positions_and_candidates()
            elif choice == '4':
                inspect_voting_status()
            elif choice == '5':
                inspect_otp_attempts()
            elif choice == '6':
                inspect_audit_log()
            elif choice == '7':
                try:
                    election_id = int(input("Enter election ID: "))
                    inspect_ballot_sample(election_id)
                except ValueError:
                    print("Invalid election ID.")
            elif choice == '8':
                inspect_admin_users()
            elif choice == '9':
                full_database_inspection()
            else:
                print("Invalid choice.")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--full':
        full_database_inspection()
    elif len(sys.argv) > 1 and sys.argv[1] == '--quick':
        quick_database_summary()
    else:
        interactive_inspector()
