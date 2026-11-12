import numpy as np
import pandas as pd

def prepare_item_inputs(frame):
    """Format raw customer and dress inputs for the saved pipeline."""
    required = ["height_cm", "weight_kg", "bra_size", "item_id"]

    missing = set(required).difference(frame.columns)
    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    inputs = frame[
        ["height_cm", "weight_kg", "bra_size"]
    ].copy()

    # Match the notebook's numeric conversion.
    for column in ["height_cm", "weight_kg"]:
        inputs[column] = pd.to_numeric(
            inputs[column], errors="coerce"
        ).astype("float64")

    # Match the bra-size normalisation used during preparation.
    bra_size = (
        inputs["bra_size"]
        .astype("string")
        .str.strip()
        .str.lower()
        .replace("", pd.NA)
    )
    inputs["bra_size"] = bra_size.astype(object).where(
        bra_size.notna(), np.nan
    )

    # IDs are categorical: preserve the original ID text.
    # Supply 123 rather than the floating-point representation 123.0.
    item_text = frame["item_id"].astype("string")
    inputs["dress_item"] = ("item_" + item_text).astype(object)
    inputs["dress_item"] = inputs["dress_item"].where(
        item_text.notna(), np.nan
    )

    return inputs
