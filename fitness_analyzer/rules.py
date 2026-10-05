"""Classification rules.

Each rule is a small class that answers two questions about the session
evidence (a dictionary produced by SessionAnalyzer):

* ``matches(evidence)`` - does this label describe the session?
* ``explain(evidence)`` - why (in plain language)?

All rules share the same interface through the ClassificationRule base class
and override these two methods. The analyzer only talks to the base-class
interface, so adding a new label means adding a new subclass - the analyzer
itself does not change.
"""

from .calculations import format_value


class ClassificationRule:
    """Base class for one session label."""

    label = "unclassified"

    def matches(self, evidence):
        raise NotImplementedError("Subclasses must implement matches()")

    def explain(self, evidence):
        return "The session was labelled '{}'.".format(self.label)

    def describe_thresholds(self):
        """Short human-readable description of the rule, for documentation."""
        return self.label

    def __repr__(self):
        return "{}(label={!r})".format(type(self).__name__, self.label)


class InsufficientDataRule(ClassificationRule):
    label = "insufficient data"
    MIN_USABLE_OBSERVATIONS = 6
    MIN_USABLE_RATIO = 0.5

    def matches(self, evidence):
        return (evidence["usable"] < self.MIN_USABLE_OBSERVATIONS
                or evidence["usable_ratio"] < self.MIN_USABLE_RATIO)

    def explain(self, evidence):
        return ("Only {} of {} observations ({:.0%}) were usable. At least {} usable "
                "observations and {:.0%} of the session are needed for a reliable "
                "classification.").format(
                    evidence["usable"], evidence["total"], evidence["usable_ratio"],
                    self.MIN_USABLE_OBSERVATIONS, self.MIN_USABLE_RATIO)

    def describe_thresholds(self):
        return "fewer than {} usable observations, or under {:.0%} usable".format(
            self.MIN_USABLE_OBSERVATIONS, self.MIN_USABLE_RATIO)


class RecoveryRule(ClassificationRule):
    """Real effort during the session, then a clear wind-down at the end.

    Improved for Assignment II. The Assignment I version compared only the
    start of the session with the end, so it recognised a session that *began*
    high and fell, but missed the common shape where a participant starts at
    rest, works hard in the middle and cools down afterwards. This version
    measures the decline from the session's peak heart rate instead, which
    covers both shapes.
    """

    label = "recovering"
    MIN_PEAK_INCREASE = 20        # bpm above baseline at the peak
    MIN_DROP_FROM_PEAK = 15       # bpm, peak minus the end-segment mean
    MIN_RETURN_FRACTION = 0.40    # share of the peak elevation that must be recovered
    MIN_ACTIVITY_DROP = 0.20      # activity units, peak activity minus end activity
    MAX_END_SHARE_OF_MEAN = 0.75  # the end must be closer to baseline than the average

    def matches(self, evidence):
        recovery = evidence["recovery"]
        # The end of the session must be clearly closer to the personal baseline
        # than the session average. Without this a flat session whose highest
        # reading happens to fall early can imitate a wind-down.
        settled = (recovery["mean_hr_increase"] > 0
                   and recovery["end_hr_increase"]
                   <= self.MAX_END_SHARE_OF_MEAN * recovery["mean_hr_increase"])
        return (recovery["peak_increase"] >= self.MIN_PEAK_INCREASE
                and recovery["drop_from_peak"] >= self.MIN_DROP_FROM_PEAK
                and recovery["drop_from_peak"]
                >= self.MIN_RETURN_FRACTION * recovery["peak_increase"]
                and recovery["activity_drop"] >= self.MIN_ACTIVITY_DROP
                and settled
                and recovery["hr_slope"] < 0
                and recovery["activity_slope"] < 0
                and recovery["post_peak_hr_slope"] < 0
                and recovery["post_peak_activity_slope"] < 0)

    def explain(self, evidence):
        r = evidence["recovery"]
        return ("The session contains real effort (peak heart rate {} bpm, {} bpm above "
                "baseline) followed by a clear wind-down: heart rate falls {} bpm from "
                "the peak to {} bpm at the end, and activity falls by {}. Heart rate and "
                "activity both decline after the peak, and at the end the heart rate is "
                "{} bpm above baseline.").format(
                    format_value(r["peak_hr"], 0), format_value(r["peak_increase"], 1),
                    format_value(r["drop_from_peak"], 1), format_value(r["end_hr"], 1),
                    format_value(r["activity_drop"], 2),
                    format_value(r["end_hr_increase"], 1))

    def describe_thresholds(self):
        return ("peak HR >= baseline + {} bpm, drop from peak >= {} bpm and >= {:.0%} of "
                "the peak elevation, activity drop >= {}, end elevation <= {:.0%} of the "
                "average elevation, and negative heart-rate and activity trends both "
                "overall and after the peak").format(
                    self.MIN_PEAK_INCREASE, self.MIN_DROP_FROM_PEAK,
                    self.MIN_RETURN_FRACTION, self.MIN_ACTIVITY_DROP,
                    self.MAX_END_SHARE_OF_MEAN)


