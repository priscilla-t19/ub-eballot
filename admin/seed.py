"""Seed default admin account."""
import secrets

from models import AdminUser
from crypto_utils import hash_password, verify_password
from app import db


def seed_admin():
    """
    Ensure the admin account exists and its password matches ADMIN_PASSWORD in .env.

    Rules:
    - If no admin exists → create one with ADMIN_PASSWORD (or a random bootstrap
      password if ADMIN_PASSWORD is not set).
    - If an admin exists AND ADMIN_PASSWORD is set in .env → always sync the hash
      to the configured password. This makes the .env the single source of truth
      for the admin credential so operators can rotate it without a DB migration.
    - If ADMIN_PASSWORD is not set and the admin already exists → leave it alone
      (the operator has presumably set a password via the Change Password UI).
    """
    from flask import current_app

    username = current_app.config.get('ADMIN_USERNAME', 'admin')
    configured_password = current_app.config.get('ADMIN_PASSWORD')
    admin = AdminUser.query.filter_by(username=username).first()

    if not admin:
        bootstrap_password = configured_password or secrets.token_urlsafe(18)
        admin = AdminUser(
            username=username,
            password_hash=hash_password(bootstrap_password)
        )
        db.session.add(admin)
        db.session.commit()
        if configured_password:
            print(f"[seed] Created admin '{username}' with password from ADMIN_PASSWORD in .env.")
        else:
            print(
                f"[seed] WARNING: Created admin '{username}' with a random password. "
                "Set ADMIN_PASSWORD in .env and restart to apply a known password."
            )
        return

    # Admin already exists.
    if configured_password:
        # Always sync the hash to whatever ADMIN_PASSWORD says in .env.
        # This lets operators rotate the password by editing .env and restarting.
        if not verify_password(admin.password_hash, configured_password):
            admin.password_hash = hash_password(configured_password)
            db.session.commit()
            print(f"[seed] Admin '{username}' password synced from ADMIN_PASSWORD in .env.")
