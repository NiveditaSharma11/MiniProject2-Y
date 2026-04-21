import json
from app import app, users
from werkzeug.security import check_password_hash


def get_token(client, username="admin", password="admin123"):
    res = client.post("/login", json={"username": username, "password": password})
    return res.get_json().get("token")


def test_app_runs():
    app.config["TESTING"] = True
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200


def test_login_success():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.post("/login", json={"username": "admin", "password": "admin123"})
    data = res.get_json()
    assert res.status_code == 200
    assert "token" in data


def test_login_invalid_credentials():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.post("/login", json={"username": "admin", "password": "wrongpass"})
    data = res.get_json()
    assert res.status_code == 401
    assert "error" in data


def test_login_missing_credentials():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.post("/login", json={"username": "admin"})
    data = res.get_json()
    assert res.status_code == 400
    assert "error" in data


def test_load_classification_requires_auth():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.get("/api/load-classification")
    assert res.status_code == 401


def test_load_classification_with_auth():
    app.config["TESTING"] = True
    client = app.test_client()
    token = get_token(client)
    res = client.get("/api/load-classification", headers={"Authorization": f"Bearer {token}"})
    data = res.get_json()
    assert res.status_code == 200
    assert "load_label" in data
    assert "risk_level" in data
    assert "current_demand" in data
    assert data["load_label"] in ["High Load", "Moderate Load", "Normal Load"]


def test_sensor_input():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.post("/api/sensor-input", json={"demand": 150.5})
    data = res.get_json()
    assert res.status_code == 200
    assert "latest_demand" in data


def test_sensor_input_invalid():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.post("/api/sensor-input", json={"demand": "bad"})
    assert res.status_code == 400
