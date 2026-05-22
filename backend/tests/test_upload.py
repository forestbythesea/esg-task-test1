from fastapi.testclient import TestClient

from app.main import app


def test_upload_rejects_non_pdf_header() -> None:
    client = TestClient(app)
    login = client.post("/api/auth/login", json={"username": "analyst"})
    token = login.json()["token"]
    response = client.post(
        "/api/reports/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"company_name": "Bad PDF", "report_year": "2026"},
        files={"file": ("bad.pdf", b"not a pdf", "application/pdf")},
    )
    assert response.status_code == 400
    assert "valid PDF" in response.json()["detail"]

