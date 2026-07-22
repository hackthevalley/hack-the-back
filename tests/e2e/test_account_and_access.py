from datetime import timedelta

import httpx

from .conftest import MAIL_URL, PASSWORD, token


def test_signup_activation_login_refresh_and_me(client, unique_email):
    signup = client.post(
        "/api/account/users",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": unique_email,
            "password": PASSWORD,
        },
    )
    assert signup.status_code == 201
    assert signup.json()["email"] == unique_email
    assert len(httpx.get(f"{MAIL_URL}/messages").json()) == 1

    inactive_login = client.post(
        "/api/account/sessions",
        data={"username": unique_email, "password": PASSWORD},
    )
    assert inactive_login.status_code in (401, 429)

    activation = token(unique_email, ["account_activate"])
    assert client.post(
        "/api/account/activations", json={"token": activation, "password": None}
    ).status_code == 200

    login = client.post(
        "/api/account/sessions",
        data={"username": unique_email, "password": PASSWORD},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = client.get("/api/account/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == unique_email

    refresh = client.post("/api/account/tokens", headers=headers)
    assert refresh.status_code == 200
    assert refresh.json()["access_token"]


def test_authentication_and_role_boundaries(client, active_hacker):
    assert client.get("/api/account/me").status_code == 401
    assert client.get("/api/admin/account/users", headers=active_hacker["headers"]).status_code == 401
    assert client.get("/api/volunteer/food", headers=active_hacker["headers"]).status_code == 401

    expired = token(active_hacker["email"], expires=timedelta(seconds=-1))
    assert client.get(
        "/api/account/me", headers={"Authorization": f"Bearer {expired}"}
    ).status_code == 401


def test_password_reset_changes_login_password(client, active_hacker):
    requested = client.post(
        "/api/account/password-resets", json={"email": active_hacker["email"]}
    )
    assert requested.status_code == 200
    assert len(httpx.get(f"{MAIL_URL}/messages").json()) == 1

    reset_token = token(active_hacker["email"], ["reset_password"])
    new_password = "AnEvenBetterPassword!84"
    reset = client.put(
        "/api/account/password-resets",
        json={"token": reset_token, "password": new_password},
    )
    assert reset.status_code == 200
    login = client.post(
        "/api/account/sessions",
        data={"username": active_hacker["email"], "password": new_password},
    )
    assert login.status_code == 200
