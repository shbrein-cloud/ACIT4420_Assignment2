# Smart Fitness Session Analyzer

**Python Programming Assignment II – Option A: Smart Fitness Session Analyzer**
(continuation of Assignment I)

- **Student name:** _Sindre Hvesser Brein_
- **Student number:** _409906_

## Description

A fitness centre collects measurements from wearable devices. This program reads the
participant profiles and the session measurements from CSV files, validates every
record, groups the rows into sessions, connects each session to a known participant,
compares the measurements with that person's personal reference values, classifies
the session and writes three report files.

A session is classified as one of **resting**, **moderate activity**,
**high activity**, **recovering** or **insufficient data**. Rows that cannot be
trusted are rejected individually, with the file, row number, field and reason
recorded, and the program continues with the next row.

This builds on Assignment I, which analyzed the same kind of data held in Python
lists and dictionaries. The domain model and the classification rules are reused;
the CSV loading, identifier validation, error handling and file output are new, and
the recovery rule has been improved (see *Improvements since Assignment I*).

## Repository structure

```
.
|-- README.md
|-- main.py                     entry point and command-line interface
|-- tests.py                    74 automated tests (unittest, standard library)
|-- requirements.txt            states that only the standard library is used
|-- sample_data.py              Assignment I scenarios, still used as test fixtures
|-- data_generator.py           Assignment I generator (instructor-supplied, unmodified)
|-- example_usage.py            Assignment I example (instructor-supplied, unmodified)
|-- data/
|   |-- participants.csv              official file, unmodified
|   |-- fitness_sessions.csv          official file, unmodified
|   `-- fitness_sessions_invalid.csv  official file, unmodified
|-- output/                     created by the program (not committed)
`-- fitness_analyzer/           the application package
    |-- __init__.py
    |-- exceptions.py           the three custom exception classes
    |-- validation.py           regular-expression identifier checks, type conversion
    |-- calculations.py         standalone calculation and formatting functions
    |-- models.py               Participant, Observation, Session
    |-- rules.py                ClassificationRule and its five subclasses
    |-- analyzer.py             SessionAnalyzer
    |-- loaders.py              reading CSV files, ParticipantRepository, SessionLoader
    |-- outputs.py              writing the three report files
    |-- report.py               readable console text
    `-- pipeline.py             the end-to-end process used by main.py
```

The package is split so that each module has one responsibility: reading data,
validating it, modelling it, classifying it, and presenting it. `main.py` only
handles command-line arguments and printing.

## Installation and running

Requires Python 3.8 or newer. No packages need to be installed.

```bash
git clone https://github.com/shbrein-cloud/ACIT4420_Assignment2.git
cd REPOSITORY
python3 main.py
```

On systems where the command is `python` rather than `python3` (common on Windows),
use `python main.py` and `python tests.py`.

Running `python3 main.py` with no arguments uses the official files in `data/` and
writes to `output/`. The full command with explicit paths:

```bash
python3 main.py --profiles data/participants.csv \
                --sessions data/fitness_sessions.csv data/fitness_sessions_invalid.csv \
                --output output
