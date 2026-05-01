import json
from app import app, users
from werkzeug.security import check_password_hash

# ── Test credentials (not hardcoded inline — defined once here) ───────────────
TEST_ADMIN_USER = "admin"
TEST_ADMIN_PASS = "admin123"
TEST_USER_USER  = "user"
TEST_USER_PASS  = "user123"


def get_token(client, username=TEST_ADMIN_USER, password=TEST_ADMIN_PASS):
    """Helper: log in and return a JWT token."""
    res = client.post("/login", json={"username": username, "password": password})
    return res.get_json().get("token")


# ── App startup ───────────────────────────────────────────────────────────────

def test_app_runs():
    app.config["TESTING"] = True
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200


def test_landing_page():
    app.config["TESTING"] = True
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200


def test_login_page_loads():
    app.config["TESTING"] = True
    client = app.test_client()
    response = client.get("/login_page")
    assert response.status_code == 200


def test_predict_page_loads():
    app.config["TESTING"] = True
    client = app.test_client()
    response = client.get("/predict_page")
    assert response.status_code == 200


def test_dashboard_page_loads():
    app.config["TESTING"] = True
    client = app.test_client()
    response = client.get("/dashboard")
    assert response.status_code == 200


def test_analytics_page_loads():
    app.config["TESTING"] = True
    client = app.test_client()
    response = client.get("/analytics")
    assert response.status_code == 200


def test_renewable_page_loads():
    app.config["TESTING"] = True
    client = app.test_client()
    response = client.get("/renewable")
    assert response.status_code == 200


# ── Authentication ────────────────────────────────────────────────────────────

def test_login_success():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.post("/login", json={"username": TEST_ADMIN_USER, "password": TEST_ADMIN_PASS})
    data = res.get_json()
    assert res.status_code == 200
    assert "token" in data


def test_login_success_regular_user():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.post("/login", json={"username": TEST_USER_USER, "password": TEST_USER_PASS})
    data = res.get_json()
    assert res.status_code == 200
    assert "token" in data


def test_login_invalid_credentials():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.post("/login", json={"username": TEST_ADMIN_USER, "password": "wrongpass"})
    data = res.get_json()
    assert res.status_code == 401
    assert "error" in data


def test_login_missing_credentials():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.post("/login", json={"username": TEST_ADMIN_USER})
    data = res.get_json()
    assert res.status_code == 400
    assert "error" in data


def test_login_empty_body():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.post("/login", json={})
    data = res.get_json()
    assert res.status_code == 400
    assert "error" in data


def test_password_hashing():
    """Passwords in user store must never be plain text."""
    for username, info in users.items():
        assert info["password"] != TEST_ADMIN_PASS
        assert info["password"] != TEST_USER_PASS
        assert info["password"].startswith("pbkdf2:") or info["password"].startswith("scrypt:")


# ── Load Classification ───────────────────────────────────────────────────────

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


def test_load_classification_invalid_token():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.get("/api/load-classification", headers={"Authorization": "Bearer invalidtoken"})
    assert res.status_code == 401


# ── Sensor Input ──────────────────────────────────────────────────────────────

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


def test_sensor_input_missing_field():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.post("/api/sensor-input", json={})
    assert res.status_code == 400


def test_sensor_input_negative_demand():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.post("/api/sensor-input", json={"demand": -50})
    assert res.status_code == 400


# ── Sensor Status ─────────────────────────────────────────────────────────────

def test_sensor_status_requires_auth():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.get("/api/sensor-status")
    assert res.status_code == 401


def test_sensor_status_with_auth():
    app.config["TESTING"] = True
    client = app.test_client()
    token = get_token(client)
    res = client.get("/api/sensor-status", headers={"Authorization": f"Bearer {token}"})
    data = res.get_json()
    assert res.status_code == 200
    assert "latest_demand" in data
    assert "trend" in data
    assert "timestamp" in data


# ── Dashboard Data ────────────────────────────────────────────────────────────

def test_dashboard_data_requires_auth():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.get("/api/dashboard-data")
    assert res.status_code == 401


def test_dashboard_data_with_auth():
    app.config["TESTING"] = True
    client = app.test_client()
    token = get_token(client)
    res = client.get("/api/dashboard-data", headers={"Authorization": f"Bearer {token}"})
    data = res.get_json()
    assert res.status_code == 200
    assert "residential" in data
    assert "industrial" in data
    assert "commercial" in data


# ── Analytics Data ────────────────────────────────────────────────────────────

def test_analytics_data_requires_auth():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.get("/api/analytics-data")
    assert res.status_code == 401


def test_analytics_data_with_auth():
    app.config["TESTING"] = True
    client = app.test_client()
    token = get_token(client)
    res = client.get("/api/analytics-data", headers={"Authorization": f"Bearer {token}"})
    data = res.get_json()
    assert res.status_code == 200
    assert "weekly" in data
    assert "renewable" in data
    assert "non_renewable" in data


# ── Renewable Data ────────────────────────────────────────────────────────────

def test_renewable_data_requires_auth():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.get("/api/renewable-data")
    assert res.status_code == 401


def test_renewable_data_with_auth():
    app.config["TESTING"] = True
    client = app.test_client()
    token = get_token(client)
    res = client.get("/api/renewable-data", headers={"Authorization": f"Bearer {token}"})
    data = res.get_json()
    assert res.status_code == 200
    assert "solar" in data
    assert "wind" in data
    assert "renewable" in data
    assert "percentage" in data


# ── Security Headers ──────────────────────────────────────────────────────────

def test_security_headers_present():
    """Verify security headers are added to every response."""
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.get("/")
    assert "X-Content-Type-Options" in res.headers
    assert "X-Frame-Options" in res.headers
    assert "X-XSS-Protection" in res.headers


# ── Error Handlers ────────────────────────────────────────────────────────────

def test_404_handler():
    app.config["TESTING"] = True
    client = app.test_client()
    res = client.get("/nonexistent-route-xyz")
    assert res.status_code == 404
