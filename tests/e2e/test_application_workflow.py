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
            answers.append(
                {"question_id": question["question_id"], "answer": "E2E answer"}
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
