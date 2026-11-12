"""Check local input preparation and prediction without retraining."""

from pathlib import Path
import sys

import joblib
import pandas as pd

# Locate the export relative to this script, not the terminal directory.
project_root = Path(__file__).resolve().parents[1]
export_dir = project_root / "models" / "ownablefit_export"

sys.path.insert(0, str(export_dir))
from input_preparation import prepare_item_inputs

model = joblib.load(export_dir / "ownablefit_pipeline.joblib")

# Choose a dress ID actually learned by the fitted encoder.
# This is a technical check, not a real customer recommendation.
encoder = (
    model.named_steps["preprocessing"]
    .named_transformers_["categorical"]
    .named_steps["encoder"]
)

# Categorical columns were ordered as bra_size, then dress_item.
known_item = next(
    str(value)
    for value in encoder.categories_[1]
    if str(value).startswith("item_")
)
item_id = known_item.removeprefix("item_")

# Illustrative inputs; no claim is made about their correct size.
sample = pd.DataFrame([{
    "height_cm": 165.0,
    "weight_kg": 62.0,
    "bra_size": "34b",
    "item_id": item_id
}])

prepared = prepare_item_inputs(sample)
prediction = model.predict(prepared)

print("Input preparation and prediction succeeded.")
print("Dress item ID:", item_id)
print("Predicted dataset size code:", int(prediction[0]))
print("This is a technical check, not verified fit advice.")