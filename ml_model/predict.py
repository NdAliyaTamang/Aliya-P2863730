"""Validate form inputs and predict using the existing exported model."""

import math
import sys

import pandas as pd

from ml_model.model import EXPORT_DIR, get_supported_options, load_model

# Import the same exported helper used by your successful model check.
sys.path.insert(0, str(EXPORT_DIR))
from input_preparation import prepare_item_inputs


def positive_number(value, label):
    """Accept only finite, positive measurements."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number.") from None

    # Reject zero, negatives, infinity and NaN.
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{label} must be a finite number greater than zero.")

    return number


def predict_size(form):
    """Return one dataset size code without storing submitted measurements."""
    dress_ids, bra_sizes = get_supported_options()

    # Read IDs as text to preserve the model's categorical representation.
    item_id = str(form.get("item_id", "")).strip()
    bra_size = str(form.get("bra_size", "")).strip().lower()

    # Validate on the server even though the browser has dropdowns.
    if item_id not in dress_ids:
        raise ValueError("Please select a supported dress ID.")

    if bra_size not in bra_sizes:
        raise ValueError("Please select a supported bra-size category.")

    # Reject non-numeric, non-finite and non-positive measurements before prediction.
    height_cm = positive_number(form.get("height_cm"), "Height")
    weight_kg = positive_number(form.get("weight_kg"), "Weight")

    # Keep inputs in memory only; do not print or save measurements.
    raw_inputs = pd.DataFrame([{
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "bra_size": bra_size,
        "item_id": item_id,
    }])

    # Reuse exported preprocessing rather than recreating it.
    # Format the submitted values and columns to match the saved model's inputs.
    prepared_inputs = prepare_item_inputs(raw_inputs)
    # The saved pipeline applies its fitted transformations and classifier.
    # Prediction uses the existing fitted model without retraining it.
    prediction = load_model().predict(prepared_inputs)

    # Return the original dataset code without size conversion.
    return int(prediction[0])