from types import SimpleNamespace

from fastapi import BackgroundTasks

from app.models.forms import StatusEnum
from app.routers.volunteer.forms import mark_walkin
from app.schemas.forms import WalkInRequest
from app.services.email import send_hacker_package_safely, send_rsvp_safely


def test_rejected_applicant_can_walk_in():
    applicant = SimpleNamespace(status=StatusEnum.REJECTED)
    application = SimpleNamespace(
        application_id="application-id", hacker_applicant=applicant
    )
    user = SimpleNamespace(
        email="hacker@example.com",
        first_name="Hack",
        full_name="Hack Er",
        application=application,
    )

    class Result:
        def first(self):
            return user

    class Session:
        def exec(self, _statement):
            return Result()

        def add(self, _applicant):
            pass

        def commit(self):
            pass

        def refresh(self, _applicant):
            pass

    background_tasks = BackgroundTasks()
    response = mark_walkin(
        WalkInRequest(email=user.email), Session(), background_tasks  # type: ignore[arg-type]
    )

    assert applicant.status == StatusEnum.WALK_IN_SUBMITTED
    assert response["old_status"] == "REJECTED"
    assert response["new_status"] == "WALK_IN_SUBMITTED"
    assert response["rsvp_sent"] is True
    assert [task.func for task in background_tasks.tasks[1:]] == [
        send_rsvp_safely,
        send_hacker_package_safely,
    ]
