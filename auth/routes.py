"""
Authentication Module — UB eBallot

Two-step identity gate:
  Step 1 (/identify/<id>)   — student number verified against registry,
                              OTP sent to their UB institutional email.
  Step 2 (/verify-otp/<id>) — student enters the OTP; on success an anonymous
                              HMAC voter token is placed in session and the
                              student number is immediately discarded.

Privacy design:
  - The student number is held in session only between Step 1 and Step 2.
  - After OTP verification the student number is deleted from session.
  - Only the HMAC token hash crosses into the voting module — never the
    student number, name, or email.
"""

from datetime import datetime, timezone, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from app import db
from models import UBStudentRegistry, VoterToken, Election, OTPCode
from crypto_utils import compute_voter_token, generate_otp, hash_otp
from email_utils import send_otp_email

auth_bp = Blueprint('auth', __name__)

_MAX_OTP_ATTEMPTS = 5


# ── Step 1: student number entry ──────────

@auth_bp.route('/identify/<int:election_id>', methods=['GET', 'POST'])
def identify(election_id):
    election = Election.query.get_or_404(election_id)

    if not election.is_open:
        flash('This election is not currently open for voting.', 'danger')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        student_number = request.form.get('student_number', '').strip().upper()

        if not student_number:
            flash('Please enter your student number.', 'danger')
            return render_template('auth/identify.html', election=election)

        # 1. Eligibility check
        entry = UBStudentRegistry.query.filter_by(
            student_number=student_number, is_active=True
        ).first()

        if not entry:
            flash(
                'Your student number was not found in the active UB student registry.',
                'danger'
            )
            return render_template('auth/identify.html', election=election)

        if not entry.ub_email:
            flash(
                'No institutional email is on record for your student number.',
                'danger'
            )
            return render_template('auth/identify.html', election=election)

        # 2. Duplicate vote check (early — avoids sending OTP to someone who already voted)
        token_hash = compute_voter_token(student_number, election_id)
        if VoterToken.query.filter_by(token_hash=token_hash).first():
            flash('You have already voted in this election.', 'warning')
            return render_template('auth/identify.html', election=election)

        # 3. Invalidate any previous unused OTPs for this student + election
        OTPCode.query.filter_by(
            student_number=student_number,
            election_id=election_id,
            is_used=False
        ).update({'is_used': True})

        # 4. Generate and store new OTP
        raw_otp = generate_otp()
        expiry = timedelta(seconds=current_app.config.get('OTP_EXPIRY', 600))

        otp_record = OTPCode(
            student_number=student_number,
            election_id=election_id,
            code_hash=hash_otp(raw_otp),
            expires_at=datetime.now(timezone.utc) + expiry
        )
        db.session.add(otp_record)
        db.session.commit()

        # 5. Send OTP — dispatched in a background thread; returns immediately.
        #    Falls back to flashing the code directly if SMTP is not configured.
        mail_configured = bool(current_app.config.get('MAIL_USERNAME'))
        if mail_configured:
            send_otp_email(entry.ub_email, raw_otp, election.title)
            local, domain = entry.ub_email.split('@', 1)
            masked = local[0] + '***@' + domain
            flash(f'A 6-digit code has been sent to {masked}. It expires in 10 minutes.', 'success')
        else:
            flash(
                f'[DEMO — email not configured] Your voting code is: {raw_otp}',
                'info'
            )

        # 6. Store student number in session temporarily (Step 2 needs it)
        #    It is deleted the moment OTP is verified.
        session['otp_student_number'] = student_number
        session['otp_election_id'] = election_id

        return redirect(url_for('auth.verify_otp', election_id=election_id))

    return render_template('auth/identify.html', election=election)


# ── Step 2: OTP verification ──────────────

@auth_bp.route('/verify-otp/<int:election_id>', methods=['GET', 'POST'])
def verify_otp(election_id):
    # Guard: must have come through Step 1
    student_number = session.get('otp_student_number')
    session_election_id = session.get('otp_election_id')

    if not student_number or session_election_id != election_id:
        flash('Session expired or invalid. Please start again.', 'danger')
        return redirect(url_for('auth.identify', election_id=election_id))

    election = Election.query.get_or_404(election_id)

    if not election.is_open:
        _clear_otp_session()
        flash('This election is no longer open.', 'danger')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        submitted_code = request.form.get('otp_code', '').strip()

        # Find the latest valid OTP record for this student + election
        otp_record = (OTPCode.query
                      .filter_by(student_number=student_number,
                                 election_id=election_id,
                                 is_used=False)
                      .order_by(OTPCode.id.desc())
                      .first())

        if not otp_record or not otp_record.is_valid:
            _clear_otp_session()
            flash('Your code has expired or is no longer valid. Please start again.', 'danger')
            return redirect(url_for('auth.identify', election_id=election_id))

        # Verify the submitted code
        if otp_record.code_hash != hash_otp(submitted_code):
            otp_record.attempts += 1
            db.session.commit()

            remaining = _MAX_OTP_ATTEMPTS - otp_record.attempts
            if remaining <= 0:
                otp_record.is_used = True
                db.session.commit()
                _clear_otp_session()
                flash('Too many incorrect attempts. Please start again.', 'danger')
                return redirect(url_for('auth.identify', election_id=election_id))

            flash(f'Incorrect code. {remaining} attempt(s) remaining.', 'danger')
            return redirect(url_for('auth.verify_otp', election_id=election_id))

        # OTP is correct — mark it used immediately
        otp_record.is_used = True
        db.session.commit()

        # Compute anonymous voter token and check for duplicate
        token_hash = compute_voter_token(student_number, election_id)

        if VoterToken.query.filter_by(token_hash=token_hash).first():
            _clear_otp_session()
            flash('You have already voted in this election.', 'warning')
            return redirect(url_for('main.index'))

        # Identity verified — discard student number from session immediately
        _clear_otp_session()

        # Pass only the anonymous token hash to the voting module
        session['voter_token_hash'] = token_hash
        session['voting_election_id'] = election_id

        return redirect(url_for('voting.cast_vote', election_id=election_id))

    # Calculate actual seconds remaining from the OTP record
    otp_record = (OTPCode.query
                  .filter_by(student_number=student_number,
                              election_id=election_id,
                              is_used=False)
                  .order_by(OTPCode.id.desc())
                  .first())

    if otp_record:
        secs = max(0, int((otp_record.expires_at.replace(tzinfo=timezone.utc)
                           - datetime.now(timezone.utc)).total_seconds()))
    else:
        secs = 0

    m, s = divmod(secs, 60)
    minutes_display = f'{m:02d}:{s:02d}'

    return render_template('auth/verify_otp.html', election=election,
                           otp_seconds_remaining=secs,
                           otp_minutes_remaining=minutes_display)


def _clear_otp_session():
    """Remove all identity data from session. Called as soon as OTP is verified or flow is aborted."""
    session.pop('otp_student_number', None)
    session.pop('otp_election_id', None)
