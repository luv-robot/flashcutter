from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import settings
from app.main import app


def test_health_check() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app": "flashcutter",
        "environment": "development",
    }


def test_root_redirects_to_docs() -> None:
    with TestClient(app, follow_redirects=False) as client:
        response = client.get("/")

    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def test_trial_auth_can_protect_api_routes() -> None:
    original_require_auth = settings.require_auth
    settings.require_auth = True
    try:
        with TestClient(app) as client:
            response = client.get("/api/assets")
            assert response.status_code == 401

            auth_response = client.post(
                "/api/auth/register",
                json={
                    "phone": f"+1555{uuid4().int % 10_000_0000:08d}",
                    "password": "trial-secret",
                    "display_name": "Trial user",
                },
            )
            assert auth_response.status_code == 200
            token = auth_response.json()["access_token"]

            authed_response = client.get(
                "/api/assets",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert authed_response.status_code == 200

            me_response = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert me_response.status_code == 200
            assert me_response.json()["display_name"] == "Trial user"
    finally:
        settings.require_auth = original_require_auth


def test_registration_can_be_disabled() -> None:
    app_settings = get_settings()
    original_allow_registration = app_settings.allow_registration
    app_settings.allow_registration = False
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/auth/register",
                json={"phone": "+15557654321", "password": "trial-secret"},
            )
            assert response.status_code == 403
    finally:
        app_settings.allow_registration = original_allow_registration


def test_user_can_change_password() -> None:
    phone = f"+1555{uuid4().int % 10_000_0000:08d}"
    with TestClient(app) as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "phone": phone,
                "password": "trial-secret",
                "display_name": "Password user",
            },
        )
        assert register_response.status_code == 200
        token = register_response.json()["access_token"]

        wrong_response = client.patch(
            "/api/auth/password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "wrong-secret",
                "new_password": "next-secret",
            },
        )
        assert wrong_response.status_code == 400

        change_response = client.patch(
            "/api/auth/password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "trial-secret",
                "new_password": "next-secret",
            },
        )
        assert change_response.status_code == 200

        old_login = client.post(
            "/api/auth/login",
            json={"phone": phone, "password": "trial-secret"},
        )
        assert old_login.status_code == 401

        new_login = client.post(
            "/api/auth/login",
            json={"phone": phone, "password": "next-secret"},
        )
        assert new_login.status_code == 200