```

Other options:

```bash
python3 main.py --print-report    # also print the full per-session report
python3 main.py --json            # print the structured results as JSON
python3 tests.py                  # run the tests
```

`--sessions` takes one or more files, because the assignment requires both the valid
and the intentionally invalid session file to be loaded. All paths are relative to the
repository root and are handled with `pathlib`, so no path has to be edited.

## Output files

The program creates the output directory if it does not exist and writes:

| File | Contents |
|---|---|
| `analysis_summary.csv` | one row per session: identifiers, classification, row counts, heart-rate summary, difference from baseline, mean activity, whether recovery was detected, source files |
| `analysis_report.txt` | a readable report per session: classification with its reason, counts, summaries, comparison with reference values and the recovery analysis |
| `rejected_records.txt` | every rejected row with its file, row number, session, field and reason, followed by the rows that were accepted but excluded for low signal quality |

All three are rewritten on every run and their contents depend only on the input
files, never on the clock, so running the program twice produces byte-identical
files and no manual cleanup is needed. A test checks this.

## Class design

| Class | Module | Responsibility |
|---|---|---|
| `Participant` | `models` | Identifier, name and personal reference values. Rejects impossible baselines. |
| `Observation` | `models` | One measurement window. Validates itself and becomes `valid`, `rejected` or `flagged`. |
| `Session` | `models` | One `Participant` plus its `Observation` objects in time order; rejects duplicate timestamps; provides counts and summaries. |
| `ClassificationRule` | `rules` | Base class defining `matches(evidence)` and `explain(evidence)`. |
| `InsufficientDataRule`, `RecoveryRule`, `HighActivityRule`, `ModerateActivityRule`, `RestingRule` | `rules` | One subclass per label, each with its own thresholds. |
| `SessionAnalyzer` | `analyzer` | Holds the rules, computes the evidence and returns the result dictionary. |
| `ParticipantRepository` | `loaders` | All known participants; `get()` raises `UnknownParticipantError` for unknown identifiers. |
| `SessionLoader` | `loaders` | Reads session CSV files, validates each row and groups rows into sessions. |
| `RejectedRecord`, `LoadReport` | `loaders` | One rejected row, and the running totals plus the list of rejections. |
| `AnalysisPipeline` | `pipeline` | Runs the whole process: load, analyze, write, summarise. |
| `FitnessDataError`, `InvalidIdentifierError`, `InvalidRecordError`, `UnknownParticipantError` | `exceptions` | The custom exceptions. |

Standalone functions live in `calculations.py` (`is_number`, `check_range`,
`summarize`, `compare_with_reference`, `linear_slope`, `split_start_and_end`,
`index_of_maximum`, `format_value`, `format_signed`), `validation.py`
(`validate_participant_id`, `validate_session_id`, `is_csv_filename`,
`require_present`, `to_int`, `to_float`), `report.py` and `outputs.py`.

### Where the OOP concepts are demonstrated

- **Composition:** a `Session` *has a* `Participant` and *has* `Observation` objects;
  a `SessionLoader` *has a* `ParticipantRepository`; a `SessionAnalyzer` *has*
  `ClassificationRule` objects; an `AnalysisPipeline` *has a* `SessionAnalyzer`.
- **Encapsulation:** `Participant` keeps its baselines in protected attributes exposed
  through validating property setters, so an invalid assignment raises `ValueError`
  and leaves the old value. `Observation` keeps `_values`, `_status` and `_problems`
  protected and returns `problems` as a tuple. `ParticipantRepository` hides its
  dictionary behind `get()`, `ids()` and `__contains__`.
- **Inheritance and overriding:** the five rule subclasses override `matches()`,
  `explain()` and `describe_thresholds()`; the analyzer uses only the base-class
  interface, so a new label needs no change to the analyzer. The exceptions form a
  second hierarchy, with `UnknownParticipantError` inheriting from
  `InvalidRecordError` so it can be caught either specifically or generally.
- **Class and static methods:** `Participant.from_profile()`, `Observation.from_dict()`,
  `Session.from_raw_data()` and `ParticipantRepository.from_csv()` are alternative
  constructors; `SessionAnalyzer.default_rules()` and
  `AnalysisPipeline.format_completion_summary()` are static methods.

## Reading and validating the CSV files

Files are opened with `open(path, newline="", encoding="utf-8")` and read with
`csv.DictReader`. Values are converted to `int` or `float` rather than left as
strings, rows are grouped by `session_id`, and every session is connected to a
participant from `participants.csv`.

### Identifier validation (regular expressions)

| Value | Pattern | Example |
|---|---|---|
| Participant ID | `^P\d{3}$` | `P001` |
| Session ID | `^FIT-\d{4}-\d{3}$` | `FIT-2026-001` |
| Input filename | `^[A-Za-z0-9_.-]+\.csv$` | `participants.csv` |

All three are anchored and matched with `re.fullmatch`, so `P001x` and `FIT-26-102`
are refused. Regular expressions are used only for these textual identifiers;
numeric limits are ordinary comparisons, as the assignment requires.

### Record validation

A row is **rejected**, and the run continues, when:

- it has more or fewer fields than the header (`row is missing the column(s): ...`);
- a required value is empty or missing;
- a value cannot be converted to its type (`heart_rate = 'fast' is not a whole number`);
- an identifier does not match its pattern;
- the participant is not in `participants.csv`;
- a measurement is outside its possible range: heart rate 35–205 bpm, skin response
  0–50, temperature 25–42 °C, activity 0–1, signal quality 0–1, timestamp ≥ 0;
- the timestamp is already used by another row in the same session.

A row whose values are all possible but whose **signal quality is below 0.60** is
**flagged**: it is accepted and counted, but excluded from the summaries and the
classification, because the sensor was not in reliable contact. Flagged rows are
listed in their own section of `rejected_records.txt`. This is the documented
poor-quality rule.

Every rejection records the source filename, the row number, the field and the reason.

## Error handling

Three custom exception classes are raised and handled:

| Exception | Raised when | Handled in |
|---|---|---|
| `InvalidIdentifierError` | an identifier fails its regular expression | `SessionLoader._load_one_row`, `ParticipantRepository.from_csv` |
| `InvalidRecordError` | a field is missing, untypeable or out of range | the same two places |
| `UnknownParticipantError` | a session row names a participant that does not exist | caught before `InvalidRecordError`, so it gets its own wording |

`FitnessDataError` is the shared base class, used for problems with a whole file.

Targeted `try`/`except` blocks:

1. `open_csv()` – `FileNotFoundError`, `PermissionError`, `OSError`.
2. `read_rows()` – `csv.Error` for a malformed file.
3. `to_int()` / `to_float()` – `ValueError`/`TypeError` on conversion.
4. `ParticipantRepository.get()` – `KeyError` turned into `UnknownParticipantError`.
5. `SessionLoader._load_one_row()` – the three custom exceptions, one row at a time.
6. `SessionLoader._load_one_file()` – a missing session file is reported and the
   remaining files are still read.
7. `ensure_output_directory()` and `_open_for_writing()` – `PermissionError`, `OSError`.
8. `main()` – `FitnessDataError`, printed to stderr with exit code 1.

There is no empty `except` block and no `except Exception` anywhere: each block names
the errors it can actually add context to, so a programming mistake still surfaces as
a normal traceback.

## Classification rules

Rules are checked in order and the first match wins. `HR increase` is the session's
average heart rate minus the participant's baseline.

1. **Insufficient data** – fewer than 6 usable observations, or under 50% of the rows usable.
2. **Recovering** – see below.
3. **High activity** – HR increase ≥ 42 bpm **and** activity ≥ 0.65.
4. **Moderate activity** – HR increase ≥ 12 bpm **or** activity ≥ 0.30.
5. **Resting** – HR increase < 12 bpm and activity < 0.30.

Recovery is checked before intensity because a cool-down has mid-range averages that
would otherwise read as moderate activity. Skin response and temperature are reported
and compared with the reference values but are not used to classify, because they move
far less clearly than heart rate and movement.

### Improvements since Assignment I

The Assignment I recovery rule compared the **first** third of a session with the last
third. That recognised a session which *begins* at peak effort, but missed the more
common shape where someone starts at rest, works hard in the middle and then cools
down — exactly `FIT-2026-004` in the official data, which Assignment I would have
labelled *moderate activity*.

The rule now measures the decline **from the session's peak heart rate**. A session is
*recovering* when all of these hold:

- the peak is at least 20 bpm above the personal baseline (there was real effort);
- heart rate falls at least 15 bpm from the peak to the final windows, and that fall is
  at least 40% of the peak elevation (it is genuinely returning toward baseline);
- activity falls at least 0.20 from its peak;
- the end of the session sits at no more than 75% of the session's average elevation
  above baseline (the session really has settled, not just fluctuated);
- heart rate and activity both trend downward, measured over the whole session *and*
  over the part after the peak.

The thresholds were checked against 40,000 generated sessions (5 scenarios × 2,000
seeds × 4 session lengths): 39,999 were labelled as expected. The single exception is
a 6-window moderate session whose random noise genuinely looks like a wind-down; it is
left as it is rather than over-fitting the rule to one case. `tests.py` repeats a
smaller version of this check (1,500 sessions).

## Results for the official data

| Session | Participant | Result | Why |
|---|---|---|---|
| `FIT-2026-001` | Amina Noor | resting | heart rate 0.8 bpm above baseline, activity 0.09 |
| `FIT-2026-002` | Jonas Berg | moderate activity | +28.0 bpm, activity 0.50 |
| `FIT-2026-003` | Maya Chen | high activity | +69.5 bpm, activity 0.75 |
| `FIT-2026-004` | Amina Noor | recovering | peak 151 bpm at t=2, down to 93 bpm at the end |
| `FIT-2026-005` | Jonas Berg | insufficient data | all 5 rows below the signal-quality limit |
| `FIT-2026-101` | Amina Noor | insufficient data | only 1 of 5 rows survived validation |

The other two session identifiers in the invalid file produce no session at all:
every `FIT-2026-102` row is rejected (bad session ID, unknown participant, text
timestamp, negative heart rate, impossible skin response and temperature), and the
single `FIT-2026-103` row is one column short.

## Example output

Console output of `python3 main.py`:

```
Rejected rows (10):
  fitness_sessions_invalid.csv row 3: [heart_rate] heart_rate = 'fast' is not a whole number
  fitness_sessions_invalid.csv row 4: [participant_id] participant_id '001' does not match the required format ^P\d{3}$
  fitness_sessions_invalid.csv row 5: [activity_level] required field 'activity_level' is empty
  fitness_sessions_invalid.csv row 6: [signal_quality] signal_quality = 1.4 is outside the possible range 0.0-1.0
  fitness_sessions_invalid.csv row 7: [session_id] session_id 'FIT-26-102' does not match the required format ^FIT-\d{4}-\d{3}$
  fitness_sessions_invalid.csv row 8: [participant_id] unknown participant 'P999' (known participants: P001, P002, P003)
  fitness_sessions_invalid.csv row 9: [timestamp] timestamp = 'two' is not a whole number
  fitness_sessions_invalid.csv row 10: [heart_rate] heart_rate = -15 is outside the possible range 35-205
  fitness_sessions_invalid.csv row 11: [skin_response] skin_response = -0.5 is outside the possible range 0.0-50.0
  fitness_sessions_invalid.csv row 12: [row] row is missing the column(s): signal_quality

