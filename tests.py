"""Automated tests. Run with:  python3 tests.py   (or python3 -m unittest tests)

The tests cover valid data, invalid data, missing files and boundary values:

* ``CalculationTests``  - the standalone helper functions
* ``ValidationTests``   - the regular expressions and type conversion
* ``ParticipantTests``, ``ObservationTests``, ``SessionTests`` - the domain classes
* ``BoundaryTests``     - values exactly on a documented limit
* ``LoaderTests``       - reading the official CSV files, including the invalid one
* ``MissingFileTests``  - missing, unreadable and malformed input files
* ``OutputTests``       - the three generated files, written to a temporary folder
* ``PipelineTests``     - the whole program end to end
* ``AnalyzerTests``     - classification, including 1,500 generated sessions
"""

import csv
import tempfile
import unittest
from pathlib import Path

from data_generator import available_scenarios, generate_fitness_data
from fitness_analyzer import (AnalysisPipeline, LoadReport, Observation, Participant,
                              ParticipantRepository, Session, SessionAnalyzer, SessionLoader,
                              format_report)
from fitness_analyzer.calculations import (check_range, compare_with_reference, index_of_maximum,
                                           is_number, linear_slope, split_start_and_end,
                                           summarize)
from fitness_analyzer.exceptions import (FitnessDataError, InvalidIdentifierError,
                                         InvalidRecordError, UnknownParticipantError)
from fitness_analyzer.loaders import read_rows
from fitness_analyzer.outputs import (REJECTED_FILENAME, REPORT_FILENAME, SUMMARY_FILENAME,
                                      ensure_output_directory)
from fitness_analyzer.rules import ClassificationRule, RecoveryRule
from fitness_analyzer.validation import (is_csv_filename, to_float, to_int,
                                         validate_participant_id, validate_session_id)
from sample_data import get_all_scenarios

DATA = Path(__file__).resolve().parent / "data"
PROFILES_CSV = DATA / "participants.csv"
SESSIONS_CSV = DATA / "fitness_sessions.csv"
INVALID_CSV = DATA / "fitness_sessions_invalid.csv"

EXPECTED_LABELS = {
    "resting": "resting",
    "moderate_activity": "moderate activity",
    "high_activity": "high activity",
    "recovery": "recovering",
    "poor_quality": "insufficient data",
}

#: What the official CSV files should produce. Used as a regression test.
EXPECTED_CSV_RESULTS = {
    "FIT-2026-001": "resting",
    "FIT-2026-002": "moderate activity",
    "FIT-2026-003": "high activity",
    "FIT-2026-004": "recovering",
    "FIT-2026-005": "insufficient data",
    "FIT-2026-101": "insufficient data",
}

PROFILE = {"participant_id": "P001", "baseline_heart_rate": 70,
           "baseline_skin_response": 1.5, "baseline_temperature": 32.5}


def make_observation(timestamp=0, **changes):
    data = {"timestamp": timestamp, "heart_rate": 80, "skin_response": 1.6,
            "temperature": 32.6, "activity_level": 0.2, "signal_quality": 0.9}
    data.update(changes)
    return Observation.from_dict(data)


class CalculationTests(unittest.TestCase):
    def test_summarize(self):
        result = summarize([2, 4, 6])
        self.assertEqual(result["mean"], 4)
        self.assertEqual((result["min"], result["max"], result["count"]), (2, 6, 3))

    def test_summarize_empty(self):
        self.assertIsNone(summarize([])["mean"])

    def test_check_range(self):
        self.assertIsNone(check_range("x", 5, 0, 10))
        self.assertIn("missing", check_range("x", None, 0, 10))
        self.assertIn("outside", check_range("x", 11, 0, 10))
        self.assertIn("not a number", check_range("x", "7", 0, 10))

    def test_is_number_rejects_bool_and_nan(self):
        self.assertFalse(is_number(True))
        self.assertFalse(is_number(float("nan")))
        self.assertTrue(is_number(3.5))

    def test_linear_slope(self):
        self.assertAlmostEqual(linear_slope([0, 1, 2, 3], [10, 8, 6, 4]), -2.0)
        self.assertEqual(linear_slope([1], [5]), 0.0)

    def test_compare_with_reference(self):
        result = compare_with_reference(90, 60)
        self.assertEqual(result["difference"], 30)
        self.assertEqual(result["percent_change"], 50.0)

    def test_split_start_and_end(self):
        start, end = split_start_and_end(list(range(12)))
        self.assertEqual(start, [0, 1, 2, 3])
        self.assertEqual(end, [8, 9, 10, 11])

    def test_index_of_maximum(self):
        self.assertEqual(index_of_maximum([1, 9, 4]), 1)
        self.assertIsNone(index_of_maximum([]))


