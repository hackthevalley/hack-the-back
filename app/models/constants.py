from enum import Enum


class UserRole(str, Enum):

    ADMIN = "admin"
    VOLUNTEER = "volunteer"
    HACKER = "hacker"


class TokenScope(str, Enum):

    ADMIN = "admin"
    VOLUNTEER = "volunteer"
    RESET_PASSWORD = "reset_password"
    ACCOUNT_ACTIVATE = "account_activate"


class SortOrder(str, Enum):

    OLDEST = "oldest"
    LATEST = "latest"


class RankingSort(str, Enum):
    HIGHEST = "highest"
    LOWEST = "lowest"


class QuestionLabel(str, Enum):
    FIRST_NAME = "First Name"
    LAST_NAME = "Last Name"
    EMAIL = "Email"
    PHONE_NUMBER = "Phone Number"
    SCHOOL_NAME = "School Name"
    CURRENT_LEVEL_OF_STUDY = "Current Level of Study"
    GENDER = "Gender"
    AVATAR = "Avatar"
    ACCESSORY = "Accessory"
    GITHUB = "Github"
    LINKEDIN = "LinkedIn"
    DEVPOST = "Devpost"
    RESUME = "Attach Your Resume"
    DIETARY_RESTRICTIONS = "Dietary Restrictions"
    T_SHIRT_SIZE = "T-Shirt Size"
    MLH_CODE_OF_CONDUCT = "MLH Code of Conduct"
    MLH_PRIVACY_AND_CONTEST_TERMS = (
        "MLH Privacy Policy, MLH Contest Terms and Conditions"
    )
    HTV_CONSENT = "Hack the Valley Consent Form Agreement"

    @classmethod
    def is_prefilled_field(cls, label: str) -> bool:
        label_lower = label.lower().strip()
        return label_lower in [
            cls.FIRST_NAME.value.lower(),
            cls.LAST_NAME.value.lower(),
            cls.EMAIL.value.lower(),
        ]

    @classmethod
    def contains_resume(cls, label: str) -> bool:
        return "resume" in label.lower()

    @classmethod
    def requires_affirmative_answer(cls, label: str) -> bool:
        return label in {
            cls.MLH_CODE_OF_CONDUCT.value,
            cls.MLH_PRIVACY_AND_CONTEST_TERMS.value,
            cls.HTV_CONSENT.value,
        }


class EmailTemplate:

    ACTIVATION = "templates/activation.html"
    CONFIRMATION = "templates/confirmation.html"
    PASSWORD_RESET = "templates/password_reset.html"
    RSVP = "templates/rsvp.html"
    HACKER_PACKAGE = "templates/hacker_package.html"


class EmailSubject:

    ACTIVATION = "Account Activation"
    CONFIRMATION = "Application Submitted"
    PASSWORD_RESET = "Account Password Reset"
    HACKER_PACKAGE = "Hack the Valley 11 Hacker Package"

    @staticmethod
    def rsvp(event_name: str) -> str:
        return f"RSVP for {event_name}"


class EmailMessage:

    CONFIRMATION = "You have successfully submitted your application"

    @staticmethod
    def hacker_package_text(links: dict[str, str]) -> str:
        return f"""Hack the Valley 11 Hacker Package

Welcome to Hack the Valley 11!

Thank you for confirming your attendance. We’re excited to see you October 16–18, 2026 at the Sam Ibrahim Building, University of Toronto Scarborough.

Hacker Package:
{links["hacker_package_link"]}

Discord:
{links["discord_link"]}

Devpost:
{links["devpost_link"]}

If you are under 18, please have a parent or guardian complete the Minor Hacker Waiver and email it to hello@hackthevalley.io:
https://raw.githubusercontent.com/hackthevalley/internal-resources/main/functions/static/htv11-hacker-liability-waiver.pdf

Women in Tech Summit — Saturday, October 17th, 2–5 PM:
{links["wits_signup_link"]}

WITS Lightning Talk Signup:
{links["wits_lightning_talk_signup_link"]}

Registration begins Friday at 5 PM. Please bring valid ID and your QR code. Hacking begins Friday at 10 PM.

See you soon!
Hack the Valley Team"""

    @staticmethod
    def password_reset_text(url: str) -> str:
        return f"Go to this link to reset your password: {url}"

    @staticmethod
    def activation_text(url: str) -> str:
        return f"Go to this link to activate your account: {url}"

    @staticmethod
    def rsvp_text(url: str) -> str:
        return f"RSVP at {url}"


ALLOWED_FILE_EXTENSIONS = frozenset([".pdf"])
DEFAULT_FILE_EXTENSION = ".pdf"
ALLOWED_FILE_TYPES_MESSAGE = "Only PDF files are allowed"


MIN_PDF_PAGES = 1
PDF_ENCRYPTED_ERROR = "Encrypted or password-protected PDFs are not supported"
PDF_NO_PAGES_ERROR = "PDF contains no pages"
PDF_JAVASCRIPT_ERROR = "PDF contains JavaScript actions, which are not allowed"
PDF_EMBEDDED_FILES_ERROR = "PDF contains embedded files, which are not allowed"

MAX_ERROR_MESSAGE_LENGTH = 120