Sessions analyzed:
  FIT-2026-001   resting              6 of 6 observations usable
  FIT-2026-002   moderate activity    6 of 6 observations usable
  FIT-2026-003   high activity        6 of 6 observations usable
  FIT-2026-004   recovering           6 of 6 observations usable
  FIT-2026-005   insufficient data    0 of 5 observations usable
  FIT-2026-101   insufficient data    1 of 1 observations usable

Completed.
  Participants loaded : 3
  Files read          : participants.csv, fitness_sessions.csv, fitness_sessions_invalid.csv
  Rows accepted       : 33 (of which 5 flagged as low quality)
  Rows rejected       : 10
  Sessions analyzed   : 6
  Report files created:
    output/analysis_summary.csv
    output/analysis_report.txt
    output/rejected_records.txt
```

`output/analysis_summary.csv`:

```
session_id,participant_id,participant_name,classification,observations_total,observations_usable,observations_rejected,observations_flagged,usable_ratio,mean_heart_rate,min_heart_rate,max_heart_rate,heart_rate_vs_baseline,mean_activity_level,mean_signal_quality,recovery_detected,source_files
FIT-2026-001,P001,Amina Noor,resting,6,6,0,0,1.0,68.83,68,70,0.83,0.09,0.97,no,fitness_sessions.csv
FIT-2026-002,P002,Jonas Berg,moderate activity,6,6,0,0,1.0,102.00,78,118,28.00,0.50,0.94,no,fitness_sessions.csv
FIT-2026-003,P003,Maya Chen,high activity,6,6,0,0,1.0,132.50,72,162,69.50,0.75,0.94,no,fitness_sessions.csv
FIT-2026-004,P001,Amina Noor,recovering,6,6,0,0,1.0,113.17,72,151,45.17,0.55,0.96,yes,fitness_sessions.csv
FIT-2026-005,P002,Jonas Berg,insufficient data,5,0,0,5,0.0,n/a,n/a,n/a,n/a,n/a,n/a,no,fitness_sessions.csv
FIT-2026-101,P001,Amina Noor,insufficient data,1,1,0,0,1.0,72.00,72,72,4.00,0.10,0.96,no,fitness_sessions_invalid.csv
```

`output/rejected_records.txt`:

```
SMART FITNESS SESSION ANALYZER
Rejected and flagged records

