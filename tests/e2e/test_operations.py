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
