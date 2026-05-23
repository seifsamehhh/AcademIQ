"""
test_compute_features.py — Unit tests for compute_features().

These tests are FULLY UNIT-LEVEL — no database, no network, no models.
They test the pure computation logic that transforms raw Moodle data into
ML features.

Run with: cd backend && pytest tests/test_compute_features.py -v
"""

import pytest
import sys
from pathlib import Path

# Ensure backend/app is importable
_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

# Import ONLY from ingest_logic — no DB dependency, safe for unit tests
from backend.app.ingest_logic import compute_features, RawMoodlePayload

# Re-use builders from conftest
from backend.tests.conftest import (
    make_session, make_assignment, make_quiz, make_course, make_payload,
)


# ---------------------------------------------------------------------------
# Helper: build a RawMoodlePayload object from dict
# ---------------------------------------------------------------------------

def build(payload_dict: dict) -> RawMoodlePayload:
    return RawMoodlePayload(**payload_dict)


# ===========================================================================
# 1. Basic happy-path
# ===========================================================================

class TestComputeFeaturesHappyPath:

    def test_returns_all_expected_keys(self):
        payload = build(make_payload())
        features = compute_features(payload)
        expected_keys = {
            "total_time_spent", "active_days", "access_frequency",
            "avg_quiz_score", "quiz_score_std", "avg_assignment_score",
            "late_submission_ratio", "avg_final_grade",
        }
        assert set(features.keys()) == expected_keys

    def test_total_time_spent_sums_session_durations(self):
        sessions = [
            make_session(duration_ms=3_600_000),   # 1 hour
            make_session(start_ts=1_700_010_000_000, duration_ms=1_800_000),  # 30 min
        ]
        features = compute_features(build(make_payload(sessions=sessions)))
        assert features["total_time_spent"] == 5_400_000

    def test_active_days_counts_unique_calendar_days(self):
        # Two sessions on the same day = 1 active day
        same_day_ts = 1_700_000_000_000   # 2023-11-14
        sessions = [
            make_session(start_ts=same_day_ts, duration_ms=3_600_000),
            make_session(start_ts=same_day_ts + 1_000_000, duration_ms=600_000),
        ]
        features = compute_features(build(make_payload(sessions=sessions)))
        assert features["active_days"] == 1

    def test_active_days_two_different_days(self):
        day1 = 1_700_000_000_000
        day2 = day1 + 86_400_000 * 2    # 2 days later
        sessions = [
            make_session(start_ts=day1, duration_ms=3_600_000),
            make_session(start_ts=day2, duration_ms=3_600_000),
        ]
        features = compute_features(build(make_payload(sessions=sessions)))
        assert features["active_days"] == 2

    def test_avg_quiz_score_correct(self):
        quizzes = [make_quiz(score=80.0), make_quiz(score=100.0)]
        course = make_course(quizzes=quizzes)
        features = compute_features(build(make_payload(courses={"C1": course})))
        assert features["avg_quiz_score"] == pytest.approx(90.0)

    def test_quiz_score_std_with_multiple_scores(self):
        # std of [80, 100] ≈ 10 (population std), statistics.stdev ≈ 14.14
        quizzes = [make_quiz(score=80.0), make_quiz(score=100.0)]
        course = make_course(quizzes=quizzes)
        features = compute_features(build(make_payload(courses={"C1": course})))
        # statistics.stdev (sample std) of [80, 100] = 14.142...
        assert features["quiz_score_std"] == pytest.approx(14.142, rel=0.01)

    def test_assignment_score_parsed_from_fraction(self):
        # grade "18/20" → 0.9
        assignment = make_assignment(grade="18/20")
        course = make_course(assignments=[assignment])
        features = compute_features(build(make_payload(courses={"C1": course})))
        assert features["avg_assignment_score"] == pytest.approx(0.9)

    def test_final_grade_parsed_from_percentage(self):
        course = make_course(final_grade="85%")
        features = compute_features(build(make_payload(courses={"C1": course})))
        assert features["avg_final_grade"] == pytest.approx(0.85)

    def test_access_frequency_is_mean_of_visit_counts(self):
        c1 = make_course(course_id="C1", visits=10)
        c2 = make_course(course_id="C2", visits=20)
        features = compute_features(build(make_payload(courses={"C1": c1, "C2": c2})))
        assert features["access_frequency"] == pytest.approx(15.0)


# ===========================================================================
# 2. Edge cases — empty collections
# ===========================================================================

