from fastapi.testclient import TestClient

from app.main import app


def test_login_and_companies() -> None:
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"username": "analyst"})
    assert response.status_code == 200
    token = response.json()["token"]
    companies = client.get("/api/companies", headers={"Authorization": f"Bearer {token}"})
    assert companies.status_code == 200
    assert len(companies.json()) >= 3

