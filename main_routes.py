"""Main routes for UB eBallot."""
from flask import Blueprint, render_template
from models import Election, Position, EncryptedBallot
from crypto_utils import decrypt_ballot

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    elections = Election.query.filter_by(is_active=True).order_by(Election.start_time.desc()).all()

    # Build tallies for all elections
    published = Election.query.order_by(Election.end_time.desc()).all()
    results_data = []
    for election in published:
        positions = Position.query.filter_by(election_id=election.id).all()
        tallies = {}
        for ballot in EncryptedBallot.query.filter_by(election_id=election.id).all():
            try:
                data = decrypt_ballot(ballot.encrypted_data)
                for pos_id_str, cand_id in data.get('choices', {}).items():
                    pos_id = int(pos_id_str)
                    tallies.setdefault(pos_id, {})[cand_id] = (
                        tallies.get(pos_id, {}).get(cand_id, 0) + 1
                    )
            except Exception:
                continue
        total_votes = EncryptedBallot.query.filter_by(election_id=election.id).count()
        results_data.append({
            'election': election,
            'positions': positions,
            'tallies': tallies,
            'total_votes': total_votes,
        })

    return render_template('index.html', elections=elections, results_data=results_data)
