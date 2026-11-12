"""Validate cart contents and calculate illustrative DKK totals.

Cart records contain only product ID, selected sample size and quantity.
Names, prices and stock are always read from the catalogue.
"""

MAX_CART_LINES = 10


def validate_quantity(value):
    """Accept a positive whole-number quantity."""
    text = str(value).strip()

    # Restrict length before converting an untrusted value to an integer.
    if (
        not text
        or len(text) > 2
        or not text.isascii()
        or not text.isdigit()
    ):
        raise ValueError("Quantity must be a positive whole number.")

    quantity = int(text)

    if quantity < 1 or quantity > 99:
        raise ValueError("Quantity must be between 1 and 99.")

    return quantity


def validate_cart(cart, products_by_id):
    """Return clean cart records after validating every line."""
    if not isinstance(cart, list):
        raise ValueError("The cart could not be read. Please clear it.")

    if len(cart) > MAX_CART_LINES:
        raise ValueError("The cart contains too many different items.")

    clean = []
    seen = set()

    for line in cart:
        if not isinstance(line, dict):
            raise ValueError("The cart contains an invalid item.")

        product_id = line.get("product_id")
        size = line.get("size")

        if not isinstance(product_id, str):
            raise ValueError("The cart contains an invalid product ID.")

        product = products_by_id.get(product_id)
        if product is None:
            raise ValueError(
                "A cart product is no longer available. Please clear the cart."
            )

        if not isinstance(size, str) or size not in product["size_stock"]:
            raise ValueError("A cart item has an unsupported size.")

        quantity = validate_quantity(line.get("quantity", ""))

        # Recheck saved cart quantities because stock may have changed since the item was added.
        if quantity > product["size_stock"][size]:
            raise ValueError(
                "A cart quantity exceeds current sample stock. "
                "Remove the item and select an available quantity."
            )

        key = (product_id, size)
        if key in seen:
            raise ValueError("The cart contains a duplicate item.")
        seen.add(key)

        # Discard any extra fields: prices and measurements are not stored.
        clean.append({
            "product_id": product_id,
            "size": size,
            "quantity": quantity,
        })

    return clean


def add_item(cart, products_by_id, product_id, size, quantity):
    """Add a new line or increase an existing line within sample stock."""
    clean = validate_cart(cart, products_by_id)

    if not isinstance(product_id, str):
        raise ValueError("Please select a valid product.")

    product = products_by_id.get(product_id)
    if product is None:
        raise ValueError("The selected product was not found.")

    if not isinstance(size, str) or size not in product["size_stock"]:
        raise ValueError("Please select a supported sample size.")

    quantity = validate_quantity(quantity)
    # Use the stock for the customer's chosen size when checking the new quantity.
    stock = product["size_stock"][size]

    if stock <= 0:
        raise ValueError("The selected sample size is unavailable.")

    for line in clean:
        if line["product_id"] == product_id and line["size"] == size:
            # Repeated additions for the same dress and size share one cart line.
            # Check their combined quantity against the current stock below.
            combined_quantity = line["quantity"] + quantity

            if combined_quantity > stock:
                raise ValueError(
                    "The total quantity in your cart would exceed "
                    "available sample stock."
                )

            line["quantity"] = combined_quantity
            return clean

    if quantity > stock:
        raise ValueError(
            "The requested quantity exceeds available sample stock."
        )

    if len(clean) >= MAX_CART_LINES:
        raise ValueError(
            "Your cart can hold up to 10 different product/size "
            "combinations. Remove an item before adding another."
        )

    clean.append({
        "product_id": product_id,
        "size": size,
        "quantity": quantity,
    })

    return clean


def remove_item(cart, products_by_id, product_id, size):
    """Remove a selected line, including one whose stock has changed."""
    if not isinstance(cart, list):
        raise ValueError("The cart could not be read. Please clear it.")

    remaining = [
        line
        for line in cart
        if not (
            isinstance(line, dict)
            and line.get("product_id") == product_id
            and line.get("size") == size
        )
    ]

    return validate_cart(remaining, products_by_id)


def get_cart_summary(cart, products_by_id):
    """Calculate display values using trusted catalogue prices."""
    clean = validate_cart(cart, products_by_id)

    items = []
    subtotal_minor = 0
    total_quantity = 0

    for line in clean:
        product = products_by_id[line["product_id"]]
        # Use the price from the current catalogue and calculate in integer øre.
        line_total = product["price_minor"] * line["quantity"]

        items.append({
            "product_id": line["product_id"],
            "name": product["name"],
            "size": line["size"],
            "quantity": line["quantity"],
            "price_minor": product["price_minor"],
            "line_total_minor": line_total,
        })

        subtotal_minor += line_total
        total_quantity += line["quantity"]

    return {
        "items": items,
        "subtotal_minor": subtotal_minor,
        "total_quantity": total_quantity,
    }