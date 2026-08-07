import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import aliased
from sqlmodel import Session, col, literal, select

from app.cache import cache
from app.core.orm import eager_load
from app.models.constants import (
    DEFAULT_FILE_EXTENSION,
    QuestionLabel,
    RankingSort,
    SortOrder,
)
from app.models.forms import (
    Forms_Answer,
    Forms_AnswerFile,
    Forms_Application,
    Forms_HackathonApplicant,
    Forms_Question,
    StatusEnum,
)
from app.models.judging import JudgingApplicationScore
from app.models.user import AccountUser
from app.services.email import send_rsvp

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    filename = Path(filename).name.replace("\x00", "")
    filename = filename.replace("..", "").replace("./", "").replace("../", "")
    filename = re.sub(r"[^\w\s\-.]", "", filename).lstrip(".")
    if len(filename) > 255:
        parts = filename.rsplit(".", 1)
        filename = (
            parts[0][: 254 - len(parts[1])] + "." + parts[1]
            if len(parts) == 2
            else filename[:255]
        )
    return (
        filename
        if filename and not filename.isspace()
        else f"file{DEFAULT_FILE_EXTENSION}"
    )


def get_resume_metadata(session: Session, application_id: UUID) -> tuple[Path, str]:
    resume = session.exec(
        select(Forms_AnswerFile).where(
            Forms_AnswerFile.application_id == application_id
        )
    ).first()
    if not resume or not resume.file_path:
        raise HTTPException(status_code=404, detail="Resume not found")
    path = Path(resume.file_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return path, sanitize_filename(
        resume.original_filename or f"resume{DEFAULT_FILE_EXTENSION}"
    )


def get_application_detail(session: Session, application_id: UUID) -> dict:
    application = session.exec(
        select(Forms_Application).where(
            Forms_Application.application_id == application_id
        )
    ).first()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return {
        "application": application,
        "form_answers": application.form_answers,
        "form_answersfile": application.form_answersfile.original_filename
        if application.form_answersfile
        else None,
    }


def list_applications(
    session: Session,
    *,
    offset: int,
    limit: int,
    search: str,
    level_of_study: str,
    gender: str,
    school: str,
    date_sort: SortOrder | None,
    ranking_sort: RankingSort | None,
    application_status: StatusEnum | None,
) -> dict:
    def fetch_questions() -> dict[str, Forms_Question]:
        questions = session.exec(
            select(Forms_Question).where(
                col(Forms_Question.label).in_(
                    [
                        QuestionLabel.CURRENT_LEVEL_OF_STUDY.value,
                        QuestionLabel.GENDER.value,
                        QuestionLabel.SCHOOL_NAME.value,
                    ]
                )
            )
        ).all()
        return {question.label: question for question in questions}

    question_map = cache.get_or_set(
        "admin_filter_questions", fetch_questions, timedelta(minutes=10)
    )
    level_question = question_map.get(QuestionLabel.CURRENT_LEVEL_OF_STUDY.value)
    gender_question = question_map.get(QuestionLabel.GENDER.value)
    school_question = question_map.get(QuestionLabel.SCHOOL_NAME.value)

    level_answer = aliased(Forms_Answer)
    gender_answer = aliased(Forms_Answer)
    school_answer = aliased(Forms_Answer)
    level_column = col(level_answer.answer) if level_question else literal(None)
    gender_column = col(gender_answer.answer) if gender_question else literal(None)
    school_column = col(school_answer.answer) if school_question else literal(None)
    statement = (
        select(
            AccountUser,
            Forms_Application,
            Forms_HackathonApplicant,
            level_column.label("level_of_study_answer"),
            gender_column.label("gender_answer"),
            school_column.label("school_answer"),
            col(JudgingApplicationScore.mu).label("ranking_mu"),
            col(JudgingApplicationScore.sigma_sq).label("ranking_sigma_sq"),
            col(JudgingApplicationScore.comparison_count).label(
                "ranking_comparison_count"
            ),
        )
        .where(col(AccountUser.is_active).is_(True))
        .join(Forms_Application, AccountUser.uid == Forms_Application.uid)
        .join(
            Forms_HackathonApplicant,
            Forms_Application.application_id == Forms_HackathonApplicant.application_id,
        )
        .outerjoin(
            JudgingApplicationScore,
            JudgingApplicationScore.application_id == Forms_Application.application_id,
        )
    )

    for question, answer_model in (
        (level_question, level_answer),
        (gender_question, gender_answer),
        (school_question, school_answer),
    ):
        if question:
            statement = statement.outerjoin(
                answer_model,
                and_(
                    answer_model.application_id == Forms_Application.application_id,
                    answer_model.question_id == question.question_id,
                ),
            )

    if search:
        pattern = f"%{search}%"
        statement = statement.where(
            or_(
                col(AccountUser.first_name).ilike(pattern),
                col(AccountUser.last_name).ilike(pattern),
                col(AccountUser.email).ilike(pattern),
                (
                    col(AccountUser.first_name) + " " + col(AccountUser.last_name)
                ).ilike(pattern),
            )
        )
    if application_status:
        statement = statement.where(
            Forms_HackathonApplicant.status == application_status
        )
    if level_of_study and level_question:
        statement = statement.where(
            func.lower(level_answer.answer) == level_of_study.lower()
        )
    if gender and gender_question:
        statement = statement.where(func.lower(gender_answer.answer) == gender.lower())
    if school and school_question:
        statement = statement.where(
            col(school_answer.answer).isnot(None),
            school_answer.answer != "",
            func.lower(school_answer.answer) == school.lower(),
        )

    if ranking_sort:
        ranking_column = col(JudgingApplicationScore.mu)
        statement = statement.order_by(
            (
                ranking_column.desc()
                if ranking_sort == RankingSort.HIGHEST
                else ranking_column.asc()
            ).nulls_last(),
            col(Forms_Application.updated_at).desc(),
            col(Forms_Application.application_id).asc(),
        )
    elif date_sort:
        date_column = col(Forms_Application.updated_at)
        statement = statement.order_by(
            date_column.asc() if date_sort == SortOrder.OLDEST else date_column.desc(),
            col(Forms_Application.application_id).asc(),
        )
    else:
        statement = statement.order_by(
            col(Forms_Application.updated_at).desc(),
            col(Forms_Application.application_id).asc(),
        )

    results = session.exec(statement.offset(offset).limit(limit)).all()
    applications = [
        {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "status": applicant.status,
            "app_id": applicant.application_id,
            "created_at": application.created_at,
            "updated_at": application.updated_at,
            "level_of_study": level,
            "gender": gender_value,
            "school": school_value,
            "ranking_mu": ranking_mu,
            "ranking_sigma_sq": ranking_sigma_sq,
            "ranking_comparison_count": comparison_count or 0,
        }
        for (
            user,
            application,
            applicant,
            level,
            gender_value,
            school_value,
            ranking_mu,
            ranking_sigma_sq,
            comparison_count,
        ) in results
    ]
    return {"application": applications, "offset": offset, "limit": limit}


def update_application_status(
    session: Session,
    application_id: str,
    new_status: StatusEnum,
) -> dict:
    result = session.exec(
        select(Forms_Application, AccountUser)
        .join(AccountUser, Forms_Application.uid == AccountUser.uid)
        .where(Forms_Application.application_id == application_id)
        .options(eager_load(Forms_Application.hackathonapplicant))
    ).first()
    if not result:
        raise HTTPException(status_code=404, detail="Application not found")
    application, user = result
    applicant = application.hackathonapplicant
    if applicant is None:
        raise HTTPException(status_code=404, detail="Applicant status not found")

    previous_status = applicant.status
    try:
        applicant.status = new_status.value
        application.updated_at = datetime.now(timezone.utc)
        session.add(applicant)
        session.add(application)
        session.commit()
        session.refresh(applicant)
        session.refresh(application)
    except Exception as error:
        session.rollback()
        logger.exception("Failed to update status for application %s", application_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update application status",
        ) from error

    if new_status == StatusEnum.ACCEPTED and previous_status != StatusEnum.ACCEPTED:
        try:
            send_rsvp(user.email, user.full_name, application_id)
        except Exception:
            logger.exception(
                "Application %s was accepted, but its RSVP could not be sent",
                application_id,
            )

    return {
        "application_id": application_id,
        "new_status": new_status.value,
        "updated_at": application.updated_at,
    }
