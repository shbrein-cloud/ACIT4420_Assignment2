"""Smart Fitness Session Analyzer package.

Modules
-------
``calculations``  standalone calculation, validation and formatting functions
``exceptions``    the custom exception classes raised while loading data
``validation``    regular-expression identifier checks and type conversion
``models``        Participant, Observation and Session
``rules``         ClassificationRule and its five subclasses
``analyzer``      SessionAnalyzer, which applies the rules
``loaders``       reading participants and session rows from CSV files
``outputs``       writing the summary, report and rejected-record files
``report``        turning a result dictionary into readable console text
``pipeline``      the end-to-end process used by main.py
"""

from .analyzer import SessionAnalyzer
from .exceptions import (FitnessDataError, InvalidIdentifierError, InvalidRecordError,
                         UnknownParticipantError)
from .loaders import LoadReport, ParticipantRepository, RejectedRecord, SessionLoader
from .models import Observation, Participant, Session
from .outputs import write_all_outputs
from .pipeline import (DEFAULT_OUTPUT, DEFAULT_PROFILES, DEFAULT_SESSIONS, AnalysisPipeline)
from .report import format_overview, format_report

__all__ = [
    "Participant", "Observation", "Session", "SessionAnalyzer",
    "ParticipantRepository", "SessionLoader", "LoadReport", "RejectedRecord",
    "AnalysisPipeline", "write_all_outputs",
    "FitnessDataError", "InvalidIdentifierError", "InvalidRecordError",
    "UnknownParticipantError",
    "format_report", "format_overview",
    "DEFAULT_PROFILES", "DEFAULT_SESSIONS", "DEFAULT_OUTPUT",
]
