"""Identifier validation with regular expressions, and value conversion.

Regular expressions are used **only** for identifiers and filenames, which have
a fixed textual shape. Numerical limits are checked with ordinary comparisons
in :mod:`fitness_analyzer.calculations`, because a range check is not a
pattern-matching problem.

Every pattern is anchored with ``^`` and ``$`` and matched with
``re.fullmatch``, so a value such as ``"P001x"`` cannot pass.
"""

import re

from .exceptions import InvalidIdentifierError, InvalidRecordError

#: ``P`` followed by exactly three digits, for example ``P001``.
PARTICIPANT_ID_PATTERN = re.compile(r"^P\d{3}$")

#: ``FIT-YYYY-NNN``, for example ``FIT-2026-001``.
SESSION_ID_PATTERN = re.compile(r"^FIT-\d{4}-\d{3}$")

#: A plain CSV filename, used to check the files given on the command line.
CSV_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+\.csv$", re.IGNORECASE)


def validate_participant_id(value):
    """Return the participant identifier, or raise :class:`InvalidIdentifierError`."""
    text = "" if value is None else str(value).strip()
    if not PARTICIPANT_ID_PATTERN.fullmatch(text):
        raise InvalidIdentifierError("participant_id", text, PARTICIPANT_ID_PATTERN.pattern)
    return text


def validate_session_id(value):
    """Return the session identifier, or raise :class:`InvalidIdentifierError`."""
    text = "" if value is None else str(value).strip()
    if not SESSION_ID_PATTERN.fullmatch(text):
        raise InvalidIdentifierError("session_id", text, SESSION_ID_PATTERN.pattern)
    return text


def is_csv_filename(name):
    """Return True when ``name`` looks like a plain CSV filename."""
    return bool(CSV_FILENAME_PATTERN.fullmatch(str(name)))


def require_present(field, value):
    """Return the stripped text of a required field, or raise if it is empty.

    A value is missing when the column was absent from the row (``None``) or
    when the cell is empty or only whitespace.
    """
    if value is None:
        raise InvalidRecordError(field, "required field '{}' is missing from the row".format(field))
    text = str(value).strip()
    if not text:
        raise InvalidRecordError(field, "required field '{}' is empty".format(field))
    return text


def to_int(field, value):
    """Convert a CSV cell to ``int``, raising :class:`InvalidRecordError` on failure.

    Accepts ``"5"`` and ``"5.0"`` but rejects ``"fast"``, ``"two"`` and ``"5.4"``.
    """
    text = require_present(field, value)
    try:
        number = float(text)
    except (TypeError, ValueError):
        raise InvalidRecordError(
            field, "{} = {!r} is not a whole number".format(field, text)
        ) from None
    if number != int(number):
        raise InvalidRecordError(field, "{} = {!r} is not a whole number".format(field, text))
    return int(number)


def to_float(field, value):
    """Convert a CSV cell to ``float``, raising :class:`InvalidRecordError` on failure."""
    text = require_present(field, value)
    try:
        return float(text)
    except (TypeError, ValueError):
        raise InvalidRecordError(
            field, "{} = {!r} is not a number".format(field, text)
        ) from None
