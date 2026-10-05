"""Domain classes: Participant, Observation and Session."""

from .calculations import check_range, is_number, summarize
from .validation import validate_participant_id, validate_session_id


class Participant:
    """A person wearing the device, together with personal reference values.

    The reference (baseline) values are stored in protected attributes and can
    only be changed through validating property setters, so a Participant can
    never hold an impossible baseline.
    """

    HEART_RATE_LIMITS = (30, 120)       # plausible resting heart rate, bpm
    SKIN_RESPONSE_LIMITS = (0.0, 50.0)  # simulated units
    TEMPERATURE_LIMITS = (25.0, 42.0)   # skin temperature, degrees C

    def __init__(self, participant_id, baseline_heart_rate, baseline_skin_response,
                 baseline_temperature, name=None):
        # The identifier is checked against the documented regular expression.
        self._participant_id = validate_participant_id(participant_id)
        self._name = (name or "").strip() or None
        # Assigning through the properties runs the validation below.
        self.baseline_heart_rate = baseline_heart_rate
        self.baseline_skin_response = baseline_skin_response
        self.baseline_temperature = baseline_temperature

    @classmethod
    def from_profile(cls, profile):
        """Alternative constructor from a profile dictionary.

        Used both by the Assignment I data generator and by the CSV loader,
        which builds the same dictionary shape from a ``participants.csv`` row.
        """
        if not isinstance(profile, dict):
            raise TypeError("profile must be a dictionary")
        required = ("participant_id", "baseline_heart_rate",
                    "baseline_skin_response", "baseline_temperature")
        missing = [key for key in required if key not in profile]
        if missing:
            raise ValueError("profile is missing: " + ", ".join(missing))
        return cls(*(profile[key] for key in required), name=profile.get("name"))

    @staticmethod
    def _validated(name, value, limits):
        problem = check_range(name, value, *limits)
        if problem:
            raise ValueError("Invalid participant reference: " + problem)
        return value

    @property
    def participant_id(self):
        return self._participant_id

    @property
    def name(self):
        return self._name

    @property
    def display_name(self):
        """Name and identifier together, for reports."""
        return "{} ({})".format(self._name, self._participant_id) if self._name \
            else self._participant_id

    @property
    def baseline_heart_rate(self):
        return self._baseline_heart_rate

    @baseline_heart_rate.setter
    def baseline_heart_rate(self, value):
        self._baseline_heart_rate = self._validated(
            "baseline_heart_rate", value, self.HEART_RATE_LIMITS)

    @property
    def baseline_skin_response(self):
        return self._baseline_skin_response

    @baseline_skin_response.setter
    def baseline_skin_response(self, value):
        self._baseline_skin_response = self._validated(
            "baseline_skin_response", value, self.SKIN_RESPONSE_LIMITS)

    @property
    def baseline_temperature(self):
        return self._baseline_temperature

    @baseline_temperature.setter
    def baseline_temperature(self, value):
        self._baseline_temperature = self._validated(
            "baseline_temperature", value, self.TEMPERATURE_LIMITS)

    def reference_values(self):
        """Reference values keyed by the matching observation field name."""
        return {
            "heart_rate": self._baseline_heart_rate,
            "skin_response": self._baseline_skin_response,
            "temperature": self._baseline_temperature,
        }

    def __repr__(self):
        return "Participant({!r}, baseline HR={} bpm)".format(
            self._participant_id, self._baseline_heart_rate)


