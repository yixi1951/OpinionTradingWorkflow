"""Public web API contract tests for the same-origin frontend."""

from fastapi.testclient import TestClient


def test_web_api_requires_session_and_serves_research_data():
    from opinion_trading.services.api_app import app

    client = TestClient(app)
    assert client.get("/v1/workspace/dashboard").status_code == 401

    login = client.post(
        "/v1/auth/login", json={"username": "demo", "password": "demo123"}
    )
    assert login.status_code == 200
    assert login.json()["user"]["username"] == "demo"

    dashboard = client.get("/v1/workspace/dashboard")
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert "picks" in body and "quality" in body and "evaluation" in body

    evidence = client.get("/v1/research/evidence?symbol=600519.SH")
    assert evidence.status_code == 200
    assert evidence.json()["symbol"] == "600519.SH"