class ValidationTests(unittest.TestCase):
    """The regular-expression identifier checks and the type converters."""

    def test_valid_identifiers(self):
        self.assertEqual(validate_participant_id("P001"), "P001")
        self.assertEqual(validate_session_id("FIT-2026-001"), "FIT-2026-001")

    def test_participant_id_rejects_wrong_shapes(self):
        for value in ("001", "P01", "P0001", "p001", "P001x", "", None, " P001 x"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidIdentifierError):
                    validate_participant_id(value)

    def test_session_id_rejects_wrong_shapes(self):
        for value in ("FIT-26-102", "FIT-2026-1", "REC-2026-001", "fit-2026-001", ""):
            with self.subTest(value=value):
                with self.assertRaises(InvalidIdentifierError):
                    validate_session_id(value)

    def test_identifier_error_reports_field_and_pattern(self):
        with self.assertRaises(InvalidIdentifierError) as caught:
            validate_session_id("FIT-26-102")
        self.assertEqual(caught.exception.field, "session_id")
        self.assertIn("FIT", caught.exception.pattern)

    def test_filename_pattern(self):
        self.assertTrue(is_csv_filename("participants.csv"))
        self.assertFalse(is_csv_filename("participants.txt"))

    def test_to_int_accepts_whole_numbers_only(self):
        self.assertEqual(to_int("timestamp", "5"), 5)
        self.assertEqual(to_int("timestamp", "5.0"), 5)
        for value in ("two", "5.4", "", None):
            with self.subTest(value=value):
                with self.assertRaises(InvalidRecordError):
                    to_int("timestamp", value)

    def test_to_float_rejects_text(self):
        self.assertAlmostEqual(to_float("energy", "0.42"), 0.42)
        with self.assertRaises(InvalidRecordError):
            to_float("energy", "fast")

    def test_record_error_keeps_field_name(self):
        with self.assertRaises(InvalidRecordError) as caught:
            to_int("heart_rate", "fast")
        self.assertEqual(caught.exception.field, "heart_rate")


class ParticipantTests(unittest.TestCase):
    def test_from_profile(self):
        participant = Participant.from_profile(PROFILE)
        self.assertEqual(participant.baseline_heart_rate, 70)
        self.assertEqual(participant.reference_values()["temperature"], 32.5)

    def test_setter_rejects_impossible_baseline(self):
        participant = Participant.from_profile(PROFILE)
        with self.assertRaises(ValueError):
            participant.baseline_heart_rate = 300
        self.assertEqual(participant.baseline_heart_rate, 70)  # unchanged

    def test_missing_profile_field(self):
        with self.assertRaises(ValueError):
            Participant.from_profile({"participant_id": "P001"})

    def test_identifier_is_validated(self):
        with self.assertRaises(InvalidIdentifierError):
            Participant("BAD", 70, 1.5, 32.5)

    def test_display_name(self):
        participant = Participant("P001", 70, 1.5, 32.5, name="Amina Noor")
        self.assertEqual(participant.display_name, "Amina Noor (P001)")