class Observation:
    """One measurement window from the wearable device.

    Every observation validates itself when it is created and ends up in one of
    three states:

    * ``valid``    - all values present and physically possible;
    * ``rejected`` - a value is missing, not numeric or impossible;
    * ``flagged``  - values are possible but the signal quality is too low to
                     trust them.

    Only ``valid`` observations are used in the analysis.
    """

    MEASUREMENT_FIELDS = ("heart_rate", "skin_response", "temperature",
                          "activity_level", "signal_quality")
    LIMITS = {
        "heart_rate": (35, 205),
        "skin_response": (0.0, 50.0),
        "temperature": (25.0, 42.0),
        "activity_level": (0.0, 1.0),
        "signal_quality": (0.0, 1.0),
    }
    MIN_SIGNAL_QUALITY = 0.60

    VALID = "valid"
    REJECTED = "rejected"
    FLAGGED = "flagged"

    def __init__(self, timestamp, heart_rate, skin_response, temperature,
                 activity_level, signal_quality, source=None):
        self._timestamp = timestamp
        self._source = source
        self._values = {
            "heart_rate": heart_rate,
            "skin_response": skin_response,
            "temperature": temperature,
            "activity_level": activity_level,
            "signal_quality": signal_quality,
        }
        self._problems = []
        self._status = self.VALID
        self._validate()

    @classmethod
    def from_dict(cls, data, source=None):
        """Build an observation from a raw dictionary.

        Missing keys are passed on as ``None`` so that they are reported as
        validation problems instead of crashing the program.
        """
        if not isinstance(data, dict):
            raise TypeError("observation data must be a dictionary")
        return cls(data.get("timestamp"),
                   *(data.get(name) for name in cls.MEASUREMENT_FIELDS),
                   source=source)

    def _validate(self):
        if not isinstance(self._timestamp, int) or isinstance(self._timestamp, bool) \
                or self._timestamp < 0:
            self._problems.append(
                "timestamp must be a non-negative integer ({!r})".format(self._timestamp))
        for name in self.MEASUREMENT_FIELDS:
            problem = check_range(name, self._values[name], *self.LIMITS[name])
            if problem:
                self._problems.append(problem)

        has_impossible_values = bool(self._problems)
        quality = self._values["signal_quality"]
        low_quality = is_number(quality) and quality < self.MIN_SIGNAL_QUALITY
        if low_quality:
            self._problems.append(
                "signal_quality {:.2f} is below the minimum {:.2f}".format(
                    quality, self.MIN_SIGNAL_QUALITY))
        # Impossible or missing values are more serious than low signal quality.
        if has_impossible_values:
            self._status = self.REJECTED
        elif low_quality:
            self._status = self.FLAGGED

    def reject(self, reason):
        """Mark the observation as unusable for a reason found by its session."""
        self._problems.append(reason)
        self._status = self.REJECTED

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def status(self):
        return self._status

    @property
    def is_usable(self):
        return self._status == self.VALID

    @property
    def problems(self):
        # Return a copy so callers cannot change the internal list.
        return tuple(self._problems)

    @property
    def source(self):
        """Where this observation came from, e.g. ``fitness_sessions.csv row 4``."""
        return self._source

    def value(self, name):
        if name not in self._values:
            raise KeyError("Unknown measurement: " + name)
        return self._values[name]

    @property
    def heart_rate(self):
        return self._values["heart_rate"]

    @property
    def activity_level(self):
        return self._values["activity_level"]

    def to_dict(self):
        data = {"timestamp": self._timestamp}
        data.update(self._values)
        return data

    def __repr__(self):
        return "Observation(t={}, HR={}, status={})".format(
            self._timestamp, self.heart_rate, self._status)


class Session:
    """A training session: one Participant plus an ordered list of Observations.

    This is the main example of composition: a Session *has a* Participant and
    *has* Observations, and delegates validation to the Observation objects.
    """

    def __init__(self, session_id, participant, observations=None, validate_id=False):
        if not isinstance(participant, Participant):
            raise TypeError("participant must be a Participant object")
        self._session_id = validate_session_id(session_id) if validate_id else str(session_id)
        self._participant = participant
        self._observations = []
        self._seen_timestamps = set()
        self._sources = []
        for observation in observations or []:
            self.add_observation(observation)

    @classmethod
    def from_raw_data(cls, session_id, profile, raw_observations):
        """Build a complete session from dictionaries (used with the generator)."""
        participant = Participant.from_profile(profile)
        session = cls(session_id, participant)
        for raw in raw_observations:
            session.add_observation(Observation.from_dict(raw))
        return session

    def add_observation(self, observation):
        if not isinstance(observation, Observation):
            raise TypeError("Only Observation objects can be added to a session")
        timestamp = observation.timestamp
        if observation.is_usable and timestamp in self._seen_timestamps:
            observation.reject("duplicate timestamp {}".format(timestamp))
        if observation.is_usable:
            self._seen_timestamps.add(timestamp)
        self._observations.append(observation)
        # Keep chronological order; rejected windows with bad timestamps go last.
        self._observations.sort(
            key=lambda o: o.timestamp if is_number(o.timestamp) else float("inf"))

    def record_source(self, source):
        """Remember which input file contributed rows to this session."""
        if source and source not in self._sources:
            self._sources.append(source)

    @property
    def session_id(self):
        return self._session_id

    @property
    def participant(self):
        return self._participant

    @property
    def observations(self):
        return tuple(self._observations)

    @property
    def sources(self):
        return tuple(self._sources)

    def observations_with_status(self, status):
        return [o for o in self._observations if o.status == status]

    def usable_observations(self):
        return self.observations_with_status(Observation.VALID)

    def usable_values(self, name):
        """All values of one measurement from the usable observations."""
        return [o.value(name) for o in self.usable_observations()]

    def summary(self):
        """Average, minimum, maximum and spread for every measurement."""
        return {name: summarize(self.usable_values(name))
                for name in Observation.MEASUREMENT_FIELDS}

    def counts(self):
        total = len(self._observations)
        usable = len(self.usable_observations())
        return {
            "total": total,
            "usable": usable,
            "rejected": len(self.observations_with_status(Observation.REJECTED)),
            "flagged": len(self.observations_with_status(Observation.FLAGGED)),
            "usable_ratio": round(usable / total, 2) if total else 0.0,
        }

    def __len__(self):
        return len(self._observations)

    def __repr__(self):
        return "Session({!r}, {!r}, {} observations)".format(
            self._session_id, self._participant.participant_id, len(self))
