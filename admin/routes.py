"""
Admin Module — UB eBallot
Handles: election management, student registry (persistent), results publishing.
Enhanced with comprehensive security and authentication.
"""

import csv
import io
from datetime import datetime, timezone, timedelta
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, session)
from app import db
from models import (AdminUser, UBStudentRegistry, Election,
                    Position, Candidate, EncryptedBallot, VoterToken, AuditLog)
from crypto_utils import hash_password, verify_password, verify_ballot_chain
from security import log_security_event, require_admin_session
from security_middleware import csrf_protect, enhanced_rate_limit, generate_csrf_token, sanitize_html_input

admin_bp = Blueprint('admin', __name__)


def is_strong_password(password: str) -> tuple[bool, str]:
    """Validate the admin password against a simple production-ready policy."""
    if len(password) < 12:
        return False, 'Password must be at least 12 characters long.'
    if not any(char.islower() for char in password):
        return False, 'Password must include at least one lowercase letter.'
    if not any(char.isupper() for char in password):
        return False, 'Password must include at least one uppercase letter.'
    if not any(char.isdigit() for char in password):
        return False, 'Password must include at least one number.'
    if not any(not char.isalnum() for char in password):
        return False, 'Password must include at least one special character.'
    return True, ''


# ── Enhanced Admin Authentication ────────────────────────────

@admin_bp.route('/login', methods=['GET', 'POST'])
@enhanced_rate_limit()
def admin_login():
    """Secure admin login with rate limiting and audit logging."""
    # Redirect if already logged in
    if session.get('admin_logged_in') and session.get('admin_username'):
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        username = sanitize_html_input(request.form.get('username', '').strip())
        password = request.form.get('password', '')
        next_page = request.form.get('next') or request.args.get('next')

        # Basic input validation
        if not username or not password:
            log_security_event(
                'ADMIN_LOGIN_FAILED',
                'Empty username or password',
                level='WARNING'
            )
            flash('Username and password are required.', 'danger')
            return render_template('admin/login.html', csrf_token=generate_csrf_token())

        # Find admin user
        admin = AdminUser.query.filter_by(username=username, is_active=True).first()

        if admin and verify_password(admin.password_hash, password):
            # Successful login
            session['admin_logged_in'] = True
            session['admin_username'] = username
            session['admin_login_time'] = datetime.now(timezone.utc).isoformat()
            session.permanent = True  # Use permanent session

            # Update last login time
            admin.last_login = datetime.now(timezone.utc)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

            log_security_event(
                'ADMIN_LOGIN_SUCCESS',
                f'Admin {username} logged in successfully',
                user_id=username
            )

            # Redirect to intended page or dashboard
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('admin.dashboard'))

        else:
            # Failed login
            log_security_event(
                'ADMIN_LOGIN_FAILED',
                f'Failed login attempt for username: {username}',
                level='WARNING'
            )
            flash('Invalid username or password.', 'danger')

    return render_template(
        'admin/login.html',
        next_page=request.args.get('next', '')
    )


@admin_bp.route('/logout')
def admin_logout():
    """Secure admin logout with session cleanup."""
    username = session.get('admin_username', 'unknown')

    # Clear all admin-related session data
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    session.pop('admin_login_time', None)

    log_security_event(
        'ADMIN_LOGOUT',
        f'Admin {username} logged out',
        user_id=username
    )

    flash('Successfully logged out from admin panel.', 'success')
    return redirect(url_for('admin.admin_login'))


@admin_bp.route('/database-view', methods=['GET'])
@require_admin_session()
def database_view():
    """Database overview showing anonymised voter token hashes."""
    elections = Election.query.all()
    total_elections = len(elections)
    active_elections = len([e for e in elections if e.is_active])
    total_ballots = EncryptedBallot.query.count()
    total_students = UBStudentRegistry.query.filter_by(is_active=True).count()
    total_voters = VoterToken.query.count()

    # Voter tokens joined with election title — no student ID exposed
    voter_tokens = (
        VoterToken.query
        .join(Election, VoterToken.election_id == Election.id)
        .add_columns(Election.title.label('election_title'))
        .order_by(VoterToken.voted_at.desc())
        .all()
    )

    return render_template('admin/database_view.html',
                           total_elections=total_elections,
                           active_elections=active_elections,
                           total_ballots=total_ballots,
                           total_students=total_students,
                           total_voters=total_voters,
                           voter_tokens=voter_tokens)


