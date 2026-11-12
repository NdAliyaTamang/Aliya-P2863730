import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

source = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "renttherunway_dresses_metric.jsonl"
)

with source.open(encoding="utf-8") as file:
    records = [
        json.loads(line)
        for line in file
        if line.strip()
    ]

# Display the smallest and largest converted measurements.
for field in ["height_cm", "weight_kg"]:
    values = sorted(
        record[field]
        for record in records
        if record.get(field) is not None
    )

    print(f"\n{field}")
    print("Populated records:", len(values))

    if values:
        print("10 smallest values:", values[:10])
        print("10 largest values:", values[-10:])
    else:
        print("No values available.")

# Count records containing both measurements.
complete_count = sum(
    record.get("height_cm") is not None
    and record.get("weight_kg") is not None
    for record in records
)

print("\nRecords with both height and weight:")
print(complete_count)

# Show the original values behind the five lowest weights.
lowest_weight_records = sorted(
    (
        record for record in records
        if record.get("weight_kg") is not None
    ),
    key=lambda record: record["weight_kg"],
)[:5]

print("\nFive lowest-weight records for review:")

for number, record in enumerate(lowest_weight_records, start=1):
    print(f"\nRecord {number}")
    print("Original weight:", record.get("weight"))
    print("Weight in kg:", record.get("weight_kg"))
    print("Original height:", record.get("height"))
    print("Height in cm:", record.get("height_cm"))
    print("Recorded age:", record.get("age"))
    print("Size code:", record.get("size"))
    print("Fit feedback:", record.get("fit"))