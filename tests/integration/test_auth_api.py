import pytest
from datetime import datetime, timedelta
from jose import jwt

from backend.routers import auth
from backend.models.job_scan import JobScan


@pytest.fixture(autouse=True)
def isolated_user_store():
    auth._users_db.clear()
    yield
    auth._users_db.clear()


def test_register_login_duplicate_and_wrong_password(client):
    registration = client.post("/api/v1/auth/register", json={
        "email": "person@example.com", "password": "safe-password", "name": "Person",
    })
    duplicate = client.post("/api/v1/auth/register", json={
        "email": "person@example.com", "password": "safe-password",
    })
    login = client.post("/api/v1/auth/login", json={
        "email": "person@example.com", "password": "safe-password",
    })
    wrong_password = client.post("/api/v1/auth/login", json={
        "email": "person@example.com", "password": "incorrect-password",
    })

    registered_body = registration.json()
    login_body = login.json()
    assert registration.status_code == 200
    assert registered_body["token_type"] == "bearer"
    assert registered_body["access_token"]
    assert login.status_code == 200
    assert login_body["user_id"] == registered_body["user_id"]
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == "Email already registered"
    assert wrong_password.status_code == 401
    assert wrong_password.json()["detail"] == "Invalid email or password"


def test_history_requires_valid_token_and_returns_only_the_callers_scans(client, db_session):
    first = client.post("/api/v1/auth/register", json={
        "email": "first@example.com", "password": "safe-password",
    }).json()
    second = client.post("/api/v1/auth/register", json={
        "email": "second@example.com", "password": "safe-password",
    }).json()
    db_session.add_all([
        JobScan(id="first-scan", user_id=first["user_id"], url="https://first.example/jobs",
                job_title="First", company_name="First", description="First", trust_score=80,
                verdict="SAFE", created_at=datetime(2026, 1, 2)),
        JobScan(id="second-scan", user_id=second["user_id"], url="https://second.example/jobs",
                job_title="Second", company_name="Second", description="Second", trust_score=20,
                verdict="FRAUD", created_at=datetime(2026, 1, 3)),
        JobScan(id="legacy-scan", user_id=None, url="https://legacy.example/jobs",
                job_title="Legacy", company_name="Legacy", description="Legacy", trust_score=50,
                verdict="SUSPICIOUS", created_at=datetime(2026, 1, 4)),
    ])
    db_session.commit()

    missing = client.get("/api/v1/history")
    valid = client.get("/api/v1/history", headers={"Authorization": f"Bearer {first['access_token']}"})
    invalid = client.get("/api/v1/history", headers={"Authorization": "Bearer invalid.token.value"})
    expired_token = jwt.encode(
        {"sub": first["user_id"], "email": first["email"], "exp": datetime.utcnow() - timedelta(minutes=1)},
        auth.SECRET_KEY,
        algorithm=auth.ALGORITHM,
    )
    expired = client.get("/api/v1/history", headers={"Authorization": f"Bearer {expired_token}"})

    assert missing.status_code == 401
    assert valid.status_code == 200
    assert [scan["scan_id"] for scan in valid.json()["scans"]] == ["first-scan"]
    assert valid.json()["total"] == 1
    assert invalid.status_code == 401
    assert expired.status_code == 401