@admin_bp.route('/change-password', methods=['GET', 'POST'])
@require_admin_session()
@csrf_protect()
def change_password():
    """Allow admins to change their password."""
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validation
        if not current_password or not new_password:
            flash('All fields are required.', 'danger')
            return render_template('admin/change_password.html', csrf_token=generate_csrf_token())

        is_valid, validation_message = is_strong_password(new_password)
        if not is_valid:
            flash(validation_message, 'danger')
            return render_template('admin/change_password.html', csrf_token=generate_csrf_token())

        if new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
            return render_template('admin/change_password.html', csrf_token=generate_csrf_token())

        # Verify current password
        admin = AdminUser.query.filter_by(
            username=session['admin_username'],
            is_active=True
        ).first()

        if not admin or not verify_password(admin.password_hash, current_password):
            log_security_event(
                'ADMIN_PASSWORD_CHANGE_FAILED',
                f'Failed password change attempt for {session["admin_username"]}',
                level='WARNING',
                user_id=session['admin_username']
            )
            flash('Current password is incorrect.', 'danger')
            return render_template('admin/change_password.html', csrf_token=generate_csrf_token())

        if verify_password(admin.password_hash, new_password):
            flash('Please choose a new password that is different from the current one.', 'danger')
            return render_template('admin/change_password.html', csrf_token=generate_csrf_token())

        # Update password
        admin.password_hash = hash_password(new_password)
        db.session.commit()

        log_security_event(
            'ADMIN_PASSWORD_CHANGED',
            f'Password changed for admin {session["admin_username"]}',
            user_id=session['admin_username']
        )

        flash('Password changed successfully. Please log in again.', 'success')
        return redirect(url_for('admin.admin_logout'))

    return render_template('admin/change_password.html', csrf_token=generate_csrf_token())


# ── Dashboard ─────────────────────────────

@admin_bp.route('/')
@require_admin_session()
def dashboard():
    """Enhanced admin dashboard with security monitoring."""
    elections = Election.query.order_by(Election.created_at.desc()).all()
    registry_count = UBStudentRegistry.query.filter_by(is_active=True).count()
    votes_cast = VoterToken.query.count()
    active_elections = Election.query.filter_by(is_active=True).count()

    # Recent audit events (last 10)
    recent_audit = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(10).all()

    # Security stats
    failed_logins = AuditLog.query.filter_by(event_type='ADMIN_LOGIN_FAILED').count()
    total_admins = AdminUser.query.filter_by(is_active=True).count()

    return render_template('admin/dashboard.html',
                           elections=elections,
                           registry_count=registry_count,
                           votes_cast=votes_cast,
                           active_elections=active_elections,
                           recent_audit=recent_audit,
                           failed_logins=failed_logins,
                           total_admins=total_admins)


# ── Registry management ───────────────────

