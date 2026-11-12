"""Administrator accounts for the local OwnableFit prototype.

Passwords are entered privately through the terminal.
Only password hashes are stored in the database.
"""

import getpass
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from src.order_store import database, init_db


MAX_FAILED_ATTEMPTS = 5
LOCK_SECONDS = 300

# Used for unknown usernames to avoid skipping password-hash verification.
DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(32))


def init_admin_db(db_path=None):
    """Add admin storage without changing existing orders."""
    init_db(db_path)

    with database(db_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK (is_active IN (0, 1)),
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until INTEGER NOT NULL DEFAULT 0
            )
        """)


def normalise_username(username):
    """Use consistent, limited administrator usernames."""
    if not isinstance(username, str):
        raise ValueError("Enter an administrator username.")

    username = username.strip().lower()

    if not re.fullmatch(r"[a-z0-9_.-]{3,50}", username):
        raise ValueError(
            "Username must contain 3–50 letters, numbers, "
            "dots, underscores or hyphens."
        )

    return username


def create_admin(username, password, db_path=None):
    """Create an administrator through a local setup command only."""
    username = normalise_username(username)

    if not isinstance(password, str) or not 15 <= len(password) <= 256:
        raise ValueError(
            "Use a password or passphrase containing 15–256 characters."
        )

    # Save a password hash so sign-in can verify the password without storing it as text.
    password_hash = generate_password_hash(password)
    init_admin_db(db_path)

    try:
        with database(db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO admin_users (
                    username, password_hash, created_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    username,
                    password_hash,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError(
            "That administrator username already exists."
        ) from None


def authenticate_admin(username, password, db_path=None):
    """Return basic admin identity on success, otherwise None.

    Password checks and failed-attempt updates are serialized.
    Account lockouts are a local-prototype protection, not a complete
    production authentication or rate-limiting solution.
    """
    try:
        username = normalise_username(username)
    except ValueError:
        username = ""

    if not isinstance(password, str) or len(password) > 256:
        return None

    now = int(time.time())

    with database(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute(
            """
            SELECT admin_id, username, password_hash, is_active,
                   failed_attempts, locked_until
            FROM admin_users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

        # Check a dummy hash for unknown usernames to reduce differences in sign-in timing.
        stored_hash = row["password_hash"] if row else DUMMY_HASH
        password_matches = check_password_hash(stored_hash, password)

        if row is None:
            return None

        if not row["is_active"] or row["locked_until"] > now:
            return None

        if password_matches:
            connection.execute(
                """
                UPDATE admin_users
                SET failed_attempts = 0, locked_until = 0
                WHERE admin_id = ?
                """,
                (row["admin_id"],),
            )

            return {
                "admin_id": row["admin_id"],
                "username": row["username"],
            }

        # Start a new attempt count after a previous lock has expired.
        previous_failures = (
            0 if row["locked_until"] else row["failed_attempts"]
        )
        failures = previous_failures + 1

        locked_until = (
            now + LOCK_SECONDS
            if failures >= MAX_FAILED_ATTEMPTS
            else 0
        )

        connection.execute(
            """
            UPDATE admin_users
            SET failed_attempts = ?, locked_until = ?
            WHERE admin_id = ?
            """,
            (failures, locked_until, row["admin_id"]),
        )

    return None


def get_active_admin(admin_id, db_path=None):
    """Recheck account status before granting access to admin pages."""
    if type(admin_id) is not int:
        return None

    with database(db_path) as connection:
        row = connection.execute(
            """
            SELECT admin_id, username
            FROM admin_users
            WHERE admin_id = ? AND is_active = 1
            """,
            (admin_id,),
        ).fetchone()

    return dict(row) if row else None


def setup_admin():
    """Create an account interactively without exposing its password."""
    init_admin_db()

    print("OwnableFit administrator setup")
    print("Passwords will not appear while you type.")

    username = input("Administrator username: ").strip()
    password = getpass.getpass("Password (at least 15 characters): ")
    confirmation = getpass.getpass("Repeat password: ")

    if password != confirmation:
        raise ValueError("Passwords did not match. No account was created.")

    create_admin(username, password)
    print("Administrator account created successfully.")
    print("The password was not printed or stored as plain text.")


if __name__ == "__main__":
    try:
        setup_admin()
    except (ValueError, EOFError, KeyboardInterrupt) as error:
        if isinstance(error, ValueError):
            print("Setup stopped:", error)
        else:
            print("\nSetup cancelled.")
        raise SystemExit(1)