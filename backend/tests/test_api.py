"""
test_api.py — Integration tests for the FastAPI HTTP endpoints.

Requires MONGODB_URI in environment. Tests that need DB are auto-skipped
when it's absent (see conftest.py client fixture).

Run with: cd backend && pytest tests/test_api.py -v
"""

import pytest
from backend.tests.conftest import make_payload, make_session, make_course, make_assignment, make_quiz

pytestmark = pytest.mark.asyncio


# ===========================================================================
# GET /  — health check
# ===========================================================================

class TestHealthEndpoint:

    async def test_root_returns_200(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200

    async def test_root_message_content(self, client):
        resp = await client.get("/")
        data = resp.json()
        assert "message" in data
        assert "running" in data["message"].lower()

    async def test_root_is_fast(self, client):
        """Non-functional: GET / must respond in under 500ms."""
        import time
        start = time.perf_counter()
        await client.get("/")
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 500, f"Root endpoint took {elapsed_ms:.0f}ms (limit: 500ms)"


# ===========================================================================
# POST /ingest — valid payloads
# ===========================================================================

class TestIngestValidPayload:

    async def test_valid_payload_returns_200(self, client):
        resp = await client.post("/ingest", json=make_payload())
        assert resp.status_code == 200

    async def test_response_has_status_ok(self, client):
        resp = await client.post("/ingest", json=make_payload())
        assert resp.json()["status"] == "ok"

    async def test_response_echoes_student_id(self, client):
        payload = make_payload(student_id="TEST_STUDENT_42")
        resp = await client.post("/ingest", json=payload)
        assert resp.json()["student_id"] == "TEST_STUDENT_42"

    async def test_response_contains_features(self, client):
        resp = await client.post("/ingest", json=make_payload())
        assert "features" in resp.json()

    async def test_features_has_all_keys(self, client):
        resp = await client.post("/ingest", json=make_payload())
        features = resp.json()["features"]
        expected = {
            "total_time_spent", "active_days", "access_frequency",
            "avg_quiz_score", "quiz_score_std", "avg_assignment_score",
            "late_submission_ratio", "avg_final_grade",
        }
        assert expected.issubset(set(features.keys()))

    async def test_features_are_numeric(self, client):
        resp = await client.post("/ingest", json=make_payload())
        features = resp.json()["features"]
        for key, val in features.items():
            assert isinstance(val, (int, float)), f"{key} is {type(val).__name__}, expected numeric"

    async def test_ingest_performance_under_200ms(self, client):
        """Non-functional: POST /ingest must respond in under 200ms."""
        import time
        payload = make_payload()
        start = time.perf_counter()
        await client.post("/ingest", json=payload)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 200, f"Ingest took {elapsed_ms:.0f}ms (limit: 200ms)"


# ===========================================================================
# POST /ingest — empty sessions / courses
# ===========================================================================

class TestIngestEmptyCollections:

    async def test_empty_sessions_accepted(self, client):
        payload = make_payload(sessions=[], courses={})
        resp = await client.post("/ingest", json=payload)
        assert resp.status_code == 200

    async def test_empty_sessions_total_time_is_zero(self, client):
        payload = make_payload(sessions=[], courses={})
        resp = await client.post("/ingest", json=payload)
        assert resp.json()["features"]["total_time_spent"] == 0

    async def test_empty_courses_access_frequency_is_zero(self, client):
        payload = make_payload(courses={})
        resp = await client.post("/ingest", json=payload)
        assert resp.json()["features"]["access_frequency"] == 0


# ===========================================================================
# POST /ingest — invalid payloads
# ===========================================================================

class TestIngestInvalidPayload:

    async def test_missing_required_field_clicks(self, client):
        payload = make_payload()
        del payload["clicks"]
        resp = await client.post("/ingest", json=payload)
        assert resp.status_code == 422  # Pydantic validation error

    async def test_missing_required_field_sessions(self, client):
        payload = make_payload()
        del payload["sessions"]
        resp = await client.post("/ingest", json=payload)
        assert resp.status_code == 422

    async def test_wrong_type_for_clicks(self, client):
        payload = make_payload()
        payload["clicks"] = "not_a_number"
        resp = await client.post("/ingest", json=payload)
        assert resp.status_code == 422

    async def test_empty_body_rejected(self, client):
        resp = await client.post("/ingest", json={})
        assert resp.status_code == 422

    async def test_completely_wrong_body(self, client):
        resp = await client.post("/ingest", json={"foo": "bar"})
        assert resp.status_code == 422


# ===========================================================================
# POST /ingest — multiple sessions same-day deduplication (active_days)
# ===========================================================================

class TestIngestActiveDayDedup:

    async def test_two_sessions_same_day_count_as_one(self, client):
        same_day_ts = 1_700_000_000_000
        sessions = [
            make_session(start_ts=same_day_ts, duration_ms=3_600_000),
            make_session(start_ts=same_day_ts + 3_600_000, duration_ms=1_800_000),
        ]
        payload = make_payload(sessions=sessions)
        resp = await client.post("/ingest", json=payload)
        assert resp.json()["features"]["active_days"] == 1

    async def test_null_student_id_accepted(self, client):
        payload = make_payload(student_id=None)
        payload["student_id"] = None
        resp = await client.post("/ingest", json=payload)
        assert resp.status_code == 200
