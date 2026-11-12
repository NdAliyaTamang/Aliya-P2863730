"""Load the saved OwnableFit pipeline and its supported categories.

This module does not train or modify the model.
"""

from functools import lru_cache
from pathlib import Path

import joblib


# Locate the export independently of the terminal's current folder.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = PROJECT_ROOT / "models" / "ownablefit_export"
MODEL_PATH = EXPORT_DIR / "ownablefit_pipeline.joblib"


@lru_cache(maxsize=1)
def load_model():
    """Load the pipeline once per running Python process."""
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            "The saved model was not found. Expected location: "
            f"{MODEL_PATH}"
        )

    # Load only the trusted model exported by this project.
    return joblib.load(MODEL_PATH)


def get_supported_options():
    """Return dress IDs and bra-size categories learned by the model."""
    # Read supported dress and bra-size categories from the fitted encoder.
    model = load_model()

    # This structure matches your successful prediction-check script.
    encoder = (
        model.named_steps["preprocessing"]
        .named_transformers_["categorical"]
        .named_steps["encoder"]
    )

    # The categorical input order is bra_size, then dress_item.
    dress_ids = sorted(
        {
            str(value).removeprefix("item_")
            for value in encoder.categories_[1]
            if str(value).startswith("item_")
        }
    )

    # "missing" is a preparation marker, not a selectable bra size.
    bra_sizes = sorted(
        {
            str(value)
            for value in encoder.categories_[0]
            if isinstance(value, str) and value != "missing"
        }
    )

    if not dress_ids or not bra_sizes:
        raise ValueError(
            "The saved model contains no usable dress or bra-size options."
        )

    return dress_ids, bra_sizes


if __name__ == "__main__":
    # A technical check using model categories, without customer data.
    dress_ids, bra_sizes = get_supported_options()

    print("Saved model loaded successfully.")
    print("Number of supported dresses:", len(dress_ids))
    print("First five dress IDs:", dress_ids[:5])
    print("Number of selectable bra-size categories:", len(bra_sizes))