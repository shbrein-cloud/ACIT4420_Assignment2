"""Scenario data for the Smart Fitness Session Analyzer.

Five scenarios come from the instructor-supplied generator (one per required
case). Three extra scenarios are built by hand to test edge cases that the
generator does not produce on its own.

The ``expected`` value is the label our rules should give. It is used by the
overview table in main.py and by tests.py; the analyzer itself never sees it.
"""

import copy

from data_generator import generate_fitness_data

GENERATED_SCENARIOS = [
    {"name": "resting", "scenario": "resting", "participant_id": "P001",
     "seed": 11, "windows": 12, "expected": "resting",
     "description": "Participant sitting still; values close to baseline."},
    {"name": "moderate_activity", "scenario": "moderate_activity",
     "participant_id": "P002", "seed": 42, "windows": 12,
     "expected": "moderate activity",
     "description": "Steady moderate exercise such as brisk walking."},
    {"name": "high_activity", "scenario": "high_activity", "participant_id": "P003",
     "seed": 7, "windows": 12, "expected": "high activity",
     "description": "Intense exercise such as running intervals."},
    {"name": "recovery", "scenario": "recovery", "participant_id": "P004",
     "seed": 42, "windows": 12, "expected": "recovering",
     "description": "Hard exercise followed by a cool-down."},
    {"name": "poor_quality", "scenario": "poor_quality", "participant_id": "P005",
     "seed": 3, "windows": 12, "expected": "insufficient data",
     "description": "Loose sensor: missing, impossible and low-quality values."},
]


def load_generated(spec):
    """Return (profile, observations) for one generated scenario spec."""
    return generate_fitness_data(
        participant_id=spec["participant_id"],
        scenario=spec["scenario"],
        seed=spec["seed"],
        number_of_windows=spec["windows"],
    )


def partially_corrupted_session():
    """Moderate session where a few windows are damaged in different ways.

    Most windows are fine, so the session should still be classified, while
    the damaged windows are reported as excluded.
    """
    profile, observations = generate_fitness_data("P006", "moderate_activity", seed=8)
    observations = copy.deepcopy(observations)
    observations[2]["heart_rate"] = None                 # missing value
    del observations[5]["temperature"]                   # missing field
    observations[7]["skin_response"] = "high"            # wrong type
    observations[9]["signal_quality"] = 0.35             # poor quality -> flagged
    observations[10]["timestamp"] = observations[3]["timestamp"]  # duplicate
    return profile, observations


def too_few_observations_session():
    """Only six windows, and two of them have weak signal quality.

    Four usable windows are not enough for a reliable classification.
    """
    profile, observations = generate_fitness_data("P007", "resting", seed=5,
                                                  number_of_windows=6)
    observations = copy.deepcopy(observations)
    observations[1]["signal_quality"] = 0.40
    observations[4]["signal_quality"] = 0.52
    return profile, observations


def handcrafted_recovery_session():
    """Small hand-written session: a cool-down after a sprint.

    Written directly as dictionaries, showing the program does not depend on
    the generator.
    """
    profile = {"participant_id": "P008", "baseline_heart_rate": 64,
               "baseline_skin_response": 1.6, "baseline_temperature": 32.4}
    heart_rates = [150, 144, 136, 124, 112, 101, 92, 84, 78, 74]
    activity = [0.92, 0.85, 0.70, 0.55, 0.40, 0.30, 0.22, 0.15, 0.12, 0.10]
    observations = []
    for t, (hr, act) in enumerate(zip(heart_rates, activity)):
        observations.append({
            "timestamp": t, "heart_rate": hr,
            "skin_response": round(2.4 - 0.07 * t, 2),
            "temperature": round(33.1 - 0.05 * t, 2),
            "activity_level": act, "signal_quality": 0.95,
        })
    return profile, observations


CUSTOM_SCENARIOS = [
    {"name": "partially_corrupted", "loader": partially_corrupted_session,
     "expected": "moderate activity",
     "description": "Moderate session with five damaged windows."},
    {"name": "too_few_observations", "loader": too_few_observations_session,
     "expected": "insufficient data",
     "description": "Short session with only four trustworthy windows."},
    {"name": "handwritten_cooldown", "loader": handcrafted_recovery_session,
     "expected": "recovering",
     "description": "Hand-written cool-down after a sprint."},
]


def get_all_scenarios():
    """All scenarios as a list of dictionaries with profile and observations."""
    scenarios = []
    for spec in GENERATED_SCENARIOS:
        profile, observations = load_generated(spec)
        scenarios.append({"name": spec["name"], "description": spec["description"],
                          "expected": spec["expected"], "profile": profile,
                          "observations": observations})
    for spec in CUSTOM_SCENARIOS:
        profile, observations = spec["loader"]()
        scenarios.append({"name": spec["name"], "description": spec["description"],
                          "expected": spec["expected"], "profile": profile,
                          "observations": observations})
    return scenarios
