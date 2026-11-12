"""Test dataset dress-ID browsing and shopping navigation."""

import unittest
from html.parser import HTMLParser
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from app import dress_ids

# Load the full website, including the routes used by shared navigation.
from run import app


class CatalogueParser(HTMLParser):
    """Extract dress selection links and the recommendation form's dress ID."""

    def __init__(self):
        super().__init__()
        self.selection_links = []
        self.dress_value = None

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)

        if tag == "a":
            href = attributes.get("href", "")
            query = parse_qs(urlsplit(href).query)

            if "item_id" in query:
                self.selection_links.append(href)

        if tag == "input" and attributes.get("id") == "item_id":
            self.dress_value = attributes.get("value", "")


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.known_id = dress_ids[0]

        # Build the expected order independently of the catalogue route.
        self.ordered_ids = sorted(
            dress_ids,
            key=lambda value: (
                (0, int(value), value)
                if value.isascii() and value.isdigit()
                else (1, 0, value)
            ),
        )

    def parse_page(self, response):
        parser = CatalogueParser()
        parser.feed(response.get_data(as_text=True))
        return parser

    def selected_ids(self, response):
        """Read dress IDs from the links actually rendered on the page."""
        return [
            parse_qs(urlsplit(link).query)["item_id"][0]
            for link in self.parse_page(response).selection_links
        ]

    def test_catalogue_loads(self):
        response = self.client.get("/catalogue")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")

    def test_first_page_contains_supported_ids(self):
        response = self.client.get("/catalogue")
        self.assertEqual(self.selected_ids(response), self.ordered_ids[:12])

    def test_second_page_contains_next_ids(self):
        response = self.client.get("/catalogue?page=2")
        self.assertEqual(self.selected_ids(response), self.ordered_ids[12:24])

    def test_search_results_match_query(self):
        query = self.known_id
        expected = [value for value in self.ordered_ids if query in value][:12]

        response = self.client.get("/catalogue", query_string={"q": query})

        self.assertEqual(self.selected_ids(response), expected)

    def test_no_matching_results(self):
        response = self.client.get(
            "/catalogue",
            query_string={"q": "not-a-dress"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("No matching dress IDs", response.get_data(as_text=True))
        self.assertEqual(self.selected_ids(response), [])

    def test_invalid_page_returns_first_page(self):
        for value in ("abc", "0", "-10"):
            with self.subTest(page=value):
                response = self.client.get(
                    "/catalogue",
                    query_string={"page": value},
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.selected_ids(response), self.ordered_ids[:12])

    def test_large_page_returns_last_page(self):
        response = self.client.get("/catalogue?page=999999")

        # Find the starting index of the final page, which may have fewer items.
        start = ((len(self.ordered_ids) - 1) // 12) * 12
        self.assertEqual(self.selected_ids(response), self.ordered_ids[start:])

    def test_selection_link_prefills_form(self):
        response = self.client.get(
            "/catalogue",
            query_string={"q": self.known_id},
        )
        link = self.parse_page(response).selection_links[0]
        form_response = self.client.get(link)

        self.assertEqual(form_response.status_code, 200)
        self.assertEqual(self.parse_page(form_response).dress_value, self.known_id)

    def test_unknown_selection_rejected(self):
        response = self.client.get("/", query_string={"item_id": "not-a-dress"})

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Please select a supported dress ID.",
            response.get_data(as_text=True),
        )
        self.assertEqual(self.parse_page(response).dress_value, "")

    def test_result_identifies_submitted_dress(self):
        # Use a fixed prediction to test what the page displays.
        with patch("app.predict_size", return_value=8):
            response = self.client.post("/", data={
                "item_id": self.known_id,
                "height_cm": "165",
                "weight_kg": "62",
                "bra_size": "34b",
            })

        page = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(f"For dress ID {self.known_id}", page)
        self.assertIn("<strong>8</strong>", page)

    def test_search_text_is_escaped(self):
        """Check that HTML in a search term is displayed as plain text."""
        response = self.client.get(
            "/catalogue",
            query_string={"q": "<script>alert(1)</script>"},
        )
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_catalogue_link_on_all_pages(self):
        # The customer-facing Dress catalogue link leads to the shop.
        paths = (
            "/", "/dashboard", "/evaluation", "/sustainability",
            "/sustainability/compare", "/catalogue", "/shop", "/cart",
        )

        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn('href="/shop"', response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()