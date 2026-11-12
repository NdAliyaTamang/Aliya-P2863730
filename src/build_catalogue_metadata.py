"""Build item-category metadata for the OwnableFit catalogue.

Read only item IDs and category labels from the original dataset.
Do not train the model or export customer records.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


# Allow this script to import project modules when run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ml_model.model import get_supported_options


SOURCE_PATH = (
    PROJECT_ROOT / "dataset" / "renttherunway_final_data.json"
)
OUTPUT_PATH = (
    PROJECT_ROOT / "data" / "catalogue" / "dress_metadata.json"
)


def build_catalogue_metadata():
    """Match model-supported IDs to their recorded category labels."""
    if not SOURCE_PATH.is_file():
        raise FileNotFoundError(
            f"Original dataset not found: {SOURCE_PATH}"
        )

    dress_ids, _ = get_supported_options()
    supported_ids = set(dress_ids)

    # Keep distinct labels rather than choosing the most frequent one.
    # Conflicting source categories should remain visible as uncertainty.
    categories_by_item = defaultdict(set)

    with SOURCE_PATH.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                raise ValueError(
                    f"Invalid JSON on dataset line {line_number}."
                ) from None

            if not isinstance(record, dict):
                raise ValueError(
                    f"Expected an object on dataset line {line_number}."
                )

            raw_id = record.get("item_id")
            if raw_id is None:
                continue

            item_id = str(raw_id).strip()
            if item_id not in supported_ids:
                continue

            category = record.get("category")

            if isinstance(category, str) and category.strip():
                categories_by_item[item_id].add(
                    category.strip().lower()
                )

    items = []
    status_counts = Counter()
    category_counts = Counter()

    for item_id in dress_ids:
        labels = sorted(categories_by_item[item_id])

        if len(labels) == 1:
            status = "single_recorded_category"
            category = labels[0]
            category_counts[category] += 1
        elif len(labels) > 1:
            status = "conflicting_categories"
            category = None
        else:
            status = "category_unavailable"
            category = None

        status_counts[status] += 1

        items.append({
            "item_id": item_id,
            "category": category,
            "category_status": status,
            "recorded_categories": labels,
        })

    output = {
        "schema_version": 1,
        "source": "dataset/renttherunway_final_data.json",
        "scope": "Only item IDs supported by the saved model",
        "description": (
            "Dataset-recorded categories, not independently verified "
            "retail product classifications."
        ),
        "items": items,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Replace the derived file only after processing finishes successfully.
    temporary_path = OUTPUT_PATH.with_suffix(".tmp")
    with temporary_path.open("w", encoding="utf-8") as destination:
        json.dump(output, destination, indent=2, ensure_ascii=False)
        destination.write("\n")

    temporary_path.replace(OUTPUT_PATH)

    print("Catalogue metadata created successfully.")
    print("Model-supported items:", len(items))
    print(
        "Items with one recorded category:",
        status_counts["single_recorded_category"],
    )
    print(
        "Items with conflicting categories:",
        status_counts["conflicting_categories"],
    )
    print(
        "Items without a category:",
        status_counts["category_unavailable"],
    )

    print("\nRecorded category counts:")
    for category, count in sorted(category_counts.items()):
        print(f"  {category}: {count}")

    print("\nSaved to:", OUTPUT_PATH.relative_to(PROJECT_ROOT))
    print("No measurements, reviews or customer IDs were exported.")


if __name__ == "__main__":
    build_catalogue_metadata()