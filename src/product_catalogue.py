"""Load and filter OwnableFit's illustrative shopping catalogues.

Shopping attributes and stock are fictional.
Model-linked display records identify original dataset items only.
Prices use integer øre; 100 øre = 1 DKK.
"""

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOGUE_DIR = PROJECT_ROOT / "data" / "catalogue"

SORT_OPTIONS = {
    "name_asc": "Name: A–Z",
    "price_asc": "Price: low to high",
    "price_desc": "Price: high to low",
}

SIZE_ORDER = ("XS", "S", "M", "L", "XL")


def read_catalogue(path, allow_model_links=False):
    """Read and validate catalogue records without changing them."""
    with path.open(encoding="utf-8") as source:
        catalogue = json.load(source)

    if catalogue.get("currency") != "DKK":
        raise ValueError("The catalogue must use DKK.")

    products = catalogue.get("products")
    if not isinstance(products, list):
        raise ValueError("The catalogue must contain a products list.")

    seen_ids = set()
    seen_model_ids = set()

    for product in products:
        if not isinstance(product, dict):
            raise ValueError("Each product must be an object.")

        for field in (
            "product_id",
            "name",
            "dress_style",
            "length",
            "colour",
        ):
            value = product.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Each product needs a valid {field}.")

        product_id = product["product_id"]

        if product_id in seen_ids:
            raise ValueError(f"Duplicate product ID: {product_id}")
        seen_ids.add(product_id)

        price = product.get("price_minor")
        if type(price) is not int or price < 0:
            raise ValueError(
                f"Price must be non-negative integer øre: {product_id}"
            )

        occasions = product.get("occasions")
        if (
            not isinstance(occasions, list)
            or not occasions
            or any(
                not isinstance(value, str) or not value.strip()
                for value in occasions
            )
        ):
            raise ValueError(f"Invalid occasions: {product_id}")

        stock = product.get("size_stock")
        if not isinstance(stock, dict) or not stock:
            raise ValueError(f"Invalid size stock: {product_id}")

        for size, quantity in stock.items():
            if (
                not isinstance(size, str)
                or not size.strip()
                or type(quantity) is not int
                or quantity < 0
            ):
                raise ValueError(f"Invalid size stock: {product_id}")

        if product.get("is_sample") is not True:
            raise ValueError(
                f"Illustrative attributes must be labelled: {product_id}"
            )

        model_id = product.get("model_item_id")

        if allow_model_links:
            if not isinstance(model_id, str) or not model_id.strip():
                raise ValueError(f"Missing model item ID: {product_id}")

            if model_id in seen_model_ids:
                raise ValueError(f"Duplicate model item ID: {model_id}")
            seen_model_ids.add(model_id)

            if product.get("model_link_scope") != "dataset_id_only":
                raise ValueError(
                    f"Missing model-link scope: {product_id}"
                )

            if (
                product.get("attributes_source")
                != "fictional_display_template"
            ):
                raise ValueError(
                    f"Unexpected attribute source: {product_id}"
                )

        elif model_id is not None:
            raise ValueError(
                f"Standalone sample products cannot have model links: "
                f"{product_id}"
            )

    return products


def load_products():
    """Load the original eight standalone sample products."""
    return read_catalogue(
        CATALOGUE_DIR / "sample_products.json",
        allow_model_links=False,
    )


def load_display_products():
    """Load display records and verify their IDs against the model."""
    from ml_model.model import get_supported_options

    products = read_catalogue(
        CATALOGUE_DIR / "display_products.json",
        allow_model_links=True,
    )

    dress_ids, _ = get_supported_options()

    linked_ids = {p["model_item_id"] for p in products}
    supported_ids = set(dress_ids)

    # Verify that the original catalogue covers the same dress IDs as the model.
    if linked_ids != supported_ids:
        raise ValueError(
            "Display catalogue IDs do not match the saved model. "
            "Run src/build_display_catalogue.py again."
        )

    return products


def format_dkk(price_minor):
    """Format integer øre without floating-point arithmetic."""
    return f"{price_minor // 100:,}.{price_minor % 100:02d} DKK"


