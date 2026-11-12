"""Generate varied illustrative products for model-supported dataset IDs.

All shopping attributes are fictional and are not inferred from the model.
Generation is deterministic: the same ID receives the same details.
"""

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ml_model.model import get_supported_options


OUTPUT_PATH = (
    PROJECT_ROOT / "data" / "catalogue" / "display_products.json"
)

# Style-specific choices avoid arbitrary combinations of every attribute.
STYLE_PROFILES = [
    {
        "style": "Wrap",
        "lengths": ["Mini", "Midi", "Maxi"],
        "occasions": [
            ["Casual"],
            ["Work"],
            ["Casual", "Work"],
            ["Wedding guest"],
        ],
        "base_price": 599,
    },
    {
        "style": "A-line",
        "lengths": ["Mini", "Midi", "Maxi"],
        "occasions": [
            ["Casual"],
            ["Work"],
            ["Wedding guest"],
            ["Evening", "Wedding guest"],
        ],
        "base_price": 649,
    },
    {
        "style": "Shirt dress",
        "lengths": ["Mini", "Midi"],
        "occasions": [
            ["Casual"],
            ["Work"],
            ["Casual", "Work"],
        ],
        "base_price": 549,
    },
    {
        "style": "Bodycon",
        "lengths": ["Mini", "Midi"],
        "occasions": [
            ["Evening"],
            ["Party"],
            ["Evening", "Party"],
        ],
        "base_price": 599,
    },
    {
        "style": "Slip",
        "lengths": ["Midi", "Maxi"],
        "occasions": [
            ["Evening"],
            ["Wedding guest"],
            ["Evening", "Wedding guest"],
        ],
        "base_price": 699,
    },
    {
        "style": "Shift",
        "lengths": ["Mini", "Midi"],
        "occasions": [
            ["Casual"],
            ["Work"],
            ["Casual", "Work"],
        ],
        "base_price": 449,
    },
    {
        "style": "Fit and flare",
        "lengths": ["Mini", "Midi"],
        "occasions": [
            ["Casual"],
            ["Party"],
            ["Wedding guest"],
        ],
        "base_price": 649,
    },
    {
        "style": "Sheath",
        "lengths": ["Midi"],
        "occasions": [
            ["Work"],
            ["Evening"],
            ["Work", "Evening"],
        ],
        "base_price": 749,
    },
    {
        "style": "Empire waist",
        "lengths": ["Midi", "Maxi"],
        "occasions": [
            ["Casual"],
            ["Wedding guest"],
            ["Evening"],
        ],
        "base_price": 699,
    },
    {
        "style": "Smock",
        "lengths": ["Mini", "Midi"],
        "occasions": [
            ["Casual"],
            ["Holiday"],
            ["Casual", "Holiday"],
        ],
        "base_price": 499,
    },
]

COLOURS = [
    "Black",
    "Navy",
    "Rose",
    "Ivory",
    "Sage",
    "Blue",
    "Burgundy",
    "Emerald",
    "Lavender",
    "Chocolate",
    "Terracotta",
    "Teal",
    "Plum",
    "Champagne",
    "Coral",
    "Olive",
]

NAME_PREFIXES = [
    "Alba",
    "Clara",
    "Freya",
    "Liv",
    "Nora",
    "Sofia",
    "Thea",
    "Vera",
    "Ingrid",
    "Maja",
    "Elise",
    "Astrid",
]

SIZES = ("XS", "S", "M", "L", "XL")

# Each price is an illustrative amount in whole DKK before conversion.
PRICE_ADJUSTMENTS = (-100, -50, 0, 50, 100, 150, 200)
LENGTH_ADJUSTMENTS = {"Mini": 0, "Midi": 50, "Maxi": 150}


def stable_number(item_id, attribute):
    """Produce an independent, repeatable number for each attribute."""
    text = f"ownablefit-display-v2:{item_id}:{attribute}"
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest, "big")


