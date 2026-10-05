"""Writing the analysis results to files in the output directory.

Three files are produced, as required by the assignment:

* ``analysis_summary.csv``  - one row per processed session;
* ``analysis_report.txt``   - a readable explanation of every result;
* ``rejected_records.txt``  - every rejected row and why it was rejected.

All three are written with ``"w"``, so running the program again replaces them
and no manual cleanup is needed. The contents depend only on the input files,
never on the clock, so two runs over the same data produce identical files.
"""

import csv
from pathlib import Path

from .calculations import format_value
from .exceptions import FitnessDataError
from .report import LINE_WIDTH, format_report

SUMMARY_FILENAME = "analysis_summary.csv"
REPORT_FILENAME = "analysis_report.txt"
REJECTED_FILENAME = "rejected_records.txt"

SUMMARY_COLUMNS = (
    "session_id", "participant_id", "participant_name", "classification",
    "observations_total", "observations_usable", "observations_rejected",
    "observations_flagged", "usable_ratio", "mean_heart_rate", "min_heart_rate",
    "max_heart_rate", "heart_rate_vs_baseline", "mean_activity_level",
    "mean_signal_quality", "recovery_detected", "source_files",
)


def ensure_output_directory(directory):
    """Create the output directory (and parents) when it does not exist."""
    path = Path(directory)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        raise FitnessDataError("no permission to create directory {}".format(path)) from None
    except OSError as error:
        raise FitnessDataError("could not create directory {}: {}".format(path, error)) from None
    return path


def summary_row(result):
    """Flatten one analysis result into a single CSV row."""
    counts = result["observation_counts"]
    heart_rate = result["summary"]["heart_rate"]
    return {
        "session_id": result["session_id"],
        "participant_id": result["participant_id"],
        "participant_name": result["participant_name"] or "",
        "classification": result["classification"],
        "observations_total": counts["total"],
        "observations_usable": counts["usable"],
        "observations_rejected": counts["rejected"],
        "observations_flagged": counts["flagged"],
        "usable_ratio": counts["usable_ratio"],
        "mean_heart_rate": format_value(heart_rate["mean"]),
        "min_heart_rate": format_value(heart_rate["min"]),
        "max_heart_rate": format_value(heart_rate["max"]),
        "heart_rate_vs_baseline": format_value(
            result["comparison_with_reference"]["heart_rate"]["difference"]),
        "mean_activity_level": format_value(result["summary"]["activity_level"]["mean"]),
        "mean_signal_quality": format_value(result["summary"]["signal_quality"]["mean"]),
        "recovery_detected": "yes" if result["recovery"]["detected"] else "no",
        "source_files": " ".join(result["sources"]),
    }


def _open_for_writing(path):
    """Open an output file, converting low-level errors into a clear message."""
    try:
        return open(path, "w", newline="", encoding="utf-8")
    except PermissionError:
        raise FitnessDataError("no permission to write {}".format(path)) from None
    except OSError as error:
        raise FitnessDataError("could not write {}: {}".format(path, error)) from None


def write_summary_csv(results, directory):
    """Write ``analysis_summary.csv`` with one row per session."""
    path = Path(directory) / SUMMARY_FILENAME
    handle = _open_for_writing(path)
    try:
        writer = csv.DictWriter(handle, fieldnames=list(SUMMARY_COLUMNS))
        writer.writeheader()
        for result in results:
            writer.writerow(summary_row(result))
    finally:
        handle.close()
    return path


def write_analysis_report(results, directory, totals=None):
    """Write ``analysis_report.txt`` with a readable report per session."""
    path = Path(directory) / REPORT_FILENAME
    parts = ["SMART FITNESS SESSION ANALYZER", "Analysis report", ""]
    if totals:
        parts.append("Input files: " + ", ".join(Path(name).name
                                                 for name in totals["files_read"]))
        parts.append("Rows accepted: {}  (of which flagged: {})  rows rejected: {}".format(
            totals["accepted_rows"], totals["flagged_rows"], totals["rejected_rows"]))
        parts.append("")
    if not results:
        parts.append("No sessions could be built from the input files.")
    for result in results:
        parts.append(format_report(result))
        parts.append("")
    parts.append("=" * LINE_WIDTH)
    parts.append("Sessions analyzed: {}".format(len(results)))
    for result in results:
        parts.append("  {:<14} {:<20} {} of {} observations usable".format(
            result["session_id"], result["classification"],
            result["observation_counts"]["usable"], result["observation_counts"]["total"]))
    parts.append("=" * LINE_WIDTH)

    handle = _open_for_writing(path)
    try:
        handle.write("\n".join(parts) + "\n")
    finally:
        handle.close()
    return path


def write_rejected_records(report, results, directory):
    """Write ``rejected_records.txt``.

    The first section lists rows rejected while reading the files. The second
    lists rows that were accepted but then excluded from the analysis because
    their signal quality was too low, which is a data-quality issue rather than
    a broken row.
    """
    path = Path(directory) / REJECTED_FILENAME
    rejected = sorted(report.rejected, key=lambda r: (r.source, r.row_number))

    lines = ["SMART FITNESS SESSION ANALYZER", "Rejected and flagged records", ""]
    lines.append("REJECTED ROWS ({} total)".format(len(rejected)))
    lines.append("-" * LINE_WIDTH)
    if rejected:
        lines.extend(record.to_line() for record in rejected)
    else:
        lines.append("None - every row in the input files was accepted.")

    flagged = [(result, item) for result in results
               for item in result["excluded_observations"]
               if item["status"] == "flagged"]
    lines.append("")
    lines.append("FLAGGED ROWS - accepted but excluded from the analysis ({} total)".format(
        len(flagged)))
    lines.append("-" * LINE_WIDTH)
    if flagged:
        for result, item in flagged:
            lines.append("{:<22} session={:<13} t={:<4} {}".format(
                item["source"] or "?", result["session_id"], item["timestamp"],
                "; ".join(item["problems"])))
    else:
        lines.append("None - no row was excluded for low signal quality.")

    handle = _open_for_writing(path)
    try:
        handle.write("\n".join(lines) + "\n")
    finally:
        handle.close()
    return path


def write_all_outputs(results, report, directory):
    """Create the output directory and write all three report files."""
    output_directory = ensure_output_directory(directory)
    return [
        write_summary_csv(results, output_directory),
        write_analysis_report(results, output_directory, report.totals()),
        write_rejected_records(report, results, output_directory),
    ]
