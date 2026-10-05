"""Standalone calculation, validation and formatting functions.

These functions deliberately do not depend on any of the project's classes.
They operate on plain numbers, lists and dictionaries, which makes them easy
to reuse and to test in isolation.
"""

import math
import statistics


def is_number(value):
    """Return True for a finite int or float (bool is not accepted)."""
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def check_range(name, value, lower, upper):
    """Validate one measurement.

    Returns ``None`` when the value is acceptable, otherwise a short text
    describing the problem. Returning a message (instead of raising) lets the
    caller collect every problem in an observation, not just the first one.
    """
    if value is None:
        return name + " is missing"
    if not is_number(value):
        return "{} is not a number ({!r})".format(name, value)
    if value < lower or value > upper:
        return "{} = {} is outside the possible range {}-{}".format(name, value, lower, upper)
    return None


def summarize(values):
    """Return count, mean, minimum, maximum and standard deviation."""
    if not values:
        return {"count": 0, "mean": None, "min": None, "max": None, "stdev": None}
    return {
        "count": len(values),
        "mean": round(statistics.fmean(values), 2),
        "min": min(values),
        "max": max(values),
        "stdev": round(statistics.pstdev(values), 2),
    }


def compare_with_reference(value, reference):
    """Compare a measured value with a personal reference value."""
    if value is None or reference is None:
        return {"reference": reference, "measured": value,
                "difference": None, "percent_change": None}
    difference = value - reference
    percent = None if reference == 0 else 100.0 * difference / reference
    return {
        "reference": reference,
        "measured": round(value, 2),
        "difference": round(difference, 2),
        "percent_change": None if percent is None else round(percent, 1),
    }


def linear_slope(x_values, y_values):
    """Least-squares slope of y against x (change of y per time step).

    Returns 0.0 when a slope cannot be calculated (fewer than two points or
    all x values identical).
    """
    if len(x_values) != len(y_values):
        raise ValueError("x_values and y_values must have the same length")
    if len(x_values) < 2:
        return 0.0
    mean_x = statistics.fmean(x_values)
    mean_y = statistics.fmean(y_values)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values))
    denominator = sum((x - mean_x) ** 2 for x in x_values)
    if denominator == 0:
        return 0.0
    return numerator / denominator


def split_start_and_end(items, fraction=1 / 3, minimum=2):
    """Return the first and last part of an ordered list.

    Each part contains ``fraction`` of the items (but at least ``minimum``).
    Used to compare the start of a session with its end.
    """
    size = max(minimum, int(len(items) * fraction))
    size = min(size, len(items) // 2)
    if size == 0:
        return [], []
    return list(items[:size]), list(items[-size:])


def index_of_maximum(values):
    """Return the position of the largest value, or ``None`` for an empty list.

    When the maximum occurs more than once the first position is returned.
    """
    if not values:
        return None
    return max(range(len(values)), key=values.__getitem__)


def format_value(value, digits=2, unit=""):
    """Format a number for the console report; ``None`` becomes 'n/a'."""
    if value is None:
        return "n/a"
    if isinstance(value, float):
        text = "{:.{}f}".format(value, digits)
    else:
        text = str(value)
    return text + (" " + unit if unit else "")


def format_signed(value, digits=1, unit=""):
    """Format a difference with an explicit + or - sign."""
    if value is None:
        return "n/a"
    text = "{:+.{}f}".format(value, digits)
    return text + (" " + unit if unit else "")
