import base64

import pytest

from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def test_analyze_json_returns_verdict(client):
    payload = base64.b64encode(b"hello there friend").decode()
    resp = client.post("/api/analyze", json={"text": payload})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["verdict"]["dominant"] == "base64"


def test_empty_input_returns_400(client):
    resp = client.post("/api/analyze", json={"text": ""})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_index_served(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Obfuscate Detector" in resp.data
