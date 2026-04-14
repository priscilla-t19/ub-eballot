"""Main routes for UB eBallot."""
from flask import Blueprint, render_template
from models import Election

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    elections = Election.query.filter_by(is_active=True).order_by(Election.start_time.desc()).all()
    return render_template('index.html', elections=elections)
