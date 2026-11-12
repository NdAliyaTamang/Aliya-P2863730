import json
import math
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
source = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "renttherunway_dresses_metric.jsonl"
)

counts = Counter()
high_ages = Counter()

with source.open(encoding="utf-8") as file:
    for line in file:
        if not line.strip():
            continue

        record = json.loads(line)
        counts["total"] += 1

        try:
            age = float(record.get("age", ""))

            if not math.isfinite(age) or age <= 0:
                counts["missing_or_invalid"] += 1
            elif not age.is_integer():
                counts["missing_or_invalid"] += 1
            elif age < 18:
                counts["under_18"] += 1
            else:
                counts["recorded_adult"] += 1

                # Review flag only: these records are not removed.
                if age >= 100:
                    high_ages[int(age)] += 1

        except (ValueError, TypeError):
            counts["missing_or_invalid"] += 1

print("AGE CHECK AFTER DUPLICATE REMOVAL")
print("Total dress records:", counts["total"])
print("Recorded age below 18:", counts["under_18"])
print("Recorded age 18 or above:", counts["recorded_adult"])
print("Missing or invalid age:", counts["missing_or_invalid"])

print("\nRecorded ages of 100 or above — review only:")
if high_ages:
    for age, count in sorted(high_ages.items()):
        print(f"  Age {age}: {count} records")
else:
    print("  None")

print("\nNo records were changed or removed.")