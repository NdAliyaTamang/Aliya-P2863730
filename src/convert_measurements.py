import json
import re
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
folder = PROJECT_ROOT / "data" / "processed"

source = folder / "renttherunway_dresses_unique.jsonl"
output = folder / "renttherunway_dresses_metric.jsonl"

counts = Counter()


def convert_height(value):
    if value is None or not str(value).strip():
        return None, "missing"

    match = re.fullmatch(
        r"""(\d+)\s*'\s*(\d+)\s*\"""",
        str(value).strip(),
    )

    if not match:
        return None, "invalid"

    feet, inches = map(int, match.groups())

    if inches >= 12 or feet * 12 + inches <= 0:
        return None, "invalid"

    centimetres = (feet * 12 + inches) * 2.54
    return round(centimetres, 2), "converted"


def convert_weight(value):
    if value is None or not str(value).strip():
        return None, "missing"

    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*lbs?",
        str(value).strip(),
        flags=re.IGNORECASE,
    )

    if not match:
        return None, "invalid"

    pounds = float(match.group(1))

    if pounds <= 0:
        return None, "invalid"

    return round(pounds * 0.45359237, 2), "converted"


with source.open(encoding="utf-8") as input_file:
    with output.open("w", encoding="utf-8") as output_file:
        for line in input_file:
            if not line.strip():
                continue

            record = json.loads(line)

            height, height_status = convert_height(
                record.get("height")
            )
            weight, weight_status = convert_weight(
                record.get("weight")
            )

            record["height_cm"] = height
            record["weight_kg"] = weight
            record["height_conversion_status"] = height_status
            record["weight_conversion_status"] = weight_status

            counts["records"] += 1
            counts[f"height_{height_status}"] += 1
            counts[f"weight_{weight_status}"] += 1

            output_file.write(json.dumps(record) + "\n")

print("Records saved:", counts["records"])

for field in ["height", "weight"]:
    print(f"\n{field.upper()}")
    for status in ["converted", "missing", "invalid"]:
        print(f"  {status}: {counts[f'{field}_{status}']}")

print("\nSaved to:", output)