"""
API-level tests for the comparison endpoints.

These exist because the service-level tests missed a 500 that broke every
comparison at creation time: they called ComparisonService directly and so
never exercised response serialization, where a freshly-created evaluation
has responses=None and the schema expected a list. Anything that only shows
up through the HTTP layer belongs here.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.main import app
from src.core.database import Base, get_db
from src.services.comparison_service import ComparisonService


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient against a throwaway DB, with the background run stubbed
    out so tests exercise the HTTP contract without calling a provider."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'routes.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    async def noop_run(self, comparison_id):
        return None

    monkeypatch.setattr(ComparisonService, "run", noop_run)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def payload(**overrides):
    body = {
        "name": "test comparison",
        "models": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "anthropic", "model": "claude-haiku-4-5"},
        ],
        "evaluators": ["accuracy", "performance", "cost"],
        "examples": [{"id": "e0", "prompt": "Say hi.", "expected_output": "hi"}],
    }
    body.update(overrides)
    return body


def test_create_returns_202_and_does_not_500(client):
    """
    The regression: creating a comparison serializes evaluations that have
    no responses yet, which raised a ValidationError and 500'd.
    """
    response = client.post("/api/v1/comparisons/", json=payload())
    assert response.status_code == 202, response.text


def test_created_pending_evaluations_serialize_with_empty_responses(client):
    response = client.post("/api/v1/comparisons/", json=payload())
    body = response.json()

    assert len(body["evaluations"]) == 2
    for evaluation in body["evaluations"]:
        assert evaluation["status"] == "pending"
        assert evaluation["responses"] == []   # not None, not missing
        assert evaluation["results"] is None
        assert evaluation["progress"] == 0.0


def test_create_response_carries_prompts_and_empty_winners(client):
    body = client.post("/api/v1/comparisons/", json=payload()).json()
    assert body["status"] == "pending"
    assert [e["prompt"] for e in body["examples"]] == ["Say hi."]
    assert body["winners"] == {}   # nothing to rank until models finish


def test_get_after_create_also_serializes(client):
    """GET has its own serialization path; it must survive pending rows too."""
    created = client.post("/api/v1/comparisons/", json=payload()).json()
    response = client.get(f"/api/v1/comparisons/{created['id']}")

    assert response.status_code == 200, response.text
    assert response.json()["id"] == created["id"]
    assert all(e["responses"] == [] for e in response.json()["evaluations"])


def test_list_includes_the_new_comparison(client):
    client.post("/api/v1/comparisons/", json=payload(name="listed"))
    body = client.get("/api/v1/comparisons/").json()

    assert body["total"] == 1
    assert body["comparisons"][0]["name"] == "listed"


def test_get_unknown_id_is_404(client):
    assert client.get("/api/v1/comparisons/does-not-exist").status_code == 404


def test_delete_removes_comparison_and_children(client):
    created = client.post("/api/v1/comparisons/", json=payload()).json()

    assert client.delete(f"/api/v1/comparisons/{created['id']}").status_code == 204
    assert client.get(f"/api/v1/comparisons/{created['id']}").status_code == 404
    # Children go with it rather than lingering as orphans.
    evaluations = client.get("/api/v1/evaluations/").json()
    assert evaluations["total"] == 0


def test_delete_unknown_id_is_404(client):
    assert client.delete("/api/v1/comparisons/nope").status_code == 404


@pytest.mark.parametrize(
    "bad,reason",
    [
        ({"models": [{"provider": "openai", "model": "gpt-4o-mini"}]}, "one model"),
        (
            {"models": [{"provider": "openai", "model": f"m{i}"} for i in range(6)]},
            "six models",
        ),
        (
            {"models": [{"provider": "openai", "model": "gpt-4o-mini"}] * 2},
            "duplicate models",
        ),
    ],
)
def test_invalid_model_lists_are_rejected(client, bad, reason):
    response = client.post("/api/v1/comparisons/", json=payload(**bad))
    assert response.status_code == 422, f"{reason} should be rejected: {response.text}"