class TestComputeFeaturesEmptyData:

    def test_no_sessions_gives_zero_total_time(self):
        features = compute_features(build(make_payload(sessions=[])))
        assert features["total_time_spent"] == 0

    def test_no_sessions_gives_zero_active_days(self):
        features = compute_features(build(make_payload(sessions=[])))
        assert features["active_days"] == 0

    def test_no_courses_gives_zero_access_frequency(self):
        features = compute_features(build(make_payload(courses={})))
        assert features["access_frequency"] == 0

    def test_no_quizzes_gives_zero_avg_score(self):
        course = make_course(quizzes=[])
        features = compute_features(build(make_payload(courses={"C1": course})))
        assert features["avg_quiz_score"] == 0.0

    def test_no_quizzes_gives_zero_std(self):
        course = make_course(quizzes=[])
        features = compute_features(build(make_payload(courses={"C1": course})))
        assert features["quiz_score_std"] == 0.0

    def test_no_assignments_gives_zero_avg_score(self):
        course = make_course(assignments=[])
        features = compute_features(build(make_payload(courses={"C1": course})))
        assert features["avg_assignment_score"] == 0.0

    def test_no_assignments_gives_zero_late_ratio(self):
        course = make_course(assignments=[])
        features = compute_features(build(make_payload(courses={"C1": course})))
        assert features["late_submission_ratio"] == 0.0

    def test_no_final_grade_gives_zero_avg(self):
        course = make_course(final_grade=None)
        features = compute_features(build(make_payload(courses={"C1": course})))
        assert features["avg_final_grade"] == 0.0


# ===========================================================================
# 3. Single quiz (std must not raise — single-element list)
# ===========================================================================

class TestComputeFeaturesSingleQuiz:

    def test_single_quiz_std_is_zero(self):
        # statistics.stdev raises with <2 values — code handles via len(quiz_scores) > 1 guard
        quiz = make_quiz(score=75.0)
        course = make_course(quizzes=[quiz])
        features = compute_features(build(make_payload(courses={"C1": course})))
        assert features["quiz_score_std"] == 0.0

    def test_single_quiz_avg_is_score(self):
        quiz = make_quiz(score=75.0)
        course = make_course(quizzes=[quiz])
        features = compute_features(build(make_payload(courses={"C1": course})))
        assert features["avg_quiz_score"] == pytest.approx(75.0)


# ===========================================================================
# 4. Grade parsing edge cases
# ===========================================================================

class TestGradeParsing:

    def test_grade_with_spaces_handled_gracefully(self):
        # "18 / 20" — the split on "/" works, but float(" 18 ") also works
        assignment = make_assignment(grade="18 / 20")
        course = make_course(assignments=[assignment])
        # Should not raise; grade may be skipped if parsing fails
        features = compute_features(build(make_payload(courses={"C1": course})))
        assert isinstance(features["avg_assignment_score"], float)

    def test_missing_grade_does_not_crash(self):
        assignment = make_assignment(grade=None)
        course = make_course(assignments=[assignment])
        features = compute_features(build(make_payload(courses={"C1": course})))
        assert features["avg_assignment_score"] == 0.0

    def test_invalid_grade_format_skipped(self):
        assignment = make_assignment(grade="A+")  # cannot be split on "/"
        course = make_course(assignments=[assignment])
        features = compute_features(build(make_payload(courses={"C1": course})))
        assert features["avg_assignment_score"] == 0.0


# ===========================================================================
# 5. Late submission logic
# ===========================================================================

class TestLateSubmissions:

    def test_on_time_submission_not_counted_late(self):
        # submitted_at is before due_date → NOT late
        assignment = make_assignment(
            submitted=True,
            due_date="2024-12-01T23:59:00",
            submitted_at="2024-11-30T20:00:00",
        )
        course = make_course(assignments=[assignment])
        features = compute_features(build(make_payload(courses={"C1": course})))
        assert features["late_submission_ratio"] == 0.0

    def test_late_submission_counted(self):
        # submitted_at is after due_date → IS late
        assignment = make_assignment(
            submitted=True,
            due_date="2024-12-01T23:59:00",
            submitted_at="2024-12-03T10:00:00",
        )
        course = make_course(assignments=[assignment])
        features = compute_features(build(make_payload(courses={"C1": course})))
        assert features["late_submission_ratio"] == pytest.approx(1.0)

    def test_missing_submitted_at_not_counted_late(self):
        # Without submitted_at we cannot determine lateness — should be 0
        assignment = make_assignment(
            submitted=True,
            due_date="2024-12-01T23:59:00",
            submitted_at=None,
        )
        # Override the fixture to remove submitted_at
        a_dict = {
            "title": "HW",
            "grade": "18/20",
            "submitted": True,
            "due_date": "2024-12-01T23:59:00",
            "submitted_at": None,
        }
        course_dict = make_course(assignments=[a_dict])
        features = compute_features(build(make_payload(courses={"C1": course_dict})))
        assert features["late_submission_ratio"] == 0.0

    def test_mixed_late_and_on_time(self):
        on_time = make_assignment(
            title="HW1",
            due_date="2024-12-01T23:59:00",
            submitted_at="2024-11-28T10:00:00",
        )
        late = make_assignment(
            title="HW2",
            due_date="2024-12-01T23:59:00",
            submitted_at="2024-12-02T08:00:00",
        )
        course = make_course(assignments=[on_time, late])
        features = compute_features(build(make_payload(courses={"C1": course})))
        assert features["late_submission_ratio"] == pytest.approx(0.5)