class HighActivityRule(ClassificationRule):
    label = "high activity"
    MIN_HR_INCREASE = 42     # bpm above baseline
    MIN_ACTIVITY = 0.65

    def matches(self, evidence):
        return (evidence["hr_increase"] >= self.MIN_HR_INCREASE
                and evidence["mean_activity"] >= self.MIN_ACTIVITY)

    def explain(self, evidence):
        return ("Average heart rate is {} bpm above the personal baseline "
                "(threshold {}) and average activity is {} (threshold {}).").format(
                    format_value(evidence["hr_increase"], 1), self.MIN_HR_INCREASE,
                    format_value(evidence["mean_activity"], 2), self.MIN_ACTIVITY)

    def describe_thresholds(self):
        return "HR >= baseline + {} bpm AND activity >= {}".format(
            self.MIN_HR_INCREASE, self.MIN_ACTIVITY)


class ModerateActivityRule(ClassificationRule):
    label = "moderate activity"
    MIN_HR_INCREASE = 12
    MIN_ACTIVITY = 0.30

    def matches(self, evidence):
        return (evidence["hr_increase"] >= self.MIN_HR_INCREASE
                or evidence["mean_activity"] >= self.MIN_ACTIVITY)

    def explain(self, evidence):
        return ("Average heart rate is {} bpm above baseline and average activity "
                "is {}. At least one exceeds the moderate threshold ({} bpm / {}) "
                "but the high-activity thresholds are not both reached.").format(
                    format_value(evidence["hr_increase"], 1),
                    format_value(evidence["mean_activity"], 2),
                    self.MIN_HR_INCREASE, self.MIN_ACTIVITY)

    def describe_thresholds(self):
        return "HR >= baseline + {} bpm OR activity >= {}".format(
            self.MIN_HR_INCREASE, self.MIN_ACTIVITY)


class RestingRule(ClassificationRule):
    label = "resting"
    MAX_HR_INCREASE = ModerateActivityRule.MIN_HR_INCREASE
    MAX_ACTIVITY = ModerateActivityRule.MIN_ACTIVITY

    def matches(self, evidence):
        return (evidence["hr_increase"] < self.MAX_HR_INCREASE
                and evidence["mean_activity"] < self.MAX_ACTIVITY)

    def explain(self, evidence):
        return ("Average heart rate stays close to the personal baseline ({} bpm "
                "difference, limit {}) and movement is low (activity {}, limit "
                "{}).").format(
                    format_value(evidence["hr_increase"], 1), self.MAX_HR_INCREASE,
                    format_value(evidence["mean_activity"], 2), self.MAX_ACTIVITY)

    def describe_thresholds(self):
        return "HR < baseline + {} bpm AND activity < {}".format(
            self.MAX_HR_INCREASE, self.MAX_ACTIVITY)
