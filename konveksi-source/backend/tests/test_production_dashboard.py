import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://produksi-tracker-9.preview.emergentagent.com").rstrip("/")
CREDS = {"email": "admin@produksi.local", "password": "Produksi#2026!"}


def test_auth_dashboard_and_crud():
    s = requests.Session()
    bad = s.post(f"{BASE_URL}/api/auth/login", json={"email": CREDS["email"], "password": "wrong"})
    assert bad.status_code == 401
    login = s.post(f"{BASE_URL}/api/auth/login", json=CREDS)
    assert login.status_code == 200
    assert login.json()["role"] == "admin"
    assert login.cookies.get("access_token")
    assert "HttpOnly" in login.headers.get("set-cookie", "")
    assert "SameSite=None" in login.headers.get("set-cookie", "")
    assert s.get(f"{BASE_URL}/api/auth/me").status_code == 200
    dash = s.get(f"{BASE_URL}/api/dashboard")
    assert dash.status_code == 200 and isinstance(dash.json()["models"], list)
    for module in ("faris", "eko", "irawan"):
        response = s.get(f"{BASE_URL}/api/records/{module}")
        assert response.status_code == 200 and isinstance(response.json(), list)
    payload = {"tanggal": "2026-01-01", "model": "TEST_Regression", "qty": 7, "tarif": 1000}
    created = s.post(f"{BASE_URL}/api/records/irawan", json=payload)
    assert created.status_code == 200
    record_id = created.json()["id"]
    fetched = s.get(f"{BASE_URL}/api/records/irawan?search=Regression")
    assert any(row["id"] == record_id for row in fetched.json())
    updated = dict(payload, model="TEST_Updated", status="DONE")
    assert s.put(f"{BASE_URL}/api/records/irawan/{record_id}", json=updated).status_code == 200
    assert s.delete(f"{BASE_URL}/api/records/irawan/{record_id}").status_code == 200
    assert s.post(f"{BASE_URL}/api/auth/logout").status_code == 200
    assert s.get(f"{BASE_URL}/api/dashboard").status_code == 401