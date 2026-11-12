"""Local payment simulation for the OwnableFit thesis prototype.

No payment provider is contacted and no money moves.
Card details are never collected.

Order checks and payment recording share one database transaction.
"""

import hashlib
import json
import secrets
from datetime import datetime, timezone

from src.order_store import database, init_db, validate_identity


OUTCOMES = ("success", "declined", "cancelled")


def order_fingerprint(order):
    """Identify the exact item, delivery and price snapshot being paid."""
    snapshot = {
        "items": [
            {
                "product_id": item["product_id"],
                "size": item["selected_size"],
                "quantity": item["quantity"],
                "unit_price_minor": item["unit_price_minor"],
            }
            for item in order["items"]
        ],
        "delivery_method": order["delivery_method"],
        "delivery_minor": order["delivery_minor"],
        "total_minor": order["total_minor"],
        "currency": order["currency"],
    }

    encoded = json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def init_payment_db(db_path=None):
    """Create simulation storage without deleting existing data."""
    init_db(db_path)

    with database(db_path) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS payment_attempts (
                attempt_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                request_token TEXT NOT NULL,
                created_at TEXT NOT NULL,
                outcome TEXT NOT NULL
                    CHECK (
                        outcome IN ('success', 'declined', 'cancelled')
                    ),
                amount_minor INTEGER NOT NULL CHECK (amount_minor >= 0),
                currency TEXT NOT NULL CHECK (currency = 'DKK'),
                is_simulated INTEGER NOT NULL DEFAULT 1
                    CHECK (is_simulated = 1),
                FOREIGN KEY (order_id) REFERENCES orders(order_id),
                UNIQUE (order_id, request_token)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_one_payment_success
                ON payment_attempts(order_id)
                WHERE outcome = 'success';
        """)


def simulate_payment(
    order_id,
    owner_id,
    request_token,
    outcome,
    expected_fingerprint,
    db_path=None,
):
    """Record an attempt only against the order snapshot the user saw.

    Repeated identical requests return their original result.
    A successful payment can be recorded only once per order.
    Decline and cancellation leave the order awaiting payment.
    """
    owner_id = validate_identity(owner_id, "Guest identifier")
    request_token = validate_identity(
        request_token,
        "Payment request identifier",
    )

    if not isinstance(order_id, str) or not order_id:
        raise ValueError("A valid order is required.")

    if outcome not in OUTCOMES:
        raise ValueError("Please select a supported simulation outcome.")

    if (
        not isinstance(expected_fingerprint, str)
        or len(expected_fingerprint) != 64
    ):
        raise ValueError("Reload the payment page before continuing.")

    init_payment_db(db_path)

    with database(db_path) as connection:
        # Checkout updates use the same write lock. An update cannot
        # occur between reading this order and recording its payment.
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute(
            """
            SELECT order_id, status, total_minor, currency,
                   delivery_method, delivery_minor
            FROM orders
            WHERE order_id = ? AND owner_id = ?
            """,
            (order_id, owner_id),
        ).fetchone()

        if row is None:
            raise ValueError("Order not found.")

        existing = connection.execute(
            """
            SELECT *
            FROM payment_attempts
            WHERE order_id = ? AND request_token = ?
            """,
            (order_id, request_token),
        ).fetchone()

        # Return the saved attempt when the same payment request is retried with the same outcome.
        if existing is not None:
            if existing["outcome"] != outcome:
                raise ValueError(
                    "This request was already processed. "
                    "Reload payment before trying again."
                )
            return dict(existing)

        if row["status"] != "pending_payment":
            raise ValueError("This order is no longer awaiting payment.")

        items = connection.execute(
            """
            SELECT product_id, selected_size, quantity, unit_price_minor
            FROM order_items
            WHERE order_id = ?
            ORDER BY line_id
            """,
            (order_id,),
        ).fetchall()

        # Rebuild the saved order state and compare it with what the customer saw.
        snapshot = dict(row)
        snapshot["items"] = [dict(item) for item in items]

        # Reject the payment attempt if the saved order differs from the one the customer reviewed.
        if not secrets.compare_digest(
            expected_fingerprint,
            order_fingerprint(snapshot),
        ):
            raise ValueError(
                "The order changed after the payment page opened. "
                "Reload the payment page and review the updated total."
            )

        attempt_id = "SIM-" + secrets.token_hex(12).upper()

        connection.execute(
            """
            INSERT INTO payment_attempts (
                attempt_id, order_id, request_token, created_at,
                outcome, amount_minor, currency, is_simulated
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt_id,
                order_id,
                request_token,
                datetime.now(timezone.utc).isoformat(),
                outcome,
                row["total_minor"],
                row["currency"],
                1,
            ),
        )

        # A successful simulation marks the order as paid in the same transaction.
        if outcome == "success":
            connection.execute(
                """
                UPDATE orders
                SET status = 'paid'
                WHERE order_id = ?
                  AND owner_id = ?
                  AND status = 'pending_payment'
                """,
                (order_id, owner_id),
            )

        attempt = connection.execute(
            """
            SELECT *
            FROM payment_attempts
            WHERE attempt_id = ?
            """,
            (attempt_id,),
        ).fetchone()

        return dict(attempt)


def list_payment_attempts(order_id, owner_id, db_path=None):
    """Return payment history only to the owning guest."""
    owner_id = validate_identity(owner_id, "Guest identifier")
    init_payment_db(db_path)

    with database(db_path) as connection:
        rows = connection.execute(
            """
            SELECT p.attempt_id, p.created_at, p.outcome,
                   p.amount_minor, p.currency, p.is_simulated
            FROM payment_attempts AS p
            JOIN orders AS o ON o.order_id = p.order_id
            WHERE p.order_id = ? AND o.owner_id = ?
            ORDER BY p.created_at, p.attempt_id
            """,
            (order_id, owner_id),
        ).fetchall()

    return [dict(row) for row in rows]


if __name__ == "__main__":
    init_payment_db()
    print("Payment simulation storage is ready.")
    print("Existing records were preserved. No money moved.")