REJECTED ROWS (10 total)
----------------------------------------------------------------------
fitness_sessions_invalid.csv row 3    session=FIT-2026-101  field=heart_rate       heart_rate = 'fast' is not a whole number
fitness_sessions_invalid.csv row 4    session=FIT-2026-101  field=participant_id   participant_id '001' does not match the required format ^P\d{3}$
fitness_sessions_invalid.csv row 5    session=FIT-2026-101  field=activity_level   required field 'activity_level' is empty
fitness_sessions_invalid.csv row 6    session=FIT-2026-101  field=signal_quality   signal_quality = 1.4 is outside the possible range 0.0-1.0
fitness_sessions_invalid.csv row 7    session=FIT-26-102    field=session_id       session_id 'FIT-26-102' does not match the required format ^FIT-\d{4}-\d{3}$
fitness_sessions_invalid.csv row 8    session=FIT-2026-102  field=participant_id   unknown participant 'P999' (known participants: P001, P002, P003)
fitness_sessions_invalid.csv row 9    session=FIT-2026-102  field=timestamp        timestamp = 'two' is not a whole number
fitness_sessions_invalid.csv row 10   session=FIT-2026-102  field=heart_rate       heart_rate = -15 is outside the possible range 35-205
fitness_sessions_invalid.csv row 11   session=FIT-2026-102  field=skin_response    skin_response = -0.5 is outside the possible range 0.0-50.0
fitness_sessions_invalid.csv row 12   session=FIT-2026-103  field=row              row is missing the column(s): signal_quality

