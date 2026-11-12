import json
import math
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
folder = PROJECT_ROOT / "data" / "processed"

source = folder / "renttherunway_dresses_metric.jsonl"
adult_output = folder / "renttherunway_dresses_adult.jsonl"
other_output = folder / "renttherunway_dresses_age_unconfirmed.jsonl"

counts = Counter()

with (
    source.open(encoding="utf-8") as input_file,
    adult_output.open("w", encoding="utf-8") as adult_file,
    other_output.open("w", encoding="utf-8") as other_file,
):
    for line in input_file:
        if not line.strip():
            continue

        record = json.loads(line)
        counts["total"] += 1
        age = None

        try:
            value = float(record.get("age", ""))
            if (
                math.isfinite(value)
                and value > 0
                and value.is_integer()
            ):
                age = int(value)
        except (ValueError, TypeError):
            pass

        record["age_years"] = age
        record["age_review_required"] = (
            age is not None and age >= 100
        )

        if age is None:
            record["age_eligibility"] = "unknown"
            other_file.write(json.dumps(record) + "\n")
            counts["unknown"] += 1

        elif age < 18:
            record["age_eligibility"] = "recorded_under_18"
            other_file.write(json.dumps(record) + "\n")
            counts["under_18"] += 1

        else:
            record["age_eligibility"] = "recorded_adult"
            adult_file.write(json.dumps(record) + "\n")
            counts["adult"] += 1

            if record["age_review_required"]:
                counts["adult_review"] += 1

print("Source records:", counts["total"])
print("Recorded adult records saved:", counts["adult"])
print("Adult records flagged for age review:", counts["adult_review"])
print("Recorded under 18 saved separately:", counts["under_18"])
print("Unknown age saved separately:", counts["unknown"])
print("\nAdult file:", adult_output)
print("Other records:", other_output)