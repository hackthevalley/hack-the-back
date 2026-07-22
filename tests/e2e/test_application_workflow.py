from io import BytesIO

from pypdf import PdfWriter


def _pdf():
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(output)
    return output.getvalue()


def test_complete_application_submission_and_admin_review(
    client, active_hacker, admin_headers
):
    questions = client.get("/api/forms/questions").json()
    assert questions

    application = client.get(
        "/api/forms/application", headers=active_hacker["headers"]
    )
    assert application.status_code == 200, application.text
    app_id = application.json()["application"]["application_id"]

    answers = []
    for question in questions:
        if "resume" not in question["label"].lower():
            values = {
                "School Name": "University of Toronto",
                "Current Level of Study": "Undergraduate",
                "Gender": "Prefer not to say",
            }
            answers.append(
                {
                    "question_id": question["question_id"],
                    "answer": values.get(question["label"], "E2E answer"),
                }
            )
    saved = client.put(
        "/api/forms/answers", json=answers, headers=active_hacker["headers"]
    )
    assert saved.status_code == 200, saved.text

    uploaded = client.post(
        "/api/forms/resume",
        files={"file": ("resume.pdf", _pdf(), "application/pdf")},
        headers=active_hacker["headers"],
    )
    assert uploaded.status_code == 200, uploaded.text

    submitted = client.post(
        "/api/forms/submission", headers=active_hacker["headers"]
    )
    assert submitted.status_code == 201, submitted.text
    assert client.post(
        "/api/forms/submission", headers=active_hacker["headers"]
    ).status_code in (403, 409)

    listing = client.get(
        "/api/admin/account/applications",
        params={
            "search": active_hacker["email"],
            "role": "APPLIED",
            "date_sort": "latest",
        },
        headers=admin_headers,
    )
    assert listing.status_code == 200, listing.text
    assert any(row["app_id"] == app_id for row in listing.json()["application"])

    filtered = client.get(
        "/api/admin/account/applications",
        params={
            "level_of_study": "undergraduate",
            "gender": "prefer not to say",
            "school": "university of toronto",
            "date_sort": "oldest",
        },
        headers=admin_headers,
    )
    assert filtered.status_code == 200, filtered.text
    assert any(row["app_id"] == app_id for row in filtered.json()["application"])

    applicants = client.get("/api/admin/account/applicants", headers=admin_headers)
    assert applicants.status_code == 200
    assert any(row["email"] == active_hacker["email"] for row in applicants.json())

    detail = client.get(f"/api/admin/account/applications/{app_id}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    resume = client.get(
        f"/api/admin/account/applications/{app_id}/resume", headers=admin_headers
    )
    assert resume.status_code == 200
    assert resume.headers["content-type"].startswith("application/pdf")

    accepted = client.patch(
        f"/api/admin/account/applications/{app_id}/status",
        params={"request": "ACCEPTED"},
        headers=admin_headers,
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["new_status"] == "ACCEPTED"

    rsvp = client.patch(
        "/api/account/rsvp-status",
        params={"status": "ACCEPTED_INVITE"},
        headers=active_hacker["headers"],
    )
    assert rsvp.status_code == 200, rsvp.text


def test_application_and_admin_not_found_paths(client, admin_headers):
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.get(
        f"/api/admin/account/applications/{missing}", headers=admin_headers
    ).status_code == 404
    assert client.get(
        f"/api/admin/account/applications/{missing}/resume", headers=admin_headers
    ).status_code == 404
    assert client.patch(
        f"/api/admin/account/applications/{missing}/status",
        params={"request": "REJECTED"},
        headers=admin_headers,
    ).status_code == 404

    invalid_answer = client.put(
        "/api/forms/answers",
        json=[
            {
                "question_id": "00000000-0000-0000-0000-000000000000",
                "answer": "invalid",
            }
        ],
        headers=admin_headers,
    )
    # Admin JWT belongs to a real user but the endpoint still requires an application.
    assert invalid_answer.status_code in (400, 500)


def test_rejects_invalid_resume(client, active_hacker):
    client.get("/api/forms/application", headers=active_hacker["headers"])
    response = client.post(
        "/api/forms/resume",
        files={"file": ("resume.pdf", b"not a pdf", "application/pdf")},
        headers=active_hacker["headers"],
    )
    assert response.status_code == 400


def test_form_validation_upload_limits_and_prefilled_fields(client, active_hacker):
    questions_response = client.get("/api/forms/questions")
    assert questions_response.status_code == 200
    questions = questions_response.json()
    # Exercise the cached response path too.
    assert client.get("/api/forms/questions").json() == questions

    application = client.get(
        "/api/forms/application", headers=active_hacker["headers"]
    )
    assert application.status_code == 200

    incomplete = client.post(
        "/api/forms/submission", headers=active_hacker["headers"]
    )
    assert incomplete.status_code == 400

    first_name = next(q for q in questions if q["label"] == "First Name")
    preserved = client.put(
        "/api/forms/answers",
        json=[{"question_id": first_name["question_id"], "answer": ""}],
        headers=active_hacker["headers"],
    )
    assert preserved.status_code == 200
    assert preserved.json()["updated_count"] == 0

    invalid_question = client.put(
        "/api/forms/answers",
        json=[
            {
                "question_id": "00000000-0000-0000-0000-000000000000",
                "answer": "invalid",
            }
        ],
        headers=active_hacker["headers"],
    )
    assert invalid_question.status_code == 400

    wrong_type = client.post(
        "/api/forms/resume",
        files={"file": ("resume.txt", b"plain text", "text/plain")},
        headers=active_hacker["headers"],
    )
    assert wrong_type.status_code == 400
    too_large = client.post(
        "/api/forms/resume",
        files={"file": ("resume.pdf", b"x" * (6 * 1024 * 1024), "application/pdf")},
        headers=active_hacker["headers"],
    )
    assert too_large.status_code == 413


def test_closed_registration_blocks_form_access(client, active_hacker, admin_headers):
    endpoint = "/api/admin/forms/registration-timerange"
    try:
        closed = client.put(
            endpoint,
            json={"start_at": "2098-01-01", "end_at": "2099-01-01"},
            headers=admin_headers,
        )
        assert closed.status_code == 200
        assert client.get(
            "/api/forms/application", headers=active_hacker["headers"]
        ).status_code == 404
        assert client.put(
            "/api/forms/answers", json=[], headers=active_hacker["headers"]
        ).status_code == 403
        assert client.post(
            "/api/forms/resume",
            files={"file": ("resume.pdf", _pdf(), "application/pdf")},
            headers=active_hacker["headers"],
        ).status_code == 403
        assert client.post(
            "/api/forms/submission", headers=active_hacker["headers"]
        ).status_code == 403
    finally:
        restored = client.put(
            endpoint,
            json={"start_at": "2020-01-01", "end_at": "2099-01-01"},
            headers=admin_headers,
        )
        assert restored.status_code == 200
