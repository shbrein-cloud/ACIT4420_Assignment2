"""Reading participants and session rows from CSV files.

Every row is validated before it becomes an :class:`~fitness_analyzer.models.Observation`.
A row that cannot be accepted is turned into a :class:`RejectedRecord` carrying the
source filename, the row number, the field and the reason, and the loader continues
with the next row instead of stopping.
"""

import csv
from pathlib import Path

from .exceptions import (FitnessDataError, InvalidIdentifierError, InvalidRecordError,
                         UnknownParticipantError)
from .models import Observation, Participant, Session
from .validation import (is_csv_filename, to_float, to_int, validate_participant_id,
                         validate_session_id)

PARTICIPANT_COLUMNS = ("participant_id", "name", "baseline_heart_rate",
                       "baseline_skin_response", "baseline_temperature")
SESSION_COLUMNS = ("session_id", "participant_id", "timestamp", "heart_rate",
                   "skin_response", "temperature", "activity_level", "signal_quality")

#: How each measurement column is converted from text.
SESSION_CONVERTERS = {
    "timestamp": to_int,
    "heart_rate": to_int,
    "skin_response": to_float,
    "temperature": to_float,
    "activity_level": to_float,
    "signal_quality": to_float,
}

#: Marker used by ``csv.DictReader`` for values beyond the header columns.
EXTRA_FIELDS_KEY = "__extra_columns__"


class RejectedRecord:
    """One row that could not be accepted, with everything needed to report it."""

    def __init__(self, source, row_number, field, reason,
                 session_id=None, participant_id=None):
        self.source = source
        self.row_number = row_number
        self.field = field
        self.reason = reason
        self.session_id = session_id
        self.participant_id = participant_id

    def to_dict(self):
        return {
            "source": self.source,
            "row_number": self.row_number,
            "session_id": self.session_id or "",
            "participant_id": self.participant_id or "",
            "field": self.field,
            "reason": self.reason,
        }

    def to_line(self):
        """One readable line for ``rejected_records.txt``."""
        return "{} row {:<4} session={:<13} field={:<16} {}".format(
            self.source, self.row_number, self.session_id or "?",
            self.field, self.reason)

    def __repr__(self):
        return "RejectedRecord({} row {}, {})".format(self.source, self.row_number, self.field)


class LoadReport:
    """Counts and rejected records collected while reading the input files."""

    def __init__(self):
        self._files_read = []
        self._rejected = []
        self._accepted_rows = 0
        self._flagged_rows = 0

    def file_read(self, path):
        self._files_read.append(str(path))

    def accept(self, flagged=False):
        self._accepted_rows += 1
        if flagged:
            self._flagged_rows += 1

    def reject(self, record):
        self._rejected.append(record)

    @property
    def files_read(self):
        return tuple(self._files_read)

    @property
    def rejected(self):
        return tuple(self._rejected)

    @property
    def accepted_rows(self):
        return self._accepted_rows

    @property
    def flagged_rows(self):
        return self._flagged_rows

    @property
    def rejected_rows(self):
        return len(self._rejected)

    def totals(self):
        return {
            "files_read": list(self._files_read),
            "accepted_rows": self._accepted_rows,
            "flagged_rows": self._flagged_rows,
            "rejected_rows": len(self._rejected),
        }


def open_csv(path):
    """Open a CSV file for reading, raising a clear error when that is impossible.

    The file is opened exactly as the assignment requires, with an explicit
    encoding and ``newline=""`` so the csv module handles line endings itself.
    """
    path = Path(path)
    if not is_csv_filename(path.name):
        raise FitnessDataError("{} is not a .csv filename".format(path.name))
    try:
        return open(path, newline="", encoding="utf-8")
    except FileNotFoundError:
        raise FitnessDataError("input file not found: {}".format(path)) from None
    except PermissionError:
        raise FitnessDataError("no permission to read {}".format(path)) from None
    except OSError as error:
        raise FitnessDataError("could not open {}: {}".format(path, error)) from None


def read_rows(path):
    """Yield ``(row_number, row_dict)`` for every data row in a CSV file.

    ``row_dict`` uses the header names. A short row gives ``None`` for the
    missing columns and a long row collects the surplus under
    :data:`EXTRA_FIELDS_KEY`, so both problems can be reported later.
    """
    handle = open_csv(path)
    try:
        reader = csv.DictReader(handle, restkey=EXTRA_FIELDS_KEY, restval=None)
        if reader.fieldnames is None:
            raise FitnessDataError("{} is empty (no header row)".format(Path(path).name))
        for row in reader:
            yield reader.line_num, row
    except csv.Error as error:
        raise FitnessDataError("malformed CSV in {}: {}".format(Path(path).name, error)) from None
    finally:
        handle.close()


def check_row_shape(row, expected_columns):
    """Raise :class:`InvalidRecordError` when a row has the wrong number of fields."""
    if row.get(EXTRA_FIELDS_KEY) is not None:
        raise InvalidRecordError(
            "row",
            "row has more fields than the {} header columns".format(len(expected_columns)))
    missing = [name for name in expected_columns if row.get(name) is None]
    if missing:
        raise InvalidRecordError(
            "row", "row is missing the column(s): {}".format(", ".join(missing)))