FLAGGED ROWS - accepted but excluded from the analysis (5 total)
----------------------------------------------------------------------
fitness_sessions.csv row 26 session=FIT-2026-005  t=0    signal_quality 0.34 is below the minimum 0.60
fitness_sessions.csv row 27 session=FIT-2026-005  t=1    signal_quality 0.29 is below the minimum 0.60
fitness_sessions.csv row 28 session=FIT-2026-005  t=2    signal_quality 0.25 is below the minimum 0.60
fitness_sessions.csv row 29 session=FIT-2026-005  t=3    signal_quality 0.31 is below the minimum 0.60
fitness_sessions.csv row 30 session=FIT-2026-005  t=4    signal_quality 0.28 is below the minimum 0.60
```

## Tests

`python3 tests.py` runs 74 tests covering valid data, invalid data, missing files and
boundary values:

- **valid**: the official files load fully, values become numbers, rows group into
  sessions, each session is connected to a participant, classifications are as expected;
- **invalid**: all ten broken rows in `fitness_sessions_invalid.csv` are rejected with
  the right field and reason, and reading continues afterwards;
- **missing file**: a missing profile file raises a clear error; a missing session file
  is reported but the other files are still read; an empty file and a non-CSV filename
  are refused;
- **boundary**: signal quality exactly 0.60, heart rate exactly 35 and 205, activity
  exactly 0.0 and 1.0, timestamp 0, and exactly 6 usable observations versus 5;
- **output**: the directory is created when missing, all three files appear, the CSV has
  one row per session, and running twice produces identical files;
- **analysis**: 1,500 generated sessions, the Assignment I scenarios, the rule
  hierarchy and the structure of the result dictionary.

## Assumptions

- Signal quality below 0.60 means the reading cannot be trusted; such rows are kept and
  counted but excluded from the analysis.
- At least 6 usable observations, and at least half the rows of a session, are needed
  before a session is classified at all.
- A session identifier may appear in more than one input file; the rows are merged into
  one session and duplicate timestamps are rejected.
- Sessions are processed in identifier order so output is reproducible.
- `participants.csv` is the only source of truth for who exists; a session row naming
  anybody else is rejected rather than inventing a participant.

## Known limitations

- The thresholds are fixed rules tuned for simulated data, not medically validated.
  They use the difference from the personal baseline and ignore age and maximum heart rate.
- Each session receives exactly one label. A session with several intervals, or one that
  is mostly high activity with a short cool-down, is described by its dominant pattern only.
- Recovery is measured from the single highest reading. A session with two peaks, or one
  that recovers in the middle and then starts again, is not described fully.
- One generated session in 40,000 is labelled *recovering* when *moderate activity* was
  expected, as noted above.
- The temperature limits (25–42 °C) follow the supplied data description. They describe
  expected skin temperature rather than physically impossible values, so a genuinely cold
  sensor reading during outdoor exercise would be rejected rather than flagged.
- The program reads the whole input into memory, which is fine for these files but would
  need streaming for very large ones.
- Results are not stored between runs; each run reads the CSV files again.
