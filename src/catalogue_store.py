"""Save admin catalogue changes in OwnableFit's existing SQLite database."""

import json
from uuid import uuid4

from src.order_store import database
from src.product_catalogue import SIZE_ORDER, price_to_minor


def init_catalogue_db():
    """Create the catalogue table the first time the app starts."""
    with database() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS catalogue_edits (
                product_id TEXT PRIMARY KEY,
                product_json TEXT NOT NULL,
                revision INTEGER NOT NULL
            )
        """)


def catalogue_by_id(seed_products):
    """Start with the original dresses, then apply saved admin changes."""
    products = {
        product["product_id"]: product for product in seed_products
    }

    with database() as connection:
        rows = connection.execute("""
            SELECT product_id, product_json, revision
            FROM catalogue_edits
        """)
        for row in rows:
            products[row["product_id"]] = {
                **json.loads(row["product_json"]),
                "revision": row["revision"],
            }

    return products


def product_from_form(form, original):
    """Validate form values and keep existing product and model IDs."""
    product = dict(original)

    for key, label in (
        ("name", "Dress name"),
        ("dress_style", "Style"),
        ("length", "Length"),
        ("colour", "Colour"),
    ):
        value = form.get(key, "").strip()
        if not 1 <= len(value) <= 100:
            raise ValueError(f"{label} must contain 1–100 characters.")
        product[key] = value

    price = form.get("price", "").strip()
    if not 1 <= len(price) <= 32:
        raise ValueError("Enter a price in DKK.")
    product["price_minor"] = price_to_minor(price, "Price")

    occasions = form.get("occasions", "")
    product["occasions"] = [
        item.strip() for item in occasions.split(",") if item.strip()
    ]
    if not product["occasions"] or len(occasions) > 200:
        raise ValueError("Enter occasions in 200 characters or fewer.")

    # Keep any existing sizes, along with the standard XS–XL options.
    # Offer the standard sizes and preserve any additional sizes on the existing dress.
    sizes = dict.fromkeys((*SIZE_ORDER, *original.get("size_stock", {})))
    stock = {}

    for size in sizes:
        quantity = form.get(f"stock_{size}", "").strip()
        if not (
            1 <= len(quantity) <= 4
            and quantity.isascii()
            and quantity.isdecimal()
        ):
            raise ValueError(f"Enter a stock quantity from 0 to 9999 for {size}.")
        stock[size] = int(quantity)

    product["size_stock"] = stock
    product["archived"] = form.get("archived") == "on"
    return product


def save_product(product, expected_revision):
    """Save one dress and reject edits made from an outdated form."""
    record = dict(product)
    # Keep the edit revision in its own database column outside the product details.
    record.pop("revision", None)

    if "product_id" not in record:
        record["product_id"] = f"DRESS-{uuid4().hex[:16]}"

    product_id = record["product_id"]
    payload = json.dumps(record, ensure_ascii=False)

    with database() as connection:
        # Check the revision and write the edit in the same transaction.
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT revision FROM catalogue_edits WHERE product_id = ?",
            (product_id,),
        ).fetchone()

        revision = row["revision"] if row else 0
        # Reject an outdated edit so it cannot overwrite a more recent stock update.
        if str(revision) != expected_revision:
            raise ValueError(
                "This dress changed after you opened the form. "
                "Reload it before saving again."
            )

        connection.execute("""
            INSERT INTO catalogue_edits (product_id, product_json, revision)
            VALUES (?, ?, ?)
            ON CONFLICT(product_id) DO UPDATE SET
                product_json = excluded.product_json,
                revision = excluded.revision
        """, (product_id, payload, revision + 1))

    return product_id