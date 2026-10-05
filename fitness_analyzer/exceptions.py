"""Custom exceptions raised by the fitness analyzer.

The exceptions inherit from ``ValueError`` because every one of them means
"this value cannot be accepted". That lets calling code catch them with the
specific class when it wants a precise reason, or with ``ValueError`` when it
only needs to know that the record was unusable.
"""


class FitnessDataError(ValueError):
    """Base class for every problem detected while loading fitness data."""


class InvalidIdentifierError(FitnessDataError):
    """Raised when an identifier has an invalid format.

    Example: a session identifier written as ``FIT-26-102`` instead of
    ``FIT-2026-102``.
    """

    def __init__(self, field, value, pattern):
        self.field = field
        self.value = value
        self.pattern = pattern
        super().__init__(
            "{} {!r} does not match the required format {}".format(field, value, pattern)
        )


class InvalidRecordError(FitnessDataError):
    """Raised when a CSV record cannot be accepted.

    Carries the field that caused the problem so the caller can write a useful
    line in the rejected-records report.
    """

    def __init__(self, field, reason):
        self.field = field
        self.reason = reason
        super().__init__(reason)


class UnknownParticipantError(InvalidRecordError):
    """Raised when a session row refers to a participant that does not exist.

    It is a subclass of :class:`InvalidRecordError` because an unknown
    participant is one particular kind of unusable record, but it is a separate
    class so that the loader can report it with its own wording.
    """

    def __init__(self, participant_id, known_ids=()):
        self.participant_id = participant_id
        self.known_ids = tuple(known_ids)
        known = ", ".join(self.known_ids) if self.known_ids else "none loaded"
        super().__init__(
            "participant_id",
            "unknown participant {!r} (known participants: {})".format(participant_id, known),
        )
