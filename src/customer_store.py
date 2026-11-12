"""Customer account storage for the OwnableFit local prototype.

Store password hashes, never plain-text passwords.
Customer accounts do not grant administrator access.
Body measurements are not stored in customer accounts.
"""

import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from src.order_store import database, init_db


MAX_FAILED_ATTEMPTS = 5
LOCK_SECONDS = 300

DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(32))


def init_customer_db(db_path=None):
    """Add customer accounts without changing existing guest orders."""
    init_db(db_path)

    with database(db_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS customer_accounts (
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                order_owner_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK (is_active IN (0, 1)),
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until INTEGER NOT NULL DEFAULT 0
            )
        """)


def normalise_email(email):
    """Apply a consistent case-insensitive account-email policy."""
    if not isinstance(email, str):
        raise ValueError("Enter a valid email address.")

    email = email.strip().lower()

    if (
        len(email) > 254
        or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)
        or any(ord(character) < 32 for character in email)
    ):
        raise ValueError("Enter a valid email address.")

    # Syntax validation does not establish ownership of this address.
    return email


def validate_display_name(name):
    if not isinstance(name, str):
        raise ValueError("Enter your name.")

    name = name.strip()

    if not 1 <= len(name) <= 120:
        raise ValueError("Name must contain 1–120 characters.")

    if any(ord(character) < 32 for character in name):
        raise ValueError("Name contains unsupported characters.")

    return name


def create_customer(display_name, email, password, db_path=None):
    """Create a customer with an independent order-ownership identifier."""
    name = validate_display_name(display_name)
    email = normalise_email(email)

    if not isinstance(password, str) or not 15 <= len(password) <= 256:
        raise ValueError(
            "Use a password or passphrase containing 15–256 characters."
        )

    password_hash = generate_password_hash(password)
    # Give each customer a random order ownership ID independent of their email address.
    order_owner_id = "customer-" + secrets.token_hex(32)

    init_customer_db(db_path)

    try:
        with database(db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO customer_accounts (
                    email, display_name, password_hash,
                    order_owner_id, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    email,
                    name,
                    password_hash,
                    order_owner_id,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError(
            "Unable to create an account with those details. "
            "If you already registered, try signing in."
        ) from None


def authenticate_customer(email, password, db_path=None):
    """Return identity on success; use the same failure result otherwise."""
    try:
        email = normalise_email(email)
    except ValueError:
        email = ""

    if not isinstance(password, str) or len(password) > 256:
        return None

    now = int(time.time())

    with database(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")

        account = connection.execute(
            """
            SELECT customer_id, email, display_name, password_hash,
                   order_owner_id, is_active,
                   failed_attempts, locked_until
            FROM customer_accounts
            WHERE email = ?
            """,
            (email,),
        ).fetchone()

        stored_hash = account["password_hash"] if account else DUMMY_HASH
        matches = check_password_hash(stored_hash, password)

        if account is None:
            return None

        if not account["is_active"] or account["locked_until"] > now:
            return None

        if matches:
            connection.execute(
                """
                UPDATE customer_accounts
                SET failed_attempts = 0, locked_until = 0
                WHERE customer_id = ?
                """,
                (account["customer_id"],),
            )

            return {
                "customer_id": account["customer_id"],
                "email": account["email"],
                "display_name": account["display_name"],
                "order_owner_id": account["order_owner_id"],
            }

        previous = (
            0 if account["locked_until"] else account["failed_attempts"]
        )
        failures = previous + 1
        locked_until = (
            now + LOCK_SECONDS
            if failures >= MAX_FAILED_ATTEMPTS
            else 0
        )

        connection.execute(
            """
            UPDATE customer_accounts
            SET failed_attempts = ?, locked_until = ?
            WHERE customer_id = ?
            """,
            (failures, locked_until, account["customer_id"]),
        )

    return None


def get_active_customer(customer_id, db_path=None):
    """Recheck account status before granting customer-account access."""
    if type(customer_id) is not int:
        return None

    with database(db_path) as connection:
        account = connection.execute(
            """
            SELECT customer_id, email, display_name, order_owner_id
            FROM customer_accounts
            WHERE customer_id = ? AND is_active = 1
            """,
            (customer_id,),
        ).fetchone()

    return dict(account) if account else None


if __name__ == "__main__":
    init_customer_db()
    print("Customer account storage initialised.")
    print("Existing orders and administrator accounts were preserved.")
    print("No customer accounts were created.")