"""Test order totals, delivery changes and guest ownership.

Uses a temporary database, not the application's saved orders.
"""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from src.order_store import create_order, get_order, init_db, list_orders


class OrderStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        self.db_path = (
            Path(self.temporary_directory.name) / "test_orders.sqlite3"
        )
        init_db(self.db_path)

        self.owner_id = "test-guest-owner"
        self.checkout_token = "test-checkout-token"

        self.customer = {
            "full_name": "Test Customer",
            "email": "customer@example.com",
            "address_line": "Example Street 1",
            "city": "Copenhagen",
            "postal_code": "1000",
            "country": "Denmark",
        }

        self.products = {
            "TEST-001": {
                "product_id": "TEST-001",
                "name": "Test Dress",
                "price_minor": 94900,
                "size_stock": {"M": 5},
            }
        }

        self.cart = [{
            "product_id": "TEST-001",
            "size": "M",
            "quantity": 1,
        }]

    def save_order(self, delivery):
        return create_order(
            owner_id=self.owner_id,
            checkout_token=self.checkout_token,
            customer=self.customer,
            delivery_method=delivery,
            cart=self.cart,
            products_by_id=self.products,
            db_path=self.db_path,
        )

    def read_order(self, order_id):
        return get_order(
            order_id,
            self.owner_id,
            db_path=self.db_path,
        )

    def test_standard_delivery_total(self):
        order = self.read_order(self.save_order("standard"))

        self.assertEqual(order["subtotal_minor"], 94900)
        self.assertEqual(order["delivery_minor"], 3900)
        self.assertEqual(order["total_minor"], 98800)

    def test_collection_total(self):
        order = self.read_order(self.save_order("collection"))

        self.assertEqual(order["subtotal_minor"], 94900)
        self.assertEqual(order["delivery_minor"], 0)
        self.assertEqual(order["total_minor"], 94900)

    def test_collection_changed_to_standard(self):
        first_id = self.save_order("collection")
        second_id = self.save_order("standard")
        order = self.read_order(second_id)

        self.assertEqual(first_id, second_id)
        self.assertEqual(order["delivery_method"], "standard")
        self.assertEqual(order["delivery_minor"], 3900)
        self.assertEqual(order["total_minor"], 98800)

    def test_standard_changed_to_collection(self):
        first_id = self.save_order("standard")
        second_id = self.save_order("collection")
        order = self.read_order(second_id)

        self.assertEqual(first_id, second_id)
        self.assertEqual(order["delivery_method"], "collection")
        self.assertEqual(order["delivery_minor"], 0)
        self.assertEqual(order["total_minor"], 94900)

    def test_repeated_submission_does_not_duplicate(self):
        first_id = self.save_order("standard")
        second_id = self.save_order("standard")

        orders = list_orders(self.owner_id, db_path=self.db_path)
        order = self.read_order(first_id)

        self.assertEqual(first_id, second_id)
        self.assertEqual(len(orders), 1)
        self.assertEqual(len(order["items"]), 1)
        self.assertEqual(order["items"][0]["quantity"], 1)

    def test_other_guest_cannot_read_order(self):
        order_id = self.save_order("standard")

        result = get_order(
            order_id,
            "different-guest",
            db_path=self.db_path,
        )

        self.assertIsNone(result)
        self.assertEqual(
            list_orders("different-guest", db_path=self.db_path),
            [],
        )

    def test_invalid_delivery_preserves_existing_order(self):
        order_id = self.save_order("collection")

        with self.assertRaises(ValueError):
            self.save_order("unsupported-delivery")

        order = self.read_order(order_id)

        self.assertEqual(order["delivery_method"], "collection")
        self.assertEqual(order["total_minor"], 94900)

    def test_paid_order_cannot_be_modified(self):
        order_id = self.save_order("standard")

        # The inner context commits; the outer context closes.
        with closing(sqlite3.connect(self.db_path)) as connection:
            with connection:
                connection.execute(
                    "UPDATE orders SET status = ? WHERE order_id = ?",
                    ("paid", order_id),
                )

        with self.assertRaises(ValueError):
            self.save_order("collection")

        order = self.read_order(order_id)

        self.assertEqual(order["status"], "paid")
        self.assertEqual(order["delivery_method"], "standard")
        self.assertEqual(order["total_minor"], 98800)


if __name__ == "__main__":
    unittest.main()