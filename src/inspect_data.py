import json
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_FOLDER = PROJECT_ROOT / "dataset"

datasets = {
    "renttherunway_final_data.json": {
        "category": "dress",
        "measurements": [
            "height", "weight", "bust size", "age", "size", "fit"
        ],
    },
    "modcloth_final_data.json": {
        "category": "dresses",
        "measurements": [
            "height", "bust", "waist", "hips",
            "bra size", "cup size", "size", "fit"
        ],
    },
}

for filename, settings in datasets.items():
    path = DATASET_FOLDER / filename
    print(f"\nDATASET: {filename}")

    if not path.is_file():
        print(f"NOT FOUND: {path}")
        continue

    with path.open(encoding="utf-8") as file:
        records = [
            json.loads(line)
            for line in file
            if line.strip()
        ]

    dresses = [
        record for record in records
        if record.get("category") == settings["category"]
    ]

    print("Total records:", len(records))
    print("Explicit dress records:", len(dresses))

    print("\nDress fit feedback:")
    fit_counts = Counter(
        record.get("fit") for record in dresses
    )
    for label, count in fit_counts.most_common():
        print(f"  {label}: {count:,}")

    print("\nMissing values in dress records:")
    for field in settings["measurements"]:
        missing = sum(
            record.get(field) is None
            or str(record.get(field)).strip().lower()
            in {"", "nan", "none", "null"}
            for record in dresses
        )

        percentage = (
            missing / len(dresses) * 100
            if dresses else 0
        )

        print(
            f"  {field}: {missing:,} missing "
            f"({percentage:.1f}%)"
        )

    print("\nDress size labels and record counts:")
    size_counts = Counter(
        record.get("size") for record in dresses
    )
    for size, count in size_counts.most_common():
        print(f"  {size}: {count:,}")