"""Test the single-scenario sustainability calculation and its web form.

All inputs are hypothetical technical examples.
"""

import unittest

from src.sustainability import calculate_scenario

# Load the same Flask entry point used to run the website.
from run import app


class SustainabilityCalculationTests(unittest.TestCase):
    """Check the calculation without submitting a web form."""

    def test_example_calculation(self):
        result = calculate_scenario(1000, 20, 10, 1)

        self.assertAlmostEqual(result["baseline_returns"], 200)
        self.assertAlmostEqual(result["avoided_returns"], 20)
        self.assertAlmostEqual(result["remaining_returns"], 180)
        self.assertAlmostEqual(result["potential_kg_co2e_saved"], 20)

    def test_relative_reduction(self):
        """A 10% relative reduction in a 20% return rate leaves 18%."""
        result = calculate_scenario(1000, 20, 10, 1)
        remaining_rate = result["remaining_returns"] / 1000 * 100

        self.assertAlmostEqual(remaining_rate, 18)

    def test_zero_reduction(self):
        result = calculate_scenario(1000, 20, 0, 1)

        self.assertEqual(result["avoided_returns"], 0)
        self.assertEqual(result["potential_kg_co2e_saved"], 0)
        self.assertEqual(result["remaining_returns"], 200)

    def test_full_reduction(self):
        result = calculate_scenario(1000, 20, 100, 1)

        self.assertEqual(result["avoided_returns"], 200)
        self.assertEqual(result["remaining_returns"], 0)

    def test_zero_orders(self):
        result = calculate_scenario(0, 20, 10, 1)

        for value in result.values():
            self.assertEqual(value, 0)

    def test_invalid_assumptions(self):
        base = {
            "orders": 1000,
            "size_return_rate_percent": 20,
            "relative_reduction_percent": 10,
            "kg_co2e_per_return": 1,
        }
        invalid_values = {
            "orders": (-1, 1.5, "abc", "nan", "inf"),
            "size_return_rate_percent": (-1, 101, "", "nan", "inf"),
            "relative_reduction_percent": (-1, 101, "", "nan", "inf"),
            "kg_co2e_per_return": (-1, "", "abc", "nan", "inf"),
        }

        # Change one assumption at a time to isolate its validation.
        for field, values in invalid_values.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        calculate_scenario(**{**base, field: value})

    def test_arithmetic_overflow(self):
        """Reject inputs whose calculation would produce a non-finite result."""
        with self.assertRaises(ValueError):
            calculate_scenario(1e308, 100, 100, 1e308)


class SustainabilityPageTests(unittest.TestCase):
    """Check requests through Flask without starting a server."""

    def setUp(self):
        self.client = app.test_client()
        self.sample = {
            "orders": "1000",
            "return_rate": "20",
            "reduction": "10",
            "impact": "1",
        }

    def test_page_loads_without_result(self):
        response = self.client.get("/sustainability")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Hypothetical scenario result", page)

    def test_valid_submission(self):
        response = self.client.post("/sustainability", data=self.sample)
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Hypothetical scenario result", page)
        self.assertIn("200.00", page)
        self.assertIn("180.00", page)
        self.assertIn("20.00", page)

        # The original inputs remain visible alongside the calculated result.
        self.assertIn('value="1000"', page)
        self.assertIn('value="10"', page)

    def test_missing_fields(self):
        for field in self.sample:
            with self.subTest(field=field):
                values = self.sample.copy()
                del values[field]

                response = self.client.post("/sustainability", data=values)
                page = response.get_data(as_text=True)

                self.assertEqual(response.status_code, 400)
                self.assertIn("Unable to calculate", page)
                self.assertNotIn("Hypothetical scenario result", page)

    def test_invalid_percentage(self):
        response = self.client.post(
            "/sustainability",
            data={**self.sample, "reduction": "101"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn(
            "Hypothetical scenario result",
            response.get_data(as_text=True),
        )

    def test_oversized_submission(self):
        response = self.client.post(
            "/sustainability",
            data={"extra": "x" * 20000},
        )

        self.assertEqual(response.status_code, 413)
        self.assertIn("The submission is too large.", response.get_data(as_text=True))

    def test_no_store_header(self):
        for values in (self.sample, {}):
            with self.subTest(values=values):
                response = self.client.post("/sustainability", data=values)
                self.assertEqual(response.headers.get("Cache-Control"), "no-store")

    def test_clear_scenario(self):
        self.client.post("/sustainability", data=self.sample)
        page = self.client.get("/sustainability").get_data(as_text=True)

        self.assertNotIn("Hypothetical scenario result", page)
        self.assertNotIn('value="1000"', page)

    def test_navigation_from_all_pages(self):
        for path in ("/", "/dashboard", "/evaluation", "/sustainability"):
            with self.subTest(path=path):
                page = self.client.get(path).get_data(as_text=True)
                self.assertIn('href="/sustainability"', page)


if __name__ == "__main__":
    unittest.main()