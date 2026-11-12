import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
source = PROJECT_ROOT / "dataset" / "renttherunway_final_data.json"

output_folder = PROJECT_ROOT / "data" / "processed"
output_folder.mkdir(parents=True, exist_ok=True)
output = output_folder / "renttherunway_dresses_unique.jsonl"

seen = set()
dress_count = 0
duplicate_count = 0
unique_records = []

with source.open(encoding="utf-8") as file:
    for line in file:
        if not line.strip():
            continue

        record = json.loads(line)

        if record.get("category") != "dress":
            continue

        dress_count += 1
        key = json.dumps(record, sort_keys=True)

        if key in seen:
            duplicate_count += 1
            continue

        seen.add(key)
        unique_records.append(record)

with output.open("w", encoding="utf-8") as file:
    for record in unique_records:
        file.write(json.dumps(record) + "\n")

print("Original dress records:", dress_count)
print("Extra duplicates removed:", duplicate_count)
print("Unique dress records saved:", len(unique_records))
print("Saved to:", output)