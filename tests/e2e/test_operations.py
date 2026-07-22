def test_admin_meal_and_volunteer_food_workflow(
    client, active_hacker, admin_headers, volunteer_headers
):
    meals = client.get("/api/meals", headers=admin_headers)
    assert meals.status_code == 200
    assert len(meals.json()) >= 1
    meal = meals.json()[0]

    updated = client.patch(
        f"/api/meals/{meal['id']}",
        json={"is_active": True},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is True

    food = client.get("/api/volunteer/food", headers=volunteer_headers)
    assert food.status_code == 200
    assert any(item["id"] == meal["id"] for item in food.json()["allFood"])

    application = client.get(
        "/api/forms/application", headers=active_hacker["headers"]
    ).json()["application"]
    tracked = client.post(
        "/api/volunteer/food/tracking",
        json={
            "food": [
                {"application": application["application_id"], "serving": meal["id"]}
            ]
        },
        headers=volunteer_headers,
    )
    assert tracked.status_code == 200, tracked.text
    assert tracked.json()["new_records_created"] == 1

    duplicate = client.post(
        "/api/volunteer/food/tracking",
        json={
            "food": [
                {"application": application["application_id"], "serving": meal["id"]}
            ]
        },
        headers=volunteer_headers,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["new_records_created"] == 0


def test_walk_in_and_qr_check_in(client, active_hacker, volunteer_headers):
    walk_in = client.post(
        "/api/volunteer/forms/walk-ins",
        json={"email": active_hacker["email"]},
        headers=volunteer_headers,
    )
    assert walk_in.status_code == 200, walk_in.text
    assert walk_in.json()["new_status"] == "WALK_IN"

    application = client.get(
        "/api/forms/application", headers=active_hacker["headers"]
    )
    assert application.status_code == 200
    application_id = application.json()["application"]["application_id"]

    scanned = client.post(
        "/api/volunteer/check-ins",
        json={"id": application_id},
        headers=volunteer_headers,
    )
    assert scanned.status_code == 200, scanned.text
    assert scanned.json()["body"]["applicant"]["status"] == "WALK_IN_SUBMITTED"


def test_admin_listing_and_input_validation(client, admin_headers, volunteer_headers):
    users = client.get("/api/admin/account/users", headers=admin_headers)
    assert users.status_code == 200
    assert isinstance(users.json(), list)
    assert client.get("/api/admin/account/users?limit=101", headers=admin_headers).status_code == 422
    assert client.post(
        "/api/volunteer/check-ins", json={"id": "not-a-uuid"}, headers=volunteer_headers
    ).status_code == 400


def test_complete_meal_crud(client, admin_headers):
    created = client.post(
        "/api/meals",
        json={"day": "friday", "meal_type": "snack", "is_active": True},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    meal = created.json()
    assert meal["name"] == "Friday Snack"

    assert client.post(
        "/api/meals",
        json={"day": "friday", "meal_type": "snack", "is_active": True},
        headers=admin_headers,
    ).status_code == 409
    assert client.get(
        f"/api/meals/{meal['id']}", headers=admin_headers
    ).status_code == 200
    filtered = client.get(
        "/api/meals",
        params={"day": "friday", "meal_type": "snack", "is_active": True},
        headers=admin_headers,
    )
    assert [row["id"] for row in filtered.json()] == [meal["id"]]
    assert client.delete(f"/api/meals/{meal['id']}", headers=admin_headers).status_code == 204
    assert client.get(f"/api/meals/{meal['id']}", headers=admin_headers).status_code == 404
    assert client.delete(f"/api/meals/{meal['id']}", headers=admin_headers).status_code == 404


def test_registration_window_and_bulk_email_paths(
    client, active_hacker, admin_headers
):
    endpoint = "/api/admin/forms/registration-timerange"
    assert client.put(
        endpoint,
        json={"start_at": "bad-date", "end_at": "2099-01-01"},
        headers=admin_headers,
    ).status_code == 400
    assert client.put(
        endpoint,
        json={"start_at": "2099-01-01", "end_at": "2020-01-01"},
        headers=admin_headers,
    ).status_code == 400
    changed = client.put(
        endpoint,
        json={"start_at": "2020-01-01", "end_at": "2099-01-01"},
        headers=admin_headers,
    )
    assert changed.status_code == 200, changed.text
    assert client.get("/api/forms/registration-timerange").status_code == 200
    assert client.get("/api/forms/submission-time").json() is True

    missing_template = client.post(
        "/api/admin/account/bulk-emails",
        json={
            "template_path": "templates/does-not-exist.html",
            "status": "REJECTED",
            "subject": "E2E",
            "text_body": "E2E",
            "context": {},
        },
        headers=admin_headers,
    )
    assert missing_template.status_code == 404
    no_recipients = client.post(
        "/api/admin/account/bulk-emails",
        json={
            "template_path": "templates/confirmation.html",
            "status": "REJECTED_INVITE",
            "subject": "E2E",
            "text_body": "E2E",
            "context": {},
        },
        headers=admin_headers,
    )
    assert no_recipients.status_code == 200
    assert no_recipients.json()["status"] == "no_recipients"

    application = client.get(
        "/api/forms/application", headers=active_hacker["headers"]
    )
    assert application.status_code == 200
    queued = client.post(
        "/api/admin/account/bulk-emails",
        json={
            "template_path": "templates/confirmation.html",
            "status": "APPLYING",
            "subject": "E2E bulk email",
            "text_body": "E2E bulk email",
            "context": {},
        },
        headers=admin_headers,
    )
    assert queued.status_code == 200, queued.text
    assert queued.json()["status"] == "queued"
    assert queued.json()["total_recipients"] >= 1
