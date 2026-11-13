from sqlmodel import Session, col, func, select

from app.models.forms import HackathonApplicant, StatusEnum


def get_check_in_counts(session: Session) -> dict[str, int]:
    scanned_count = session.exec(
        select(func.count(HackathonApplicant.application_id)).where(
            HackathonApplicant.status == StatusEnum.SCANNED_IN
        )
    ).one()
    walkin_count = session.exec(
        select(func.count(HackathonApplicant.application_id)).where(
            col(HackathonApplicant.status).in_(
                [StatusEnum.WALK_IN, StatusEnum.WALK_IN_SUBMITTED]
            )
        )
    ).one()
    return {"scannedCount": scanned_count, "walkinCount": walkin_count}
