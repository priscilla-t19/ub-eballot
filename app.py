"""
UB eBallot - Online Anonymous Voting System
University of Botswana SRC Elections
Alpha Version
"""

import os
from dotenv import load_dotenv
load_dotenv()  # Load environment variables first

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from config import Config

db = SQLAlchemy()
mail = Mail()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    mail.init_app(app)

    # ── Apply security configurations ──
    from security import configure_session_security, configure_security_headers
    configure_session_security(app)
    configure_security_headers(app)

    # ── Initialize security middleware ──
    # Temporarily disabled for debugging
    # from security_middleware import init_security_middleware
    # init_security_middleware(app)

    from auth.routes import auth_bp
    from voting.routes import voting_bp
    from verification.routes import verification_bp
    from admin.routes import admin_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(voting_bp, url_prefix='/vote')
    app.register_blueprint(verification_bp, url_prefix='/verify')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from main_routes import main_bp
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()
        from admin.seed import seed_admin
        seed_admin()

    # ── Register error handlers ──
    register_error_handlers(app)

    # ── Register Flask CLI commands ──
    register_cli_commands(app)

    return app


def register_error_handlers(app):
    """Register HTTP error handlers so all error pages render consistently."""
    from flask import render_template

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        from flask import redirect, url_for
        return redirect(url_for('main.index'))

    @app.errorhandler(413)
    def payload_too_large(e):
        return render_template('errors/413.html'), 413

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        return render_template('errors/429.html'), 429

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception('Internal server error: %s', e)
        return render_template('errors/500.html'), 500


def register_cli_commands(app):
    """Register Flask CLI commands for database administration."""
    import click
    from database_admin import (
        quick_database_summary, full_database_inspection, interactive_inspector,
        inspect_student_registry, inspect_elections, inspect_voting_status
    )
    from security import print_deployment_checklist

    @app.cli.command()
    def db_summary():
        """Show quick database summary."""
        quick_database_summary()

    @app.cli.command()
    def db_inspect():
        """Interactive database inspector."""
        interactive_inspector()

    @app.cli.command()
    def db_full():
        """Full database inspection report."""
        full_database_inspection()

    @app.cli.command()
    def db_registry():
        """Show student registry."""
        inspect_student_registry()

    @app.cli.command()
    def db_elections():
        """Show election details."""
        inspect_elections()

    @app.cli.command()
    def db_voting():
        """Show voting statistics."""
        inspect_voting_status()

    @app.cli.command()
    def security_checklist():
        """Print deployment security checklist."""
        print_deployment_checklist()

    @app.cli.command()
    def mobile_guide():
        """Print mobile deployment guide."""
        from mobile_deployment import print_mobile_guide
        print_mobile_guide()

    @app.cli.command('backup-db')
    @click.option('--dest', default='backups', help='Directory to store backups (default: ./backups)')
    def backup_db(dest):
        """Back up the SQLite database.  Usage: flask backup-db [--dest DIR]

        For PostgreSQL use pg_dump instead — this command targets SQLite only.
        """
        import shutil
        from pathlib import Path
        from datetime import datetime

        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if not db_uri.startswith('sqlite'):
            click.echo('[skip] backup-db only supports SQLite. Use pg_dump for PostgreSQL.')
            return

        # Extract file path from sqlite:///path
        db_path = Path(db_uri.replace('sqlite:///', '').replace('sqlite://', ''))
        if not db_path.is_absolute():
            db_path = Path(app.root_path) / db_path

        if not db_path.exists():
            click.echo(f'[error] Database file not found: {db_path}')
            raise SystemExit(1)

        dest_dir = Path(dest)
        dest_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = dest_dir / f'ub_eballot_{timestamp}.db'
        shutil.copy2(db_path, backup_path)
        click.echo(f'[ok] Backup saved to {backup_path}')
        click.echo(f'     Source: {db_path} ({db_path.stat().st_size // 1024} KB)')

    @app.cli.command('reset-admin')
    @click.argument('new_password')
    def reset_admin(new_password):
        """Reset the admin password. Usage: flask reset-admin <new_password>"""
        from models import AdminUser
        from crypto_utils import hash_password
        from admin.routes import is_strong_password

        ok, msg = is_strong_password(new_password)
        if not ok:
            click.echo(f'[error] Password rejected: {msg}')
            raise SystemExit(1)

        admin = AdminUser.query.filter_by(username='admin').first()
        if not admin:
            click.echo('[error] No admin account found. Start the app once to seed it.')
            raise SystemExit(1)

        admin.password_hash = hash_password(new_password)
        db.session.commit()
        click.echo(f"[ok] Password for admin '{admin.username}' has been updated.")
        click.echo("     Update ADMIN_PASSWORD in .env to match so it persists on restart.")