class ParticipantRepository:
    """All known participants, keyed by identifier.

    Encapsulates the dictionary of participants so that callers can only reach
    them through :meth:`get`, which raises a precise error for unknown people.
    """

    def __init__(self, participants=None):
        self._participants = {}
        for participant in participants or []:
            self.add(participant)

    @classmethod
    def from_csv(cls, path, report=None):
        """Load ``participants.csv`` into a repository.

        Invalid profile rows are rejected individually; the remaining
        participants are still loaded.
        """
        repository = cls()
        report = report if report is not None else LoadReport()
        source = Path(path).name
        for row_number, row in read_rows(path):
            try:
                check_row_shape(row, PARTICIPANT_COLUMNS)
                repository.add(cls._participant_from_row(row))
            except (InvalidIdentifierError, InvalidRecordError) as error:
                report.reject(RejectedRecord(source, row_number, getattr(error, "field", "row"),
                                             str(error),
                                             participant_id=row.get("participant_id")))
            except ValueError as error:
                # Raised by Participant when a baseline is outside its limits.
                report.reject(RejectedRecord(source, row_number, "baseline", str(error),
                                             participant_id=row.get("participant_id")))
            else:
                report.accept()
        report.file_read(path)
        return repository, report

    @staticmethod
    def _participant_from_row(row):
        """Convert one ``participants.csv`` row into a Participant object."""
        return Participant(
            participant_id=validate_participant_id(row.get("participant_id")),
            baseline_heart_rate=to_int("baseline_heart_rate", row.get("baseline_heart_rate")),
            baseline_skin_response=to_float("baseline_skin_response",
                                            row.get("baseline_skin_response")),
            baseline_temperature=to_float("baseline_temperature",
                                          row.get("baseline_temperature")),
            name=row.get("name"),
        )

    def add(self, participant):
        if not isinstance(participant, Participant):
            raise TypeError("only Participant objects can be stored")
        self._participants[participant.participant_id] = participant

    def get(self, participant_id):
        """Return the participant, or raise :class:`UnknownParticipantError`."""
        try:
            return self._participants[participant_id]
        except KeyError:
            raise UnknownParticipantError(participant_id, self.ids()) from None

    def ids(self):
        return tuple(sorted(self._participants))

    def __contains__(self, participant_id):
        return participant_id in self._participants

    def __len__(self):
        return len(self._participants)

    def __repr__(self):
        return "ParticipantRepository({} participants)".format(len(self._participants))


class SessionLoader:
    """Builds Session objects from session CSV files.

    The loader *has a* :class:`ParticipantRepository` (composition) and uses it
    to connect every session to an existing participant.
    """

    def __init__(self, repository):
        if not isinstance(repository, ParticipantRepository):
            raise TypeError("repository must be a ParticipantRepository")
        self._repository = repository
        self._sessions = {}

    @property
    def repository(self):
        return self._repository

    def load_files(self, paths, report=None):
        """Read several session files and return ``(sessions, report)``.

        Sessions are returned in identifier order so that re-running the
        program always produces the same output.
        """
        report = report if report is not None else LoadReport()
        for path in paths:
            self._load_one_file(path, report)
        sessions = [self._sessions[key] for key in sorted(self._sessions)]
        return sessions, report

    def _load_one_file(self, path, report):
        source = Path(path).name
        try:
            rows = list(read_rows(path))
        except FitnessDataError as error:
            # A missing or unreadable file must not stop the other files.
            report.reject(RejectedRecord(source, 0, "file", str(error)))
            return
        for row_number, row in rows:
            self._load_one_row(row, source, row_number, report)
        report.file_read(path)

    def _load_one_row(self, row, source, row_number, report):
        """Validate one session row and add it to its session, or reject it."""
        try:
            check_row_shape(row, SESSION_COLUMNS)
            session_id = validate_session_id(row.get("session_id"))
            participant_id = validate_participant_id(row.get("participant_id"))
            participant = self._repository.get(participant_id)
            values = self._convert_measurements(row)
        except UnknownParticipantError as error:
            report.reject(RejectedRecord(source, row_number, error.field, str(error),
                                         session_id=row.get("session_id"),
                                         participant_id=row.get("participant_id")))
        except InvalidIdentifierError as error:
            report.reject(RejectedRecord(source, row_number, error.field, str(error),
                                         session_id=row.get("session_id"),
                                         participant_id=row.get("participant_id")))
        except InvalidRecordError as error:
            report.reject(RejectedRecord(source, row_number, error.field, str(error),
                                         session_id=row.get("session_id"),
                                         participant_id=row.get("participant_id")))
        else:
            self._add_observation(session_id, participant, values,
                                  source, row_number, report)

    @staticmethod
    def _convert_measurements(row):
        """Convert and range-check every measurement column of a session row."""
        values = {}
        for field, converter in SESSION_CONVERTERS.items():
            values[field] = converter(field, row.get(field))
        if values["timestamp"] < 0:
            raise InvalidRecordError("timestamp", "timestamp must not be negative")
        for field, (lower, upper) in Observation.LIMITS.items():
            value = values[field]
            if value < lower or value > upper:
                raise InvalidRecordError(
                    field, "{} = {} is outside the possible range {}-{}".format(
                        field, value, lower, upper))
        return values

    def _add_observation(self, session_id, participant, values, source, row_number, report):
        """Create the observation and attach it to its session."""
        session = self._sessions.get(session_id)
        if session is None:
            session = Session(session_id, participant)
            self._sessions[session_id] = session
        session.record_source(source)

        observation = Observation(source="{} row {}".format(source, row_number), **values)
        session.add_observation(observation)

        if observation.status == Observation.REJECTED:
            # The session itself found a problem, such as a duplicate timestamp.
            report.reject(RejectedRecord(source, row_number, "timestamp",
                                         "; ".join(observation.problems),
                                         session_id=session_id,
                                         participant_id=participant.participant_id))
        else:
            report.accept(flagged=observation.status == Observation.FLAGGED)
