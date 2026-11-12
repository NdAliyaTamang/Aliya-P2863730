"""Integration tests for OwnableFit's pages and recommendation form.

The inputs are illustrative. These tests do not train or tune the model.
"""

import unittest
from unittest.mock import patch

from app import dress_ids, metadata
from ml_model.predict import predict_size

# Use the same entry point as the website so all routes are registered.
from run import app


class OwnableFitTests(unittest.TestCase):
    """Check page rendering, prediction, validation and error handling."""

    def setUp(self):
        """Create a fresh test client without starting a web server."""
        self.client = app.test_client()
        self.sample = {
            "item_id": dress_ids[0],
            "height_cm": "165",
            "weight_kg": "62",
            "bra_size": "34b",
        }

    def assert_rejected(self, values):
        """Check that invalid input produces an error instead of a result."""
        response = self.client.post("/", data=values)
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unable to predict", page)
        self.assertNotIn("Predicted dataset size code:", page)

    def test_pages_load(self):
        for path in ("/", "/dashboard", "/evaluation"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)

    def test_navigation_links(self):
        """Check that the three model pages link to one another."""
        for path in ("/", "/dashboard", "/evaluation"):
            with self.subTest(path=path):
                page = self.client.get(path).get_data(as_text=True)
                for destination in ("/", "/dashboard", "/evaluation"):
                    self.assertIn(f'href="{destination}"', page)

    def test_valid_prediction(self):
        """Compare the web result with the real model's direct output."""
        expected = predict_size(self.sample)
        self.assertIn(expected, metadata["size_codes"])

        response = self.client.post("/", data=self.sample)
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Predicted dataset size code:", page)
        self.assertIn(f"<strong>{expected}</strong>", page)

    def test_missing_fields(self):
        # Remove one field at a time to verify backend validation.
        for field in self.sample:
            with self.subTest(field=field):
                values = self.sample.copy()
                del values[field]
                self.assert_rejected(values)

    def test_invalid_measurements(self):
        for field in ("height_cm", "weight_kg"):
            for value in ("-10", "0", "abc", "nan", "inf", "-inf", ""):
                with self.subTest(field=field, value=value):
                    self.assert_rejected({**self.sample, field: value})

    def test_unknown_categories(self):
        for field, value in (
            ("item_id", "not-a-dress"),
            ("bra_size", "not-a-size"),
        ):
            with self.subTest(field=field):
                self.assert_rejected({**self.sample, field: value})

    def test_no_store_header(self):
        """Check cache headers on both successful and rejected requests."""
        responses = [
            self.client.get("/"),
            self.client.get("/dashboard"),
            self.client.get("/evaluation"),
            self.client.post("/", data=self.sample),
            self.client.post("/", data={}),
        ]

        for response in responses:
            self.assertEqual(response.headers.get("Cache-Control"), "no-store")

    def test_prediction_failure(self):
        # Simulate an unexpected failure and check that its details stay private.
        with patch(
            "app.predict_size",
            side_effect=RuntimeError("INTERNAL_TEST_DETAIL"),
        ):
            response = self.client.post("/", data=self.sample)

        page = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 500)
        self.assertIn("The prediction could not be completed.", page)
        self.assertNotIn("INTERNAL_TEST_DETAIL", page)
        self.assertNotIn("Predicted dataset size code:", page)

    def test_size_code_zero_displays(self):
        """Check that zero is displayed as a valid prediction."""
        with patch("app.predict_size", return_value=0):
            response = self.client.post("/", data=self.sample)

        self.assertEqual(response.status_code, 200)
        self.assertIn("<strong>0</strong>", response.get_data(as_text=True))

    def test_oversized_submission(self):
        response = self.client.post("/", data={"extra": "x" * 20000})
        self.assertEqual(response.status_code, 413)

    def test_start_again_clears_result(self):
        self.client.post("/", data=self.sample)

        response = self.client.get("/")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Predicted dataset size code:", page)
        self.assertNotIn("Unable to predict", page)


if __name__ == "__main__":
    unittest.main()