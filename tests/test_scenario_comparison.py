"""Test the low, medium and high sustainability scenario comparison."""

import unittest
from unittest.mock import patch

from src.sustainability import compare_scenarios

# Use the application's normal entry point for the web tests.
from run import app


class ComparisonCalculationTests(unittest.TestCase):
    """Test the calculation directly, independently of the web form."""

    def setUp(self):
        self.assumptions = {
            "orders": 1000,
            "size_return_rate_percent": 20,
            "low_reduction_percent": 5,
            "medium_reduction_percent": 10,
            "high_reduction_percent": 20,
            "kg_co2e_per_return": 1,
        }

    def test_example_comparison(self):
        results = compare_scenarios(**self.assumptions)

        self.assertEqual(
            [row["label"] for row in results],
            ["Low", "Medium", "High"],
        )

        # All scenarios start at 200 expected returns. Only the reduction varies.
        for row, expected in zip(results, (10, 20, 40)):
            self.assertAlmostEqual(row["baseline_returns"], 200)
            self.assertAlmostEqual(row["avoided_returns"], expected)
            self.assertAlmostEqual(row["remaining_returns"], 200 - expected)
            self.assertAlmostEqual(row["potential_kg_co2e_saved"], expected)

    def test_unordered_reductions_rejected(self):
        for low, medium, high in ((20, 10, 30), (5, 30, 20)):
            with self.subTest(low=low, medium=medium, high=high):
                values = {
                    **self.assumptions,
                    "low_reduction_percent": low,
                    "medium_reduction_percent": medium,
                    "high_reduction_percent": high,
                }

                with self.assertRaises(ValueError):
                    compare_scenarios(**values)

    def test_equal_reductions_allowed(self):
        results = compare_scenarios(**{
            **self.assumptions,
            "low_reduction_percent": 10,
            "medium_reduction_percent": 10,
            "high_reduction_percent": 10,
        })

        for row in results:
            self.assertAlmostEqual(row["avoided_returns"], 20)

    def test_invalid_reductions_rejected(self):
        fields = (
            "low_reduction_percent",
            "medium_reduction_percent",
            "high_reduction_percent",
        )

        for field in fields:
            for value in (-1, 101, "nan", "inf", "", "abc"):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        compare_scenarios(**{**self.assumptions, field: value})

    def test_fractional_expected_returns(self):
        """Expected return counts can be fractional."""
        results = compare_scenarios(**{**self.assumptions, "orders": 125})

        self.assertAlmostEqual(results[0]["avoided_returns"], 1.25)
        self.assertAlmostEqual(results[1]["avoided_returns"], 2.5)
        self.assertAlmostEqual(results[2]["avoided_returns"], 5)


class ComparisonPageTests(unittest.TestCase):
    """Test submission, errors and navigation through Flask's test client."""

    def setUp(self):
        self.client = app.test_client()
        self.sample = {
            "orders": "1000",
            "return_rate": "20",
            "impact": "1",
            "low": "5",
            "medium": "10",
            "high": "20",
        }

    def test_page_loads(self):
        response = self.client.get("/sustainability/compare")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Hypothetical comparison results", page)

    def test_valid_submission(self):
        response = self.client.post("/sustainability/compare", data=self.sample)
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Hypothetical comparison results", page)

        for expected in ("10.00", "20.00", "40.00"):
            self.assertIn(expected, page)

        # Check that users can still see the assumptions behind their results.
        for value in self.sample.values():
            self.assertIn(f'value="{value}"', page)

    def test_missing_fields(self):
        for field in self.sample:
            with self.subTest(field=field):
                values = self.sample.copy()
                del values[field]

                response = self.client.post("/sustainability/compare", data=values)
                page = response.get_data(as_text=True)

                self.assertEqual(response.status_code, 400)
                self.assertIn("Unable to compare scenarios", page)
                self.assertNotIn("Hypothetical comparison results", page)

    def test_unordered_submission(self):
        response = self.client.post(
            "/sustainability/compare",
            data={**self.sample, "low": "50"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn(
            "Hypothetical comparison results",
            response.get_data(as_text=True),
        )

    def test_oversized_submission(self):
        response = self.client.post(
            "/sustainability/compare",
            data={"extra": "x" * 20000},
        )

        self.assertEqual(response.status_code, 413)
        self.assertIn("The submission is too large.", response.get_data(as_text=True))

    def test_no_store_header(self):
        for values in (self.sample, {}):
            with self.subTest(values=values):
                response = self.client.post("/sustainability/compare", data=values)
                self.assertEqual(response.headers.get("Cache-Control"), "no-store")

    def test_clear_comparison(self):
        self.client.post("/sustainability/compare", data=self.sample)
        page = self.client.get("/sustainability/compare").get_data(as_text=True)

        self.assertNotIn("Hypothetical comparison results", page)
        self.assertNotIn('value="1000"', page)

    def test_safe_failure_message(self):
        # Simulate an internal failure and check the public error message.
        with patch(
            "app.compare_scenarios",
            side_effect=RuntimeError("INTERNAL_TEST_DETAIL"),
        ):
            response = self.client.post("/sustainability/compare", data=self.sample)

        page = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 500)
        self.assertIn("The comparison could not be calculated.", page)
        self.assertNotIn("INTERNAL_TEST_DETAIL", page)

    def test_navigation_from_every_page(self):
        paths = (
            "/", "/dashboard", "/evaluation",
            "/sustainability", "/sustainability/compare",
        )

        for path in paths:
            with self.subTest(path=path):
                page = self.client.get(path).get_data(as_text=True)
                self.assertIn('href="/sustainability/compare"', page)


if __name__ == "__main__":
    unittest.main()