@admin_bp.route('/registry', methods=['GET', 'POST'])
@require_admin_session()
def manage_registry():
    """
    Manage the persistent UB student registry.
    CSV import is a one-time (or periodic) setup operation — the data lives
    in the database and does not need to be re-uploaded each election.
    Individual records can also be added or deactivated here.
    """
    if request.method == 'POST':
        action = request.form.get('action', 'import_csv')

        if action == 'import_csv':
            file = request.files.get('registry_file')
            if not file or not file.filename.endswith('.csv'):
                log_security_event(
                    'REGISTRY_IMPORT_FAILED',
                    'Invalid file upload attempt',
                    level='WARNING',
                    user_id=session['admin_username']
                )
                flash('Please upload a valid CSV file.', 'danger')
                return redirect(url_for('admin.manage_registry'))

            content = file.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(content))

            added = updated = skipped = 0
            for row in reader:
                student_number = row.get('student_number', '').strip().upper()
                full_name = row.get('full_name', '').strip()
                if not student_number or not full_name:
                    skipped += 1
                    continue

                existing = UBStudentRegistry.query.filter_by(
                    student_number=student_number
                ).first()
                ub_email = row.get('ub_email', '').strip().lower() or None
                programme = row.get('programme', '').strip() or None
                year = int(row.get('year_of_study', 0) or 0) or None

                if existing:
                    existing.full_name = full_name
                    existing.ub_email = ub_email
                    existing.programme = programme
                    existing.year_of_study = year
                    existing.is_active = True
                    updated += 1
                else:
                    db.session.add(UBStudentRegistry(
                        student_number=student_number,
                        full_name=full_name,
                        ub_email=ub_email,
                        programme=programme,
                        year_of_study=year,
                    ))
                    added += 1

            db.session.commit()
            log_security_event(
                'REGISTRY_IMPORTED',
                f'Imported registry: {added} added, {updated} updated, {skipped} skipped',
                user_id=session['admin_username']
            )
            flash(
                f'Registry updated: {added} added, {updated} updated, {skipped} skipped.',
                'success'
            )
            return redirect(url_for('admin.manage_registry'))

        elif action == 'add_entry':
            student_number = request.form.get('student_number', '').strip().upper()
            full_name = request.form.get('full_name', '').strip()
            if not student_number or not full_name:
                flash('Student number and full name are required.', 'danger')
                return redirect(url_for('admin.manage_registry'))

            ub_email = request.form.get('ub_email', '').strip().lower() or None
            programme = request.form.get('programme', '').strip() or None

            existing = UBStudentRegistry.query.filter_by(student_number=student_number).first()
            if existing:
                existing.full_name = full_name
                existing.ub_email = ub_email
                existing.programme = programme
                existing.is_active = True
                flash(f'{student_number} already existed — record updated and activated.', 'info')
            else:
                db.session.add(UBStudentRegistry(
                    student_number=student_number,
                    full_name=full_name,
                    ub_email=ub_email,
                    programme=programme,
                ))
                flash(f'Added {student_number} to registry.', 'success')
            db.session.commit()
            return redirect(url_for('admin.manage_registry'))

    # GET request - show registry
    page = request.args.get('page', 1, type=int)
    per_page = 50
    students = UBStudentRegistry.query.paginate(page=page, per_page=per_page)
    return render_template('admin/registry.html', students=students)


@admin_bp.route('/registry/<int:entry_id>/deactivate', methods=['POST'])
@require_admin_session()
def deactivate_registry_entry(entry_id):
    entry = UBStudentRegistry.query.get_or_404(entry_id)
    entry.is_active = False
    db.session.commit()
    flash(f'{entry.student_number} deactivated — no longer eligible to vote.', 'info')
    return redirect(url_for('admin.manage_registry'))


# ── Election management ───────────────────

@admin_bp.route('/elections/new', methods=['GET', 'POST'])
@require_admin_session()
def new_election():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        start_str = request.form.get('start_time', '')
        end_str = request.form.get('end_time', '')

        try:
            start_time = datetime.fromisoformat(start_str)
            end_time = datetime.fromisoformat(end_str)
        except ValueError:
            flash('Invalid date/time format.', 'danger')
            return render_template('admin/new_election.html')

        if end_time <= start_time:
            flash('End time must be after start time.', 'danger')
            return render_template('admin/new_election.html')

        election = Election(title=title, description=description,
                            start_time=start_time, end_time=end_time)
        db.session.add(election)
        db.session.commit()
        flash(f'Election "{title}" created.', 'success')
        return redirect(url_for('admin.manage_election', election_id=election.id))

    return render_template('admin/new_election.html')


@admin_bp.route('/elections/<int:election_id>', methods=['GET', 'POST'])
@require_admin_session()
def manage_election(election_id):
    election = Election.query.get_or_404(election_id)
    positions = Position.query.filter_by(election_id=election_id).all()
    ballot_count = EncryptedBallot.query.filter_by(election_id=election_id).count()
    chain_ok = verify_ballot_chain(election_id) if ballot_count > 0 else None
    return render_template('admin/manage_election.html',
                           election=election,
                           positions=positions,
                           ballot_count=ballot_count,
                           chain_ok=chain_ok)


@admin_bp.route('/elections/<int:election_id>/delete', methods=['POST'])
@require_admin_session()
def delete_election(election_id):
    election = Election.query.get_or_404(election_id)
    if election.is_active:
        flash('Deactivate the election before deleting it.', 'danger')
        return redirect(url_for('admin.manage_election', election_id=election_id))
    db.session.delete(election)
    db.session.commit()
    flash(f'Election "{election.title}" deleted.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/elections/<int:election_id>/toggle', methods=['POST'])