class ObservationTests(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(make_observation().is_usable)

    def test_missing_value_rejected(self):
        self.assertEqual(make_observation(heart_rate=None).status, Observation.REJECTED)

    def test_impossible_values_rejected(self):
        self.assertFalse(make_observation(heart_rate=265).is_usable)
        self.assertFalse(make_observation(activity_level=-0.2).is_usable)
        self.assertFalse(make_observation(temperature=50).is_usable)

    def test_missing_key_rejected(self):
        self.assertFalse(Observation.from_dict({"timestamp": 0, "heart_rate": 80}).is_usable)

    def test_low_quality_flagged(self):
        observation = make_observation(signal_quality=0.3)
        self.assertEqual(observation.status, Observation.FLAGGED)
        self.assertFalse(observation.is_usable)

    def test_problems_cannot_be_modified(self):
        self.assertIsInstance(make_observation(heart_rate=None).problems, tuple)


class BoundaryTests(unittest.TestCase):
    """Values exactly on a documented limit."""

    def test_signal_quality_exactly_at_minimum_is_usable(self):
        self.assertTrue(make_observation(signal_quality=0.60).is_usable)

    def test_signal_quality_just_below_minimum_is_flagged(self):
        self.assertEqual(make_observation(signal_quality=0.59).status, Observation.FLAGGED)

    def test_heart_rate_limits_are_inclusive(self):
        self.assertTrue(make_observation(heart_rate=35).is_usable)
        self.assertTrue(make_observation(heart_rate=205).is_usable)
        self.assertFalse(make_observation(heart_rate=34).is_usable)
        self.assertFalse(make_observation(heart_rate=206).is_usable)

    def test_activity_limits_are_inclusive(self):
        self.assertTrue(make_observation(activity_level=0.0).is_usable)
        self.assertTrue(make_observation(activity_level=1.0).is_usable)
        self.assertFalse(make_observation(activity_level=1.01).is_usable)

    def test_timestamp_zero_is_accepted_but_negative_is_not(self):
        self.assertTrue(make_observation(timestamp=0).is_usable)
        self.assertFalse(make_observation(timestamp=-1).is_usable)

    def test_exactly_minimum_usable_observations_is_enough(self):
        participant = Participant.from_profile(PROFILE)
        analyzer = SessionAnalyzer()
        six = Session("FIT-2026-001", participant, [make_observation(t) for t in range(6)])
        self.assertNotEqual(analyzer.analyze(six)["classification"], "insufficient data")
        five = Session("FIT-2026-001", participant, [make_observation(t) for t in range(5)])
        self.assertEqual(analyzer.analyze(five)["classification"], "insufficient data")


class SessionTests(unittest.TestCase):
    def test_composition_and_counts(self):
        observations = [make_observation(t) for t in range(5)]
        observations.append(make_observation(5, heart_rate=None))
        session = Session("FIT-2026-001", Participant.from_profile(PROFILE), observations)
        counts = session.counts()
        self.assertEqual((counts["total"], counts["usable"], counts["rejected"]), (6, 5, 1))
        self.assertIsInstance(session.participant, Participant)

    def test_duplicate_timestamp_rejected(self):
        session = Session("FIT-2026-001", Participant.from_profile(PROFILE),
                          [make_observation(1), make_observation(1)])
        self.assertEqual(session.counts()["rejected"], 1)

    def test_only_observation_objects_accepted(self):
        session = Session("FIT-2026-001", Participant.from_profile(PROFILE))
        with self.assertRaises(TypeError):
            session.add_observation({"timestamp": 0})

    def test_session_id_can_be_validated(self):
        with self.assertRaises(InvalidIdentifierError):
            Session("FIT-26-1", Participant.from_profile(PROFILE), validate_id=True)


class RepositoryTests(unittest.TestCase):
    def test_loads_official_participants(self):
        repository, report = ParticipantRepository.from_csv(PROFILES_CSV)
        self.assertEqual(len(repository), 3)
        self.assertEqual(repository.ids(), ("P001", "P002", "P003"))
        self.assertEqual(report.rejected_rows, 0)
        self.assertEqual(repository.get("P001").name, "Amina Noor")

    def test_unknown_participant_raises_custom_error(self):
        repository, _ = ParticipantRepository.from_csv(PROFILES_CSV)
        with self.assertRaises(UnknownParticipantError) as caught:
            repository.get("P999")
        self.assertEqual(caught.exception.participant_id, "P999")
        self.assertIsInstance(caught.exception, InvalidRecordError)  # inheritance

    def test_only_participants_can_be_stored(self):
        with self.assertRaises(TypeError):
            ParticipantRepository().add("P001")


class LoaderTests(unittest.TestCase):
    """Reading the official session files, valid and invalid."""

    @classmethod
    def setUpClass(cls):
        cls.repository, _ = ParticipantRepository.from_csv(PROFILES_CSV)

    def load(self, paths):
        loader = SessionLoader(self.repository)
        return loader.load_files(paths, LoadReport())

    def test_valid_file_is_fully_accepted(self):
        sessions, report = self.load([SESSIONS_CSV])
        self.assertEqual(report.rejected_rows, 0)
        self.assertEqual(report.accepted_rows, 29)
        self.assertEqual([s.session_id for s in sessions],
                         ["FIT-2026-001", "FIT-2026-002", "FIT-2026-003",
                          "FIT-2026-004", "FIT-2026-005"])

    def test_values_are_converted_to_numbers(self):
        sessions, _ = self.load([SESSIONS_CSV])
        observation = sessions[0].usable_observations()[0]
        self.assertIsInstance(observation.heart_rate, int)
        self.assertIsInstance(observation.value("temperature"), float)
        self.assertIsInstance(observation.timestamp, int)

    def test_invalid_file_rejects_every_broken_row(self):
        _, report = self.load([INVALID_CSV])
        self.assertEqual(report.rejected_rows, 10)
        fields = sorted({record.field for record in report.rejected})
        self.assertEqual(fields, ["activity_level", "heart_rate", "participant_id",
                                  "row", "session_id", "signal_quality",
                                  "skin_response", "timestamp"])

    def test_every_rejection_names_its_source_row_and_reason(self):
        _, report = self.load([INVALID_CSV])
        for record in report.rejected:
            with self.subTest(row=record.row_number):
                self.assertEqual(record.source, INVALID_CSV.name)
                self.assertGreater(record.row_number, 1)
                self.assertTrue(record.reason)
                self.assertTrue(record.field)

    def test_specific_rejection_reasons(self):
        _, report = self.load([INVALID_CSV])
        reasons = {record.row_number: record.reason for record in report.rejected}
        self.assertIn("not a whole number", reasons[3])        # heart_rate "fast"
        self.assertIn("does not match", reasons[4])            # participant "001"
        self.assertIn("empty", reasons[5])                     # missing activity_level
        self.assertIn("outside the possible range", reasons[6])  # signal_quality 1.40
        self.assertIn("does not match", reasons[7])            # session "FIT-26-102"
        self.assertIn("unknown participant", reasons[8])       # P999
        self.assertIn("missing the column", reasons[12])       # short row

    def test_reading_continues_after_a_bad_row(self):
        sessions, report = self.load([INVALID_CSV])
        self.assertEqual(report.accepted_rows, 1)  # the one good row in the file
        self.assertEqual([s.session_id for s in sessions], ["FIT-2026-101"])

    def test_sessions_are_connected_to_participants(self):
        sessions, _ = self.load([SESSIONS_CSV])
        for session in sessions:
            with self.subTest(session=session.session_id):
                self.assertIsInstance(session.participant, Participant)
                self.assertIn(session.participant.participant_id, self.repository)

    def test_rows_are_grouped_by_session_identifier(self):
        sessions, _ = self.load([SESSIONS_CSV, INVALID_CSV])
        counts = {s.session_id: len(s) for s in sessions}
        self.assertEqual(counts["FIT-2026-001"], 6)
        self.assertEqual(counts["FIT-2026-005"], 5)
        self.assertEqual(counts["FIT-2026-101"], 1)

    def test_loader_requires_a_repository(self):
        with self.assertRaises(TypeError):
            SessionLoader({"P001": "not a repository"})


class MissingFileTests(unittest.TestCase):
    """Missing, unreadable and malformed input files."""

    def test_missing_profile_file_raises_clear_error(self):
        with self.assertRaises(FitnessDataError) as caught:
            ParticipantRepository.from_csv(DATA / "does_not_exist.csv")
        self.assertIn("not found", str(caught.exception))

    def test_missing_session_file_is_reported_but_does_not_stop_the_run(self):
        repository, _ = ParticipantRepository.from_csv(PROFILES_CSV)
        loader = SessionLoader(repository)
        sessions, report = loader.load_files([DATA / "missing.csv", SESSIONS_CSV], LoadReport())
        self.assertEqual(len(sessions), 5)              # the good file was still read
        self.assertEqual(report.rejected[0].field, "file")
        self.assertIn("not found", report.rejected[0].reason)

    def test_non_csv_filename_is_refused(self):
        with self.assertRaises(FitnessDataError):
            list(read_rows(Path("participants.txt")))

    def test_empty_file_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as folder:
            empty = Path(folder) / "empty.csv"
            empty.write_text("", encoding="utf-8")
            with self.assertRaises(FitnessDataError) as caught:
                list(read_rows(empty))
            self.assertIn("empty", str(caught.exception))

    def test_pipeline_reports_a_missing_profile_file(self):
        pipeline = AnalysisPipeline()
        with self.assertRaises(FitnessDataError):
            pipeline.run(DATA / "no_such_profiles.csv", [SESSIONS_CSV], None)


class OutputTests(unittest.TestCase):
    """The three generated files, written into a temporary folder."""

    def run_into(self, folder):
        return AnalysisPipeline().run(PROFILES_CSV, [SESSIONS_CSV, INVALID_CSV], folder)

    def test_creates_missing_output_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "new" / "nested"
            self.assertFalse(target.exists())
            ensure_output_directory(target)
            self.assertTrue(target.is_dir())

    def test_writes_the_three_required_files(self):
        with tempfile.TemporaryDirectory() as folder:
            self.run_into(folder)
            for name in (SUMMARY_FILENAME, REPORT_FILENAME, REJECTED_FILENAME):
                with self.subTest(name=name):
                    self.assertTrue((Path(folder) / name).is_file())

    def test_summary_csv_has_one_row_per_session(self):
        with tempfile.TemporaryDirectory() as folder:
            outcome = self.run_into(folder)
            with open(Path(folder) / SUMMARY_FILENAME, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), len(outcome["results"]))
            self.assertEqual(rows[0]["session_id"], "FIT-2026-001")
            self.assertEqual(rows[0]["classification"], "resting")
            self.assertEqual(rows[0]["participant_name"], "Amina Noor")

    def test_rejected_file_lists_every_rejected_row(self):
        with tempfile.TemporaryDirectory() as folder:
            self.run_into(folder)
            text = (Path(folder) / REJECTED_FILENAME).read_text(encoding="utf-8")
            self.assertIn("REJECTED ROWS (10 total)", text)
            self.assertIn("FIT-26-102", text)
            self.assertIn("unknown participant", text)
            self.assertIn("FLAGGED ROWS", text)

    def test_report_file_explains_each_session(self):
        with tempfile.TemporaryDirectory() as folder:
            self.run_into(folder)
            text = (Path(folder) / REPORT_FILENAME).read_text(encoding="utf-8")
            for session_id in EXPECTED_CSV_RESULTS:
                with self.subTest(session=session_id):
                    self.assertIn(session_id, text)
            self.assertIn("CLASSIFICATION: RECOVERING", text)

    def test_running_twice_produces_identical_files(self):
        with tempfile.TemporaryDirectory() as folder:
            self.run_into(folder)
            first = {name: (Path(folder) / name).read_text(encoding="utf-8")
                     for name in (SUMMARY_FILENAME, REPORT_FILENAME, REJECTED_FILENAME)}
            self.run_into(folder)
            for name, content in first.items():
                with self.subTest(name=name):
                    self.assertEqual((Path(folder) / name).read_text(encoding="utf-8"), content)


