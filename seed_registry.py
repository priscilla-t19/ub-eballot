"""
seed_registry.py — UB eBallot server-side registry loader

Usage:
    python seed_registry.py <path_to_csv>

Examples:
    python seed_registry.py sample_registry.csv
    python seed_registry.py /home/ubuntu/ub_students_2026.csv

CSV must have columns:
    student_number   (required)
    full_name        (required)
    ub_email         (recommended — required for OTP voting)
    programme        (optional)
    year_of_study    (optional)

Run this on the server before opening an election.
Data is written directly to the database and persists permanently.
Re-running with an updated CSV updates existing records and adds new ones.
"""

import csv
import sys
import os


def load_registry(csv_path: str):
    if not os.path.exists(csv_path):
        print(f"ERROR: File not found: {csv_path}")
        sys.exit(1)

    # Bootstrap Flask app context
    from app import create_app, db
    from models import UBStudentRegistry

    app = create_app()

    with app.app_context():
        db.create_all()

        added = updated = skipped = 0

        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            required = {'student_number', 'full_name'}
            if not required.issubset(set(reader.fieldnames or [])):
                print(f"ERROR: CSV must contain columns: {required}")
                print(f"       Found: {reader.fieldnames}")
                sys.exit(1)

            has_email_col = 'ub_email' in (reader.fieldnames or [])
            if not has_email_col:
                print("WARNING: CSV has no 'ub_email' column — students will not be able to "
                      "receive OTP codes and cannot vote until emails are added.")

            for i, row in enumerate(reader, start=2):  # start=2 accounts for header row
                student_number = row.get('student_number', '').strip().upper()
                full_name = row.get('full_name', '').strip()

                if not student_number or not full_name:
                    print(f"  Row {i}: skipped — missing student_number or full_name")
                    skipped += 1
                    continue

                ub_email = row.get('ub_email', '').strip().lower() or None
                programme = row.get('programme', '').strip() or None
                raw_year = row.get('year_of_study', '').strip()
                year_of_study = int(raw_year) if raw_year.isdigit() else None

                existing = UBStudentRegistry.query.filter_by(
                    student_number=student_number
                ).first()

                if existing:
                    existing.full_name = full_name
                    existing.ub_email = ub_email
                    existing.programme = programme
                    existing.year_of_study = year_of_study
                    existing.is_active = True
                    updated += 1
                else:
                    db.session.add(UBStudentRegistry(
                        student_number=student_number,
                        full_name=full_name,
                        ub_email=ub_email,
                        programme=programme,
                        year_of_study=year_of_study,
                    ))
                    added += 1

        db.session.commit()

        total = UBStudentRegistry.query.filter_by(is_active=True).count()
        print(f"\nRegistry import complete:")
        print(f"  {added:>6} records added")
        print(f"  {updated:>6} records updated")
        print(f"  {skipped:>6} rows skipped")
        print(f"  {total:>6} total active students in registry")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python seed_registry.py <path_to_csv>")
        print("       python seed_registry.py sample_registry.csv")
        sys.exit(1)

    load_registry(sys.argv[1])
