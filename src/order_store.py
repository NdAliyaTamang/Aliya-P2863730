"""SQLite storage for OwnableFit prototype orders.

Store checkout details and order snapshots.
Never store body measurements or payment-card details.
"""

import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "instance" / "orders.sqlite3"

# Illustrative delivery options, not carrier quotations.
DELIVERY_OPTIONS = {
    "standard": {
        "label": "Standard delivery",
        "price_minor": 3900,
    },
    "collection": {
        "label": "Collection",
        "price_minor": 0,
    },
}

CUSTOMER_FIELDS = (
    "full_name",
    "email",
    "address_line",
    "city",
    "postal_code",
    "country",
)


@contextmanager
def database(db_path=None):
    """Commit successful operations and roll back failures."""
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(path), timeout=10)
    connection.row_factory = sqlite3.Row
    # Enable relationship checks so order items must refer to valid orders.
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        # Commit successful writes and roll them back if the operation raises an error.
        with connection:
            yield connection
    finally:
        connection.close()


def init_db(db_path=None):
    """Create tables without deleting existing orders."""
    with database(db_path) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                checkout_token TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending_payment'
                    CHECK (
                        status IN (
                            'pending_payment', 'paid', 'cancelled'
                        )
                    ),
                currency TEXT NOT NULL CHECK (currency = 'DKK'),
                customer_json TEXT NOT NULL,
                delivery_method TEXT NOT NULL,
                delivery_label TEXT NOT NULL,
                subtotal_minor INTEGER NOT NULL
                    CHECK (subtotal_minor >= 0),
                delivery_minor INTEGER NOT NULL
                    CHECK (delivery_minor >= 0),
                total_minor INTEGER NOT NULL
                    CHECK (
                        total_minor = subtotal_minor + delivery_minor
                    ),
                UNIQUE (owner_id, checkout_token)
            );

            CREATE TABLE IF NOT EXISTS order_items (
                line_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                selected_size TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                unit_price_minor INTEGER NOT NULL
                    CHECK (unit_price_minor >= 0),
                line_total_minor INTEGER NOT NULL
                    CHECK (
                        line_total_minor = quantity * unit_price_minor
                    ),
                FOREIGN KEY (order_id) REFERENCES orders(order_id),
                UNIQUE (order_id, product_id, selected_size)
            );

            CREATE INDEX IF NOT EXISTS idx_orders_owner
                ON orders(owner_id, created_at);
        """)


def required_text(value, label, maximum):
    """Validate required text without echoing personal information."""
    if not isinstance(value, str):
        raise ValueError(f"{label} is required.")

    text = value.strip()

    if not text:
        raise ValueError(f"{label} is required.")

    if len(text) > maximum:
        raise ValueError(
            f"{label} must not exceed {maximum} characters."
        )

    if any(ord(character) < 32 for character in text):
        raise ValueError(f"{label} contains unsupported characters.")

    return text


def validate_customer(customer):
    """Accept only the expected checkout fields."""
    if not isinstance(customer, dict):
        raise ValueError("Checkout details are required.")

    limits = {
        "full_name": 120,
        "email": 254,
        "address_line": 200,
        "city": 100,
        "postal_code": 20,
        "country": 80,
    }

    labels = {
        "full_name": "Full name",
        "email": "Email",
        "address_line": "Address",
        "city": "City",
        "postal_code": "Postal code",
        "country": "Country",
    }

    clean = {
        field: required_text(
            customer.get(field), labels[field], limits[field]
        )
        for field in CUSTOMER_FIELDS
    }

    email = clean["email"]
    if (
        email.count("@") != 1
        or any(character.isspace() for character in email)
    ):
        raise ValueError(
            "Enter an email address in name@example.com format."
        )

    local, domain = email.split("@")
    if not local or "." not in domain or domain.startswith("."):
        raise ValueError(
            "Enter an email address in name@example.com format."
        )

    return clean


def validate_identity(value, label):
    return required_text(value, label, 128)


def create_order(
    owner_id,
    checkout_token,
    customer,
    delivery_method,
    cart,
    products_by_id,
    db_path=None,
):
    """Create or refresh a pending order for the checkout token.

    Recalculate prices and delivery from backend data every time.
    A pending order can be refreshed before payment integration.
    Paid or cancelled orders cannot be changed.

    Payment-session creation will require locking this snapshot before
    an external payment is started.
    """
    from src.cart_service import get_cart_summary

    owner_id = validate_identity(owner_id, "Guest identifier")
    checkout_token = validate_identity(
        checkout_token, "Checkout identifier"
    )
    clean_customer = validate_customer(customer)

    if (
        not isinstance(delivery_method, str)
        or delivery_method not in DELIVERY_OPTIONS
    ):
        raise ValueError("Please select a supported delivery option.")

    # Rebuild order totals from server-side catalogue prices and stock.
    summary = get_cart_summary(cart, products_by_id)
    if not summary["items"]:
        raise ValueError("Your cart is empty.")

    delivery = DELIVERY_OPTIONS[delivery_method]
    subtotal_minor = summary["subtotal_minor"]
    delivery_minor = delivery["price_minor"]
    total_minor = subtotal_minor + delivery_minor
    customer_json = json.dumps(clean_customer, ensure_ascii=False)

    init_db(db_path)

    with database(db_path) as connection:
        # Serialize writes so duplicate requests cannot create two orders.
        connection.execute("BEGIN IMMEDIATE")

        existing = connection.execute(
            """
            SELECT order_id, status
            FROM orders
            WHERE owner_id = ? AND checkout_token = ?
            """,
            (owner_id, checkout_token),
        ).fetchone()

        # Handle a repeated checkout using the order already associated with this token.
        if existing is not None:
            if existing["status"] != "pending_payment":
                raise ValueError(
                    "This order can no longer be changed. "
                    "Start a new checkout."
                )

            order_id = existing["order_id"]

            # Update delivery and totals together in the same transaction.
            connection.execute(
                """
                UPDATE orders
                SET customer_json = ?,
                    delivery_method = ?,
                    delivery_label = ?,
                    subtotal_minor = ?,
                    delivery_minor = ?,
                    total_minor = ?
                WHERE order_id = ? AND owner_id = ?
                """,
                (
                    customer_json,
                    delivery_method,
                    delivery["label"],
                    subtotal_minor,
                    delivery_minor,
                    total_minor,
                    order_id,
                    owner_id,
                ),
            )

            connection.execute(
                "DELETE FROM order_items WHERE order_id = ?",
                (order_id,),
            )

        else:
            order_id = "OF-" + secrets.token_hex(12).upper()

            connection.execute(
                """
                INSERT INTO orders (
                    order_id, owner_id, checkout_token, created_at,
                    status, currency, customer_json, delivery_method,
                    delivery_label, subtotal_minor, delivery_minor,
                    total_minor
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    owner_id,
                    checkout_token,
                    datetime.now(timezone.utc).isoformat(),
                    "pending_payment",
                    "DKK",
                    customer_json,
                    delivery_method,
                    delivery["label"],
                    subtotal_minor,
                    delivery_minor,
                    total_minor,
                ),
            )

        # Save the current validated cart as the order snapshot.
        for item in summary["items"]:
            connection.execute(
                """
                INSERT INTO order_items (
                    order_id, product_id, product_name, selected_size,
                    quantity, unit_price_minor, line_total_minor
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    item["product_id"],
                    item["name"],
                    item["size"],
                    item["quantity"],
                    item["price_minor"],
                    item["line_total_minor"],
                ),
            )

    return order_id


def get_order(order_id, owner_id, db_path=None):
    """Return an order only to its owning guest."""
    owner_id = validate_identity(owner_id, "Guest identifier")

    if not isinstance(order_id, str):
        return None

    with database(db_path) as connection:
        row = connection.execute(
            """
            SELECT order_id, created_at, status, currency, customer_json,
                   delivery_method, delivery_label, subtotal_minor,
                   delivery_minor, total_minor
            FROM orders
            WHERE order_id = ? AND owner_id = ?
            """,
            (order_id, owner_id),
        ).fetchone()

        if row is None:
            return None

        order = dict(row)
        order["customer"] = json.loads(order.pop("customer_json"))

        items = connection.execute(
            """
            SELECT line_id, product_id, product_name, selected_size,
                   quantity, unit_price_minor, line_total_minor
            FROM order_items
            WHERE order_id = ?
            ORDER BY line_id
            """,
            (order_id,),
        ).fetchall()

        order["items"] = [dict(item) for item in items]

    return order


def list_orders(owner_id, db_path=None):
    """List summaries belonging to the current guest."""
    owner_id = validate_identity(owner_id, "Guest identifier")

    with database(db_path) as connection:
        rows = connection.execute(
            """
            SELECT order_id, created_at, status, currency, total_minor
            FROM orders
            WHERE owner_id = ?
            ORDER BY created_at DESC, order_id DESC
            """,
            (owner_id,),
        ).fetchall()

    return [dict(row) for row in rows]


if __name__ == "__main__":
    init_db()
    print("Order database initialised successfully.")
    print("Existing orders were preserved.")