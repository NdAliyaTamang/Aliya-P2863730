"""Calculate hypothetical sustainability scenarios.

Inputs are explicit assumptions, not measured OwnableFit benefits.
Model accuracy is not used to estimate return reductions.
"""

import math


def validate_number(value, label, minimum=0, maximum=None):
    """Accept a finite number within the specified bounds."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{label} must be a number.") from None

    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite.")

    if number < minimum:
        raise ValueError(f"{label} must be at least {minimum}.")

    if maximum is not None and number > maximum:
        raise ValueError(f"{label} must not exceed {maximum}.")

    return number


def calculate_scenario(
    orders,
    size_return_rate_percent,
    relative_reduction_percent,
    kg_co2e_per_return,
):
    """Calculate one hypothetical scenario.

    Rates are percentages between 0 and 100.
    Emissions are kilograms of CO2 equivalent per return.
    Fractional returns are expected values, not observed counts.
    """
    orders = validate_number(orders, "Number of orders")

    if not orders.is_integer():
        raise ValueError("Number of orders must be a whole number.")

    return_rate = validate_number(
        size_return_rate_percent,
        "Size-related return rate",
        maximum=100,
    )

    relative_reduction = validate_number(
        relative_reduction_percent,
        "Assumed relative reduction",
        maximum=100,
    )

    impact = validate_number(
        kg_co2e_per_return,
        "Emissions per return",
    )

    # Convert the assumed return rate into the expected number of size-related returns.
    baseline_returns = orders * (return_rate / 100)
    # Apply the relative reduction to expected size-related returns.
    avoided_returns = baseline_returns * (relative_reduction / 100)
    remaining_returns = baseline_returns - avoided_returns
    # Multiply expected avoided returns by the assumed impact per return.
    potential_saving = avoided_returns * impact

    # Reject calculations that overflow despite finite individual inputs.
    results = (
        baseline_returns,
        avoided_returns,
        remaining_returns,
        potential_saving,
    )

    if not all(math.isfinite(value) for value in results):
        raise ValueError("The assumptions are too large to calculate.")

    return {
        "baseline_returns": baseline_returns,
        "avoided_returns": avoided_returns,
        "remaining_returns": remaining_returns,
        "potential_kg_co2e_saved": potential_saving,
    }


def compare_scenarios(
    orders,
    size_return_rate_percent,
    low_reduction_percent,
    medium_reduction_percent,
    high_reduction_percent,
    kg_co2e_per_return,
):
    """Compare three ordered relative-reduction assumptions.

    Orders, baseline return rate and emissions factor stay the same.
    Only the assumed relative reduction changes between scenarios.
    Low, medium and high are scenario labels, not confidence intervals.
    """
    low = validate_number(
        low_reduction_percent,
        "Low relative reduction",
        maximum=100,
    )
    medium = validate_number(
        medium_reduction_percent,
        "Medium relative reduction",
        maximum=100,
    )
    high = validate_number(
        high_reduction_percent,
        "High relative reduction",
        maximum=100,
    )

    # Check that the hypothetical reductions follow the low, medium and high order.
    if not low <= medium <= high:
        raise ValueError(
            "Relative reductions must follow: low ≤ medium ≤ high."
        )

    comparison = []

    for label, reduction in (
        ("Low", low),
        ("Medium", medium),
        ("High", high),
    ):
        result = calculate_scenario(
            orders=orders,
            size_return_rate_percent=size_return_rate_percent,
            relative_reduction_percent=reduction,
            kg_co2e_per_return=kg_co2e_per_return,
        )

        comparison.append({
            "label": label,
            "relative_reduction_percent": reduction,
            **result,
        })

    return comparison


if __name__ == "__main__":
    # Arbitrary technical examples, not research findings.
    scenarios = compare_scenarios(
        orders=1000,
        size_return_rate_percent=20,
        low_reduction_percent=5,
        medium_reduction_percent=10,
        high_reduction_percent=20,
        kg_co2e_per_return=1,
    )

    print("Hypothetical comparison — illustrative assumptions only.")

    for scenario in scenarios:
        print(
            f'{scenario["label"]}: '
            f'{scenario["relative_reduction_percent"]:g}% relative reduction; '
            f'{scenario["avoided_returns"]:.2f} potential returns avoided; '
            f'{scenario["potential_kg_co2e_saved"]:.2f} kg CO2e potential saving'
        )

    print("The emissions factor is illustrative, not a sourced estimate.")