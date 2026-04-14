"""
Verification Module — UB eBallot
Allows voters to verify their vote was included using receipt code.
"""

from flask import Blueprint, render_template, request, flash
from models import EncryptedBallot, Election
from crypto_utils import hash_receipt, decrypt_ballot, verify_ballot_chain

verification_bp = Blueprint('verification', __name__)


@verification_bp.route('/', methods=['GET', 'POST'])
def verify():
    result = None
    chain_ok = None

    if request.method == 'POST':
        receipt_code = request.form.get('receipt_code', '').strip().upper()

        if not receipt_code:
            flash('Please enter your receipt code.', 'warning')
            return render_template('verification/verify.html', result=None)

        receipt_hash = hash_receipt(receipt_code)
        ballot = EncryptedBallot.query.filter_by(receipt_hash=receipt_hash).first()

        if ballot:
            election = Election.query.get(ballot.election_id)
            chain_ok = verify_ballot_chain(ballot.election_id)

            # Decrypt to show choices (anonymously — no voter identity)
            choices_display = []
            try:
                data = decrypt_ballot(ballot.encrypted_data)
                for pos_id_str, cand_id in data.get('choices', {}).items():
                    from models import Position, Candidate
                    pos = Position.query.get(int(pos_id_str))
                    cand = Candidate.query.get(cand_id)
                    if pos and cand:
                        choices_display.append({
                            'position': pos.title,
                            'candidate': cand.full_name
                        })
            except Exception:
                pass

            result = {
                'found': True,
                'receipt_code': receipt_code,
                'election_title': election.title if election else 'Unknown',
                'cast_at': ballot.cast_at,
                'choices': choices_display,
                'chain_hash': ballot.chain_hash[:16] + '...',
                'chain_ok': chain_ok
            }
        else:
            result = {'found': False, 'receipt_code': receipt_code}

    return render_template('verification/verify.html', result=result)


@verification_bp.route('/bulletin/<int:election_id>')
def bulletin_board(election_id):
    """Public bulletin board: shows all receipt hashes (not codes) for an election."""
    election = Election.query.get_or_404(election_id)
    ballots = EncryptedBallot.query.filter_by(election_id=election_id)\
        .order_by(EncryptedBallot.id.asc()).all()

    chain_intact = verify_ballot_chain(election_id)

    return render_template('verification/bulletin.html',
                           election=election,
                           ballots=ballots,
                           chain_intact=chain_intact,
                           total=len(ballots))
