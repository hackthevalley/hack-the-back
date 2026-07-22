import time
from datetime import timedelta

import httpx

from .conftest import MAIL_URL, PASSWORD, db_query, token


def _wait_for_mail_count(expected: int):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        messages = httpx.get(f"{MAIL_URL}/messages").json()
        if len(messages) == expected:
            return
        time.sleep(0.05)
    raise AssertionError(f"Expected {expected} email messages")


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
    assert signup.status_code == 202
    assert len(httpx.get(f"{MAIL_URL}/messages").json()) == 1

    inactive_login = client.post(
        "/api/account/sessions",
        data={"username": unique_email, "password": PASSWORD},
    )
    assert inactive_login.status_code in (401, 429)

    activation = token(unique_email, ["account_activate"])
    assert (
        client.post(
            "/api/account/activations", json={"token": activation, "password": None}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/account/activations", json={"token": activation, "password": None}
        ).status_code
        == 401
    )

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
    assert (
        client.get(
            "/api/admin/account/users", headers=active_hacker["headers"]
        ).status_code
        == 401
    )
    assert (
        client.get("/api/volunteer/food", headers=active_hacker["headers"]).status_code
        == 401
    )

    expired = token(active_hacker["email"], expires=timedelta(seconds=-1))
    assert (
        client.get(
            "/api/account/me", headers={"Authorization": f"Bearer {expired}"}
        ).status_code
        == 401
    )


def test_live_role_and_account_state_revoke_existing_tokens(client, admin_identity):
    admin_headers = admin_identity["headers"]
    assert (
        client.get("/api/admin/account/users", headers=admin_headers).status_code == 200
    )

    db_query(
        "UPDATE account_user SET role = 'HACKER' "
        f"WHERE email = '{admin_identity['email']}'"
    )
    assert (
        client.get("/api/admin/account/users", headers=admin_headers).status_code == 401
    )

    db_query(
        "UPDATE account_user SET is_active = false "
        f"WHERE email = '{admin_identity['email']}'"
    )
    assert client.get("/api/account/me", headers=admin_headers).status_code == 401


def test_repeated_login_failures_lock_the_account(client, active_hacker):
    for _ in range(5):
        response = client.post(
            "/api/account/sessions",
            data={
                "username": active_hacker["email"],
                "password": "WrongPassword1",
            },
        )
        assert response.status_code == 401

    locked_login = client.post(
        "/api/account/sessions",
        data={"username": active_hacker["email"], "password": PASSWORD},
    )
    assert locked_login.status_code == 401


def test_password_reset_changes_login_password(client, active_hacker):
    requested = client.post(
        "/api/account/password-resets", json={"email": active_hacker["email"]}
    )
    assert requested.status_code == 200
    _wait_for_mail_count(1)

    reset_token = token(
        active_hacker["email"],
        ["reset_password"],
        token_version=active_hacker["token_version"],
    )
    new_password = "AnEvenBetterPassword!84"
    reset = client.put(
        "/api/account/password-resets",
        json={"token": reset_token, "password": new_password},
    )
    assert reset.status_code == 200
    assert (
        client.get("/api/account/me", headers=active_hacker["headers"]).status_code
        == 401
    )
    assert (
        client.put(
            "/api/account/password-resets",
            json={"token": reset_token, "password": "YetAnotherPassword1"},
        ).status_code
        == 401
    )
    login = client.post(
        "/api/account/sessions",
        data={"username": active_hacker["email"], "password": new_password},
    )
    assert login.status_code == 200


def test_account_validation_and_failure_paths(client, active_hacker):
    duplicate = client.post(
        "/api/account/users",
        json={
            "first_name": "Duplicate",
            "last_name": "User",
            "email": active_hacker["email"],
            "password": PASSWORD,
        },
    )
    assert duplicate.status_code == 202

    weak_password = client.post(
        "/api/account/users",
        json={
            "first_name": "Weak",
            "last_name": "Password",
            "email": "weak-password@example.com",
            "password": "lowercase",
        },
    )
    assert weak_password.status_code == 422

    wrong_password = client.post(
        "/api/account/sessions",
        data={"username": active_hacker["email"], "password": "WrongPassword1"},
    )
    assert wrong_password.status_code == 401
    missing_login = client.post(
        "/api/account/sessions",
        data={"username": "missing@example.com", "password": PASSWORD},
    )
    existing_login = client.post(
        "/api/account/sessions",
        data={"username": active_hacker["email"], "password": "WrongPassword1"},
    )
    assert missing_login.status_code == existing_login.status_code == 401
    assert missing_login.json() == existing_login.json()

    missing_reset = client.post(
        "/api/account/password-resets", json={"email": "missing@example.com"}
    )
    existing_reset = client.post(
        "/api/account/password-resets", json={"email": active_hacker["email"]}
    )
    assert missing_reset.status_code == existing_reset.status_code == 200
    assert missing_reset.json() == existing_reset.json()

    wrong_scope = token(active_hacker["email"], ["account_activate"])
    assert (
        client.put(
            "/api/account/password-resets",
            json={"token": wrong_scope, "password": "AnotherPassword1"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/account/tokens",
            headers={"Authorization": f"Bearer {wrong_scope}"},
        ).status_code
        == 401
    )

    assert (
        client.get(
            "/api/account/apple-wallet/00000000-0000-0000-0000-000000000000"
        ).status_code
        == 404
    )
