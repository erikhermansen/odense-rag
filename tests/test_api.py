"""Tests af HTTP-laget. RAG-flowet erstattes, så testen kun dækker API'ets egen logik."""

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.exceptions import ModelConnectionError

from odense_rag import api
from odense_rag.models import AskResponse, Source

FAKE = AskResponse(
    kind="answer",
    answer="Det koster 894 kr.",
    sources=[
        Source(
            chunk_id="priser-og-gyldighed#0",
            title="Hvad koster et pas?",
            section="Er du over 18 år?",
            url="https://www.odense.dk/borger/borgerservice/pas-online-booking/priser-og-gyldighed",
            quote="894 kr.",
        )
    ],
    retrieved=[],
    model="test",
    latency_ms=1,
    input_tokens=10,
    output_tokens=5,
)


# monkeypatch er pytests indbyggede måde at udskifte attributter på under én
# test (som vi.spyOn/vi.mock); ændringen rulles automatisk tilbage bagefter.
@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(api, "answer_question", lambda settings, question: FAKE)
    return TestClient(api.app)


def test_ask_returnerer_svar_med_kilder(client: TestClient) -> None:
    response = client.post("/ask", json={"question": "Hvad koster et pas?"})

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "answer"
    assert body["sources"][0]["url"].startswith("https://www.odense.dk/")


@pytest.mark.parametrize("question", ["", "x" * 501])
def test_ask_afviser_ugyldige_spoergsmaal(client: TestClient, question: str) -> None:
    response = client.post("/ask", json={"question": question})

    assert response.status_code == 422  # valideret af Pydantic, før vores kode kører


def test_ask_giver_503_naar_sprogmodellen_er_utilgaengelig(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(settings: object, question: str) -> AskResponse:
        raise ModelConnectionError("test-model", "Connection error.")

    monkeypatch.setattr(api, "answer_question", fail)

    response = TestClient(api.app).post("/ask", json={"question": "Hvad koster et pas?"})

    assert response.status_code == 503