def price_to_minor(value, label):
    """Convert an optional DKK filter to integer øre."""
    text = str(value or "").strip()

    if not text:
        return None

    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise ValueError(f"{label} must be a valid DKK amount.") from None

    if not amount.is_finite() or amount < 0:
        raise ValueError(f"{label} must be finite and non-negative.")

    if amount > Decimal("1000000000"):
        raise ValueError(
            f"{label} must not exceed 1,000,000,000 DKK."
        )

    minor = amount * 100

    if minor != minor.to_integral_value():
        raise ValueError(
            f"{label} can have at most two decimal places."
        )

    return int(minor)


def get_filter_options(products):
    """Build choices from catalogue attributes and positive sample stock."""
    available_sizes = {
        size
        for product in products
        for size, quantity in product["size_stock"].items()
        if quantity > 0
    }

    ordered_sizes = [
        size for size in SIZE_ORDER if size in available_sizes
    ]
    ordered_sizes.extend(sorted(available_sizes - set(SIZE_ORDER)))

    return {
        "styles": sorted({p["dress_style"] for p in products}),
        "lengths": sorted({p["length"] for p in products}),
        "occasions": sorted({
            occasion
            for product in products
            for occasion in product["occasions"]
        }),
        "colours": sorted({p["colour"] for p in products}),
        "sizes": ordered_sizes,
    }


def filter_products(products, filters):
    """Apply combined filters and return a deterministically sorted list."""
    query = str(filters.get("q", "")).strip().casefold()

    minimum = price_to_minor(
        filters.get("min_price", ""),
        "Minimum price",
    )
    maximum = price_to_minor(
        filters.get("max_price", ""),
        "Maximum price",
    )

    if minimum is not None and maximum is not None:
        if minimum > maximum:
            raise ValueError(
                "Minimum price must not exceed maximum price."
            )

    matches = []

    for product in products:
        # Search by name, display product ID or original model item ID.
        searchable = " ".join((
            product["name"],
            product["product_id"],
            product.get("model_item_id") or "",
        )).casefold()

        if query and query not in searchable:
            continue

        if filters.get("style"):
            if product["dress_style"] != filters["style"]:
                continue

        if filters.get("length"):
            if product["length"] != filters["length"]:
                continue

        if filters.get("occasion"):
            if filters["occasion"] not in product["occasions"]:
                continue

        if filters.get("colour"):
            if product["colour"] != filters["colour"]:
                continue

        # A dress matches a requested size only if that size has positive stock.
        if filters.get("size"):
            if product["size_stock"].get(filters["size"], 0) <= 0:
                continue

        if minimum is not None and product["price_minor"] < minimum:
            continue

        if maximum is not None and product["price_minor"] > maximum:
            continue

        matches.append(product)

    sort_order = filters.get("sort", "name_asc")

    # Product ID breaks ties so pagination stays consistent.
    if sort_order == "price_asc":
        matches.sort(key=lambda p: (
            p["price_minor"],
            p["name"].casefold(),
            p["product_id"],
        ))
    elif sort_order == "price_desc":
        matches.sort(key=lambda p: (
            -p["price_minor"],
            p["name"].casefold(),
            p["product_id"],
        ))
    else:
        matches.sort(key=lambda p: (
            p["name"].casefold(),
            p["product_id"],
        ))

    return matches


if __name__ == "__main__":
    # Import project modules when this file is run directly.
    import sys

    sys.path.insert(0, str(PROJECT_ROOT))

    products = load_display_products()
    options = get_filter_options(products)

    print("Display catalogue loaded:", len(products), "products")
    print("All linked IDs match the saved model.")
    print("Currency: DKK")
    print("Styles:", ", ".join(options["styles"]))
    print("Available sample sizes:", ", ".join(options["sizes"]))

    cheapest = filter_products(products, {"sort": "price_asc"})[0]
    print("Lowest sample price:", format_dkk(cheapest["price_minor"]))
    print("Shopping attributes remain fictional.")