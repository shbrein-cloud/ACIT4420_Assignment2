"""Smart Fitness Session Analyzer - entry point (Assignment II).

Reads the participant and session CSV files, validates every row, analyzes each
session and writes the report files into the output directory.

Usage from the repository root:

    python3 main.py
    python3 main.py --profiles data/participants.csv \\
                    --sessions data/fitness_sessions.csv data/fitness_sessions_invalid.csv \\
                    --output output
    python3 main.py --print-report        # also print the full report to the console
    python3 main.py --json                # print the structured result as JSON
"""

import argparse
import json
import sys
from pathlib import Path

from fitness_analyzer import AnalysisPipeline, format_report
from fitness_analyzer.exceptions import FitnessDataError
from fitness_analyzer.pipeline import DEFAULT_OUTPUT, DEFAULT_PROFILES, DEFAULT_SESSIONS


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(
        description="Analyze wearable fitness sessions stored in CSV files.")
    parser.add_argument("--profiles", default=str(DEFAULT_PROFILES),
                        help="participant profile CSV (default: %(default)s)")
    parser.add_argument("--sessions", nargs="+",
                        default=[str(path) for path in DEFAULT_SESSIONS],
                        help="one or more session CSV files (default: the two official files)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT),
                        help="directory for the report files (default: %(default)s)")
    parser.add_argument("--print-report", action="store_true",
                        help="also print the full per-session report to the console")
    parser.add_argument("--json", action="store_true",
                        help="print the structured results as JSON instead of text")
    return parser.parse_args(argv)


def print_console_output(outcome, args):
    """Print what the user asked to see, before the completion summary."""
    if args.json:
        print(json.dumps({"results": outcome["results"],
                          "rejected_records": outcome["rejected_records"],
                          "totals": outcome["totals"]}, indent=2))
        return

    if args.print_report:
        for result in outcome["results"]:
            print(format_report(result))
            print()

    rejected = outcome["rejected_records"]
    if rejected:
        print("Rejected rows ({}):".format(len(rejected)))
        for record in rejected:
            print("  {} row {}: [{}] {}".format(
                record["source"], record["row_number"], record["field"], record["reason"]))
        print()

    print("Sessions analyzed:")
    for result in outcome["results"]:
        counts = result["observation_counts"]
        print("  {:<14} {:<20} {} of {} observations usable".format(
            result["session_id"], result["classification"],
            counts["usable"], counts["total"]))
    print()


def main(argv=None):
    args = parse_arguments(argv)
    pipeline = AnalysisPipeline()

    # The pipeline raises FitnessDataError for problems it cannot recover from,
    # such as an unreadable profile file or an output directory it may not create.
    try:
        outcome = pipeline.run(Path(args.profiles), [Path(p) for p in args.sessions],
                               Path(args.output))
    except FitnessDataError as error:
        print("Error: {}".format(error), file=sys.stderr)
        return 1

    print_console_output(outcome, args)
    if not args.json:
        print(AnalysisPipeline.format_completion_summary(outcome))
    return 0


if __name__ == "__main__":
    sys.exit(main())
