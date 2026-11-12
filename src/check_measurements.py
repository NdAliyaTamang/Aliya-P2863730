import json
import math
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
path = PROJECT_ROOT / "dataset" / "renttherunway_final_data.json"

with path.open(encoding="utf-8") as file:
    dresses = [
        json.loads(line)
        for line in file
        if line.strip()
    ]

dresses = [
    record for record in dresses
    if record.get("category") == "dress"
]

ages = []

for record in dresses:
    try:
        age = float(record.get("age", ""))
        if math.isfinite(age) and age > 0:
            ages.append(age)
    except (ValueError, TypeError):
        pass

print("AGE CHECK")
print("Lowest recorded ages:", sorted(set(ages))[:10])
print("Highest recorded ages:", sorted(set(ages))[-10:])
print(
    "Records with fractional ages:",
    sum(not age.is_integer() for age in ages),
)

# Identical values across every field.
row_counts = Counter(
    json.dumps(record, sort_keys=True)
    for record in dresses
)

extra_duplicates = sum(
    count - 1 for count in row_counts.values()
    if count > 1
)

print("\nDUPLICATE CHECK")
print("Extra exact duplicate dress records:", extra_duplicates)

user_counts = Counter(
    record["user_id"]
    for record in dresses
    if record.get("user_id")
)

print("Distinct recorded users:", len(user_counts))
print(
    "Users with multiple dress records:",
    sum(count > 1 for count in user_counts.values()),
)