class PipelineTests(unittest.TestCase):
    """The whole program, end to end, on the official files."""

    @classmethod
    def setUpClass(cls):
        cls.outcome = AnalysisPipeline().run(PROFILES_CSV, [SESSIONS_CSV, INVALID_CSV], None)

    def test_classifications_match_expectations(self):
        actual = {result["session_id"]: result["classification"]
                  for result in self.outcome["results"]}
        self.assertEqual(actual, EXPECTED_CSV_RESULTS)

    def test_totals(self):
        totals = self.outcome["totals"]
        self.assertEqual(totals["participants_loaded"], 3)
        self.assertEqual(totals["accepted_rows"], 33)
        self.assertEqual(totals["flagged_rows"], 5)
        self.assertEqual(totals["rejected_rows"], 10)
        self.assertEqual(totals["sessions_analyzed"], 6)

    def test_poor_quality_session_is_insufficient_not_misclassified(self):
        result = next(r for r in self.outcome["results"] if r["session_id"] == "FIT-2026-005")
        self.assertEqual(result["classification"], "insufficient data")
        self.assertEqual(result["observation_counts"]["flagged"], 5)
        self.assertEqual(result["observation_counts"]["usable"], 0)

    def test_recovery_session_is_detected_from_the_peak(self):
        result = next(r for r in self.outcome["results"] if r["session_id"] == "FIT-2026-004")
        recovery = result["recovery"]
        self.assertTrue(recovery["detected"])
        self.assertEqual(recovery["peak_hr"], 151)
        self.assertEqual(recovery["peak_timestamp"], 2)  # peak in the middle, not at the start

    def test_completion_summary_mentions_counts(self):
        summary = AnalysisPipeline.format_completion_summary(self.outcome)
        self.assertIn("Rows accepted", summary)
        self.assertIn("Rows rejected", summary)


class AnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = SessionAnalyzer()

    def analyze(self, scenario, seed, windows=12):
        profile, observations = generate_fitness_data("P001", scenario, seed, windows)
        return self.analyzer.analyze(
            Session.from_raw_data("FIT-2026-001", profile, observations))

    def test_generated_scenarios_many_seeds(self):
        for scenario in available_scenarios():
            for seed in range(100):
                for windows in (12, 20, 40):
                    with self.subTest(scenario=scenario, seed=seed, windows=windows):
                        result = self.analyze(scenario, seed, windows)
                        self.assertEqual(result["classification"], EXPECTED_LABELS[scenario])

    def test_sample_scenarios(self):
        for scenario in get_all_scenarios():
            with self.subTest(scenario=scenario["name"]):
                session = Session.from_raw_data("FIT-2026-001", scenario["profile"],
                                                scenario["observations"])
                result = self.analyzer.analyze(session)
                self.assertEqual(result["classification"], scenario["expected"])

    def test_result_is_structured_dictionary(self):
        result = self.analyze("moderate_activity", 1)
        for key in ("classification", "explanation", "observation_counts", "summary",
                    "comparison_with_reference", "recovery", "excluded_observations",
                    "participant_name", "sources"):
            self.assertIn(key, result)
        self.assertEqual(result["observation_counts"]["usable"], 12)

    def test_recovery_detected_only_in_recovery(self):
        self.assertTrue(self.analyze("recovery", 3)["recovery"]["detected"])
        self.assertFalse(self.analyze("high_activity", 3)["recovery"]["detected"])

    def test_empty_session(self):
        session = Session("FIT-2026-001", Participant.from_profile(PROFILE))
        self.assertEqual(self.analyzer.analyze(session)["classification"], "insufficient data")

    def test_custom_rule_order_uses_overridden_methods(self):
        class AlwaysTestRule(ClassificationRule):
            label = "test label"

            def matches(self, evidence):
                return True

        result = SessionAnalyzer([AlwaysTestRule()]).analyze(
            Session("FIT-2026-001", Participant.from_profile(PROFILE)))
        self.assertEqual(result["classification"], "test label")

    def test_base_rule_is_abstract(self):
        with self.assertRaises(NotImplementedError):
            ClassificationRule().matches({})

    def test_recovery_rule_thresholds(self):
        evidence = {"recovery": {"peak_increase": 60, "drop_from_peak": 40,
                                 "activity_drop": 0.5, "end_hr_increase": 20,
                                 "mean_hr_increase": 40, "hr_slope": -3,
                                 "activity_slope": -0.05, "post_peak_hr_slope": -4,
                                 "post_peak_activity_slope": -0.06}}
        self.assertTrue(RecoveryRule().matches(evidence))
        # Too small a drop from the peak is not recovery.
        evidence["recovery"]["drop_from_peak"] = 10
        self.assertFalse(RecoveryRule().matches(evidence))
        # Neither is a session that never settles back toward the baseline.
        evidence["recovery"]["drop_from_peak"] = 40
        evidence["recovery"]["end_hr_increase"] = 39
        self.assertFalse(RecoveryRule().matches(evidence))

    def test_report_contains_key_information(self):
        report = format_report(self.analyze("poor_quality", 1))
        self.assertIn("INSUFFICIENT DATA", report)
        self.assertIn("rejected", report)


if __name__ == "__main__":
    unittest.main(verbosity=1)
