"""
Voting Module (Sandboxed) — UB eBallot

This module never sees or stores a student number. It receives only:
  - session['voter_token_hash']  — pre-computed HMAC set by the auth module
  - session['voting_election_id'] — the election being voted in

The voter token is written to the database atomically with the encrypted ballot,
providing race-condition-safe duplicate vote prevention at the DB level.
"""

from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from app import db
from models import Election, Position, Candidate, VoterToken, EncryptedBallot
from crypto_utils import (
    encrypt_ballot, decrypt_ballot, generate_receipt_code,
    hash_receipt, compute_chain_hash, get_last_chain_hash
)

voting_bp = Blueprint('voting', __name__)


def _get_voting_session(election_id: int):
    """
    Retrieve and validate the anonymous voting session.
    Returns the voter_token_hash if valid, or None on failure.
    """
    token_hash = session.get('voter_token_hash')
    session_election_id = session.get('voting_election_id')

    if not token_hash or session_election_id != election_id:
        return None

    # Confirm the token has not already been used (race-condition double-check)
    if VoterToken.query.filter_by(token_hash=token_hash).first():
        return None

    return token_hash


def _clear_voting_session():
    session.pop('voter_token_hash', None)
    session.pop('voting_election_id', None)


@voting_bp.route('/cast/<int:election_id>', methods=['GET', 'POST'])
def cast_vote(election_id):
    """
    Sandboxed ballot interface. No student identity is accessible here.
    Access is controlled solely by the anonymous voter token in the session.
    """
    token_hash = _get_voting_session(election_id)

    if not token_hash:
        flash('Invalid or expired voting session. Please enter your student number again.', 'danger')
        return redirect(url_for('main.index'))

    election = Election.query.get_or_404(election_id)

    if not election.is_open:
        flash('This election is no longer open.', 'danger')
        _clear_voting_session()
        return redirect(url_for('main.index'))

    positions = Position.query.filter_by(election_id=election_id).all()

    if request.method == 'POST':
        # Collect ballot choices {position_id: candidate_id}
        ballot_choices = {}
        for position in positions:
            candidate_id = request.form.get(f'position_{position.id}')
            if candidate_id:
                ballot_choices[str(position.id)] = int(candidate_id)

        if not ballot_choices:
            flash('Please make at least one selection before submitting.', 'warning')
            return render_template('voting/cast_vote.html', election=election, positions=positions)

        # Validate all candidate IDs belong to their declared positions
        for pos_id_str, cand_id in ballot_choices.items():
            cand = Candidate.query.filter_by(id=cand_id, position_id=int(pos_id_str)).first()
            if not cand:
                flash('Invalid ballot submission detected.', 'danger')
                return render_template('voting/cast_vote.html', election=election, positions=positions)

        # Build ballot payload — no voter identity included
        ballot_data = {
            'election_id': election_id,
            'choices': ballot_choices,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

        encrypted_data = encrypt_ballot(ballot_data)
        receipt_code = generate_receipt_code()
        receipt_hash = hash_receipt(receipt_code)
        prev_hash = get_last_chain_hash(election_id)
        chain_hash = compute_chain_hash(encrypted_data, prev_hash)

        ballot = EncryptedBallot(
            election_id=election_id,
            encrypted_data=encrypted_data,
            receipt_code=receipt_code,
            receipt_hash=receipt_hash,
            prev_hash=prev_hash,
            chain_hash=chain_hash,
        )
        db.session.add(ballot)

        # Store the voter token atomically with the ballot.
        # If the token already exists (race condition), the DB unique constraint
        # raises an IntegrityError and rolls back the entire transaction.
        voter_token = VoterToken(token_hash=token_hash, election_id=election_id)
        db.session.add(voter_token)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash(
                'Your vote could not be recorded — a duplicate vote was detected. '
                'Contact the SRC if you believe this is an error.',
                'danger'
            )
            _clear_voting_session()
            return redirect(url_for('main.index'))

        _clear_voting_session()
        session['last_receipt'] = receipt_code

        flash('Your vote has been cast successfully!', 'success')
        return redirect(url_for('voting.vote_receipt'))

    return render_template('voting/cast_vote.html', election=election, positions=positions)


@voting_bp.route('/receipt')
def vote_receipt():
    receipt_code = session.pop('last_receipt', None)
    if not receipt_code:
        return redirect(url_for('main.index'))
    return render_template('voting/receipt.html', receipt_code=receipt_code)


@voting_bp.route('/results/<int:election_id>')
def results(election_id):
    election = Election.query.get_or_404(election_id)
    positions = Position.query.filter_by(election_id=election_id).all()
    tallies = {}

    for ballot in EncryptedBallot.query.filter_by(election_id=election_id).all():
        try:
            data = decrypt_ballot(ballot.encrypted_data)
            for pos_id_str, cand_id in data.get('choices', {}).items():
                pos_id = int(pos_id_str)
                tallies.setdefault(pos_id, {})[cand_id] = (
                    tallies.get(pos_id, {}).get(cand_id, 0) + 1
                )
        except Exception:
            continue

    total_votes = EncryptedBallot.query.filter_by(election_id=election_id).count()
    return render_template('voting/results.html',
                           election=election,
                           positions=positions,
                           tallies=tallies,
                           total_votes=total_votes)
