import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://produksi-tracker-9.preview.emergentagent.com").rstrip("/")
CREDS = {"email": "admin@produksi.local", "password": "Produksi#2026!"}


def test_valid_auth_cookie_me_and_logout():
    session = requests.Session()
    response = session.post(f"{BASE_URL}/api/auth/login", json=CREDS)
    assert response.status_code == 200
    assert response.cookies.get("access_token")
    assert "HttpOnly" in response.headers.get("set-cookie", "")
    assert session.get(f"{BASE_URL}/api/auth/me").status_code == 200
    assert session.post(f"{BASE_URL}/api/auth/logout").status_code == 200
    assert session.get(f"{BASE_URL}/api/auth/me").status_code == 401


def test_invalid_login_locks_nonexistent_identifier_after_five_failures():
    email = "lockout-regression-nobody@invalid.local"
    for _ in range(4):
        assert requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "wrong"}).status_code == 401
    fifth = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "wrong"})
    assert fifth.status_code == 401
    sixth = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "wrong"})
    assert sixth.status_code == 429


def test_authenticated_dashboard_and_modules():
    session = requests.Session()
    assert session.post(f"{BASE_URL}/api/auth/login", json=CREDS).status_code == 200
    dashboard = session.get(f"{BASE_URL}/api/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["total_qty"] >= 0
    for module in ("faris", "eko", "irawan"):
        response = session.get(f"{BASE_URL}/api/records/{module}")
        assert response.status_code == 200
        assert isinstance(response.json(), list)