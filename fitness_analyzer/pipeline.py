"""The end-to-end pipeline: load CSV files, analyze sessions, write reports.

Keeping the whole process in one class means ``main.py`` only has to deal with
command-line arguments and printing, and the tests can run the same pipeline
without starting a subprocess.
"""

from pathlib import Path

from .analyzer import SessionAnalyzer
from .loaders import LoadReport, ParticipantRepository, SessionLoader
from .outputs import write_all_outputs

DEFAULT_PROFILES = Path("data") / "participants.csv"
DEFAULT_SESSIONS = (Path("data") / "fitness_sessions.csv",
                    Path("data") / "fitness_sessions_invalid.csv")
DEFAULT_OUTPUT = Path("output")


class AnalysisPipeline:
    """Runs the complete analysis for one set of input files.

    The pipeline *has a* :class:`~fitness_analyzer.analyzer.SessionAnalyzer`
    (composition) and builds its own participant repository and session loader
    while it runs.
    """

    def __init__(self, analyzer=None):
        self._analyzer = analyzer or SessionAnalyzer()

    @property
    def analyzer(self):
        return self._analyzer

    def run(self, profiles_path, session_paths, output_directory=None):
        """Load, analyze and (optionally) write the report files.

        Returns a structured result dictionary holding the per-session results,
        the rejected records and the totals. When ``output_directory`` is
        ``None`` nothing is written, which the tests use.
        """
        report = LoadReport()
        repository, report = ParticipantRepository.from_csv(profiles_path, report)

        loader = SessionLoader(repository)
        sessions, report = loader.load_files(session_paths, report)

        results = [self._analyzer.analyze(session) for session in sessions]

        written_files = []
        if output_directory is not None:
            written_files = write_all_outputs(results, report, output_directory)

        totals = report.totals()
        totals["participants_loaded"] = len(repository)
        totals["sessions_analyzed"] = len(results)
        return {
            "participants": repository,
            "sessions": sessions,
            "results": results,
            "load_report": report,
            "rejected_records": [record.to_dict() for record in report.rejected],
            "totals": totals,
            "written_files": [str(path) for path in written_files],
        }

    @staticmethod
    def format_completion_summary(outcome):
        """The short completion summary printed when the program finishes."""
        totals = outcome["totals"]
        lines = [
            "Completed.",
            "  Participants loaded : {}".format(totals["participants_loaded"]),
            "  Files read          : {}".format(
                ", ".join(Path(name).name for name in totals["files_read"]) or "none"),
            "  Rows accepted       : {} (of which {} flagged as low quality)".format(
                totals["accepted_rows"], totals["flagged_rows"]),
            "  Rows rejected       : {}".format(totals["rejected_rows"]),
            "  Sessions analyzed   : {}".format(totals["sessions_analyzed"]),
        ]
        if outcome["written_files"]:
            lines.append("  Report files created:")
            lines.extend("    " + name for name in outcome["written_files"])
        else:
            lines.append("  Report files created: none (output writing was skipped)")
        return "\n".join(lines)
