"""Presentation functions that turn a result dictionary into console text."""

from .calculations import format_signed, format_value

UNITS = {
    "heart_rate": "bpm",
    "skin_response": "units",
    "temperature": "C",
    "activity_level": "",
    "signal_quality": "",
}

LINE_WIDTH = 70


def format_summary_table(summary):
    """Table with count, mean, min and max for each measurement."""
    lines = ["  {:<16}{:>7}{:>10}{:>10}{:>10}".format(
        "Measurement", "Count", "Mean", "Min", "Max")]
    for name, stats in summary.items():
        lines.append("  {:<16}{:>7}{:>10}{:>10}{:>10}".format(
            name, stats["count"], format_value(stats["mean"]),
            format_value(stats["min"]), format_value(stats["max"])))
    return "\n".join(lines)


def format_comparison(comparison):
    """Lines comparing session averages with personal reference values."""
    lines = []
    for name, item in comparison.items():
        unit = UNITS.get(name, "")
        percent = item["percent_change"]
        lines.append("  {:<16} reference {:>8}   session {:>8}   change {:>10} ({})".format(
            name, format_value(item["reference"]), format_value(item["measured"]),
            format_signed(item["difference"], 2, unit),
            "n/a" if percent is None else "{:+.1f}%".format(percent)))
    return "\n".join(lines)


def format_recovery(recovery):
    if not recovery["segment_size"]:
        return "  Not enough usable observations to examine recovery."
    return "\n".join([
        "  Compared the peak with the last {} usable windows".format(
            recovery["segment_size"]),
        "  Peak heart rate: {} bpm at t={} ({} bpm above baseline)".format(
            format_value(recovery["peak_hr"], 0), recovery["peak_timestamp"],
            format_value(recovery["peak_increase"], 1)),
        "  Heart rate at the end: {} bpm (down {} bpm from the peak, "
        "trend {} bpm/window)".format(
            format_value(recovery["end_hr"], 1), format_value(recovery["drop_from_peak"], 1),
            format_signed(recovery["hr_slope"], 2)),
        "  Activity drop from the peak: {} (trend {} per window)".format(
            format_value(recovery["activity_drop"]),
            format_signed(recovery["activity_slope"], 3)),
        "  Recovery detected: {}".format("yes" if recovery["detected"] else "no"),
    ])


def format_excluded(excluded, limit=6):
    if not excluded:
        return "  None - all observations passed validation."
    lines = []
    for item in excluded[:limit]:
        lines.append("  t={:<4} {:<9} {}".format(
            str(item["timestamp"]), item["status"], "; ".join(item["problems"])))
    if len(excluded) > limit:
        lines.append("  ... and {} more".format(len(excluded) - limit))
    return "\n".join(lines)


def format_report(result, title=None):
    """Complete readable console report for one analyzed session."""
    counts = result["observation_counts"]
    heading = title or "Session {}".format(result["session_id"])
    parts = [
        "=" * LINE_WIDTH,
        heading,
        "Participant: {}   Session: {}".format(result["participant_id"], result["session_id"]),
        "=" * LINE_WIDTH,
        "CLASSIFICATION: {}".format(result["classification"].upper()),
        "Reason: " + result["explanation"],
        "",
        "Observations: {total} total, {usable} usable, {rejected} rejected, "
        "{flagged} flagged (usable ratio {usable_ratio:.0%})".format(**counts),
        format_excluded(result["excluded_observations"]),
        "",
        "Summary of usable observations:",
        format_summary_table(result["summary"]),
        "",
        "Comparison with personal reference values:",
        format_comparison(result["comparison_with_reference"]),
        "",
        "Recovery analysis:",
        format_recovery(result["recovery"]),
    ]
    return "\n".join(parts)


def format_overview(rows):
    """One-line-per-session overview table.

    ``rows`` is a list of dictionaries with keys name, expected and result.
    """
    lines = ["-" * LINE_WIDTH,
             "{:<24}{:<20}{:<20}{:>6}".format("Scenario", "Expected", "Classified", "Usable"),
             "-" * LINE_WIDTH]
    for row in rows:
        counts = row["result"]["observation_counts"]
        lines.append("{:<24}{:<20}{:<20}{:>6}".format(
            row["name"], row["expected"] or "-", row["result"]["classification"],
            "{}/{}".format(counts["usable"], counts["total"])))
    lines.append("-" * LINE_WIDTH)
    return "\n".join(lines)