def choose(options, item_id, attribute):
    """Choose deterministically without using global random state."""
    return options[stable_number(item_id, attribute) % len(options)]


def build_product(item_id):
    """Build one fictional presentation for an original dataset ID."""
    profile = choose(STYLE_PROFILES, item_id, "style")
    length = choose(profile["lengths"], item_id, "length")
    occasions = choose(profile["occasions"], item_id, "occasion")
    colour = choose(COLOURS, item_id, "colour")
    prefix = choose(NAME_PREFIXES, item_id, "name")

    price_dkk = (
        profile["base_price"]
        + LENGTH_ADJUSTMENTS[length]
        + choose(PRICE_ADJUSTMENTS, item_id, "price")
    )

    stock = {
        size: stable_number(item_id, f"stock-{size}") % 8
        for size in SIZES
    }

    # Keep at least one sample size available on each generated item.
    if not any(stock.values()):
        stock[choose(SIZES, item_id, "fallback-size")] = 1

    # The ID suffix makes names distinct without claiming a real collection.
    name = (
        f'{prefix} {colour} {length} {profile["style"]} Dress'
        f" · {item_id}"
    )

    return {
        "product_id": f"DISPLAY-{item_id}",
        "model_item_id": item_id,
        "name": name,
        "dress_style": profile["style"],
        "length": length,
        "occasions": list(occasions),
        "colour": colour,
        "price_minor": price_dkk * 100,
        "size_stock": stock,
        "is_sample": True,
        "attributes_source": "fictional_display_template",
        "model_link_scope": "dataset_id_only",
    }


def build_display_catalogue():
    """Generate and validate the catalogue before replacing its file."""
    dress_ids, _ = get_supported_options()

    if not dress_ids:
        raise ValueError("The saved model contains no supported dress IDs.")

    if len(dress_ids) != len(set(dress_ids)):
        raise ValueError("Duplicate model dress IDs were found.")

    products = [
        build_product(item_id)
        for item_id in sorted(dress_ids)
    ]

    if len({p["name"] for p in products}) != len(products):
        raise ValueError("Generated product names are not unique.")

    if {p["model_item_id"] for p in products} != set(dress_ids):
        raise ValueError("Generated IDs do not match the model.")

    # Check that generation produces the same record for the same ID.
    if build_product(dress_ids[0]) != build_product(dress_ids[0]):
        raise ValueError("Product generation is not reproducible.")

    catalogue = {
        "schema_version": 1,
        "generator_version": 2,
        "catalogue_kind": "illustrative_model_item_display",
        "currency": "DKK",
        "description": (
            "Real model-known dataset IDs with fictional shopping "
            "attributes. Names, styles, lengths, colours, occasions, "
            "prices and stock are not verified for the original items."
        ),
        "size_notice": (
            "Sample XS–XL stock labels have no verified mapping "
            "to predicted dataset size codes."
        ),
        "prediction_notice": (
            "Predictions concern the original dataset item ID only. "
            "They do not validate the fictional product presentation."
        ),
        "products": products,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = OUTPUT_PATH.with_suffix(".tmp")
    with temporary_path.open("w", encoding="utf-8") as destination:
        json.dump(catalogue, destination, indent=2, ensure_ascii=False)
        destination.write("\n")

    temporary_path.replace(OUTPUT_PATH)

    print("Varied display catalogue created successfully.")
    print("Products:", len(products))
    print("Unique display names:", len({p["name"] for p in products}))
    print("Colours:", len({p["colour"] for p in products}))
    print("Price points:", len({p["price_minor"] for p in products}))

    print("\nStyle distribution:")
    for style, count in sorted(
        Counter(p["dress_style"] for p in products).items()
    ):
        print(f"  {style}: {count}")

    print("\nSaved to:", OUTPUT_PATH.relative_to(PROJECT_ROOT))
    print("All shopping attributes remain fictional.")
    print("The trained model and original dataset were not changed.")


if __name__ == "__main__":
    build_display_catalogue()