@require_admin_session()
def toggle_election(election_id):
    election = Election.query.get_or_404(election_id)
    election.is_active = not election.is_active
    db.session.commit()
    status = 'activated' if election.is_active else 'deactivated'
    flash(f'Election "{election.title}" {status}.', 'success')
    return redirect(url_for('admin.manage_election', election_id=election_id))


@admin_bp.route('/elections/<int:election_id>/publish', methods=['POST'])
@require_admin_session()
def publish_results(election_id):
    election = Election.query.get_or_404(election_id)
    election.results_published = True
    db.session.commit()
    flash('Results published.', 'success')
    return redirect(url_for('admin.manage_election', election_id=election_id))


@admin_bp.route('/elections/<int:election_id>/unpublish', methods=['POST'])
@require_admin_session()
def unpublish_results(election_id):
    election = Election.query.get_or_404(election_id)
    election.results_published = False
    db.session.commit()
    flash(f'Results for "{election.title}" have been unpublished.', 'warning')
    return redirect(url_for('admin.manage_election', election_id=election_id))


# ── Position & Candidate management ──────

@admin_bp.route('/elections/<int:election_id>/positions/add', methods=['POST'])
@require_admin_session()
def add_position(election_id):
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    if title:
        db.session.add(Position(election_id=election_id, title=title,
                                description=description))
        db.session.commit()
        flash(f'Position "{title}" added.', 'success')
    return redirect(url_for('admin.manage_election', election_id=election_id))


@admin_bp.route('/positions/<int:position_id>/candidates/add', methods=['POST'])
@require_admin_session()
def add_candidate(position_id):
    position = Position.query.get_or_404(position_id)
    full_name = request.form.get('full_name', '').strip()
    student_number = request.form.get('student_number', '').strip().upper()
    party = request.form.get('party', '').strip() or None
    manifesto = request.form.get('manifesto', '').strip()

    if full_name and student_number:
        db.session.add(Candidate(position_id=position_id, full_name=full_name,
                                 student_number=student_number, party=party,
                                 manifesto=manifesto))
        db.session.commit()
        flash(f'Candidate "{full_name}" added.', 'success')
    return redirect(url_for('admin.manage_election', election_id=position.election_id))


@admin_bp.route('/positions/<int:position_id>/edit', methods=['GET', 'POST'])
@require_admin_session()
def edit_position(position_id):
    position = Position.query.get_or_404(position_id)
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        if title:
            position.title = title
            position.description = description
            db.session.commit()
            flash(f'Position updated to "{title}".', 'success')
        return redirect(url_for('admin.manage_election', election_id=position.election_id))
    return render_template('admin/edit_position.html', position=position)


@admin_bp.route('/positions/<int:position_id>/delete', methods=['POST'])
@require_admin_session()
def delete_position(position_id):
    position = Position.query.get_or_404(position_id)
    election_id = position.election_id
    db.session.delete(position)
    db.session.commit()
    flash(f'Position "{position.title}" and all its candidates deleted.', 'success')
    return redirect(url_for('admin.manage_election', election_id=election_id))


@admin_bp.route('/candidates/<int:candidate_id>/edit', methods=['GET', 'POST'])
@require_admin_session()
def edit_candidate(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    if request.method == 'POST':
        candidate.full_name = request.form.get('full_name', '').strip()
        candidate.student_number = request.form.get('student_number', '').strip().upper()
        candidate.party = request.form.get('party', '').strip() or None
        candidate.manifesto = request.form.get('manifesto', '').strip() or None
        db.session.commit()
        flash(f'Candidate "{candidate.full_name}" updated.', 'success')
        return redirect(url_for('admin.manage_election',
                                election_id=candidate.position.election_id))
    return render_template('admin/edit_candidate.html', candidate=candidate)


@admin_bp.route('/candidates/<int:candidate_id>/delete', methods=['POST'])
@require_admin_session()
def delete_candidate(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    election_id = candidate.position.election_id
    name = candidate.full_name
    db.session.delete(candidate)
    db.session.commit()
    flash(f'Candidate "{name}" removed.', 'success')
    return redirect(url_for('admin.manage_election', election_id=election_id))
