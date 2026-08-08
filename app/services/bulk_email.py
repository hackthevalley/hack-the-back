import logging
from concurrent.futures import ThreadPoolExecutor

from sqlmodel import Session, func, select

from app.config import EmailConfig
from app.models.forms import FormApplication, HackathonApplicant
from app.models.requests import BulkEmailRequest
from app.models.user import AccountUser
from app.services.email import send_email

logger = logging.getLogger(__name__)


def send_batch_email(
    users_data: list[dict],
    template_path: str,
    subject: str,
    text_body: str,
    base_context: dict,
) -> None:
    total = len(users_data)
    successful = 0
    failures: list[dict] = []

    logger.info(
        "Starting bulk email send: %s recipients, subject='%s', template='%s', "
        "concurrency=%s, chunk_size=%s",
        total,
        subject,
        template_path,
        EmailConfig.BULK_MAX_CONCURRENT,
        EmailConfig.BULK_CHUNK_SIZE,
    )

    def send_one(user_data: dict) -> tuple[bool, str, dict]:
        email = user_data.get("email", "unknown")
        try:
            email_context = base_context.copy() if base_context else {}
            email_context.update(user_data)
            status_code, response = send_email(
                template_path, email, subject, text_body, email_context
            )
            if status_code == 200:
                return True, email, {}
            return False, email, {
                "email": email,
                "reason": f"Status {status_code}",
                "response": response,
            }
        except Exception as error:
            return False, email, {"email": email, "reason": str(error)}

    for index in range(0, total, EmailConfig.BULK_CHUNK_SIZE):
        chunk = users_data[index : index + EmailConfig.BULK_CHUNK_SIZE]
        with ThreadPoolExecutor(
            max_workers=EmailConfig.BULK_MAX_CONCURRENT
        ) as executor:
            results = list(executor.map(send_one, chunk))
        for success, email, error_info in results:
            if success:
                successful += 1
                logger.debug("Email sent successfully to %s", email)
            else:
                failures.append(error_info)
                logger.warning("Email send failed to %s: %s", email, error_info)

    logger.info(
        "Bulk email send complete: %s/%s successful, %s/%s failed",
        successful,
        total,
        len(failures),
        total,
    )


def get_bulk_email_recipients(
    session: Session, request: BulkEmailRequest
) -> tuple[int, list[dict]]:
    base_query = (
        select(AccountUser)
        .join(FormApplication, AccountUser.uid == FormApplication.uid)
        .join(
            HackathonApplicant,
            FormApplication.application_id
            == HackathonApplicant.application_id,
        )
        .where(
            AccountUser.is_active,
            HackathonApplicant.status == request.status,
        )
    )
    total = session.exec(
        select(func.count()).select_from(base_query.subquery())
    ).one()
    if total == 0:
        return 0, []

    rows = session.exec(
        select(
            AccountUser.first_name,
            AccountUser.last_name,
            AccountUser.email,
        )
        .join(FormApplication, AccountUser.uid == FormApplication.uid)
        .join(
            HackathonApplicant,
            FormApplication.application_id
            == HackathonApplicant.application_id,
        )
        .where(
            AccountUser.is_active,
            HackathonApplicant.status == request.status,
        )
    ).all()
    return total, [
        {"first_name": row[0], "last_name": row[1], "email": row[2]}
        for row in rows
    ]
