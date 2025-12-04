from enum import Enum


class UserRole(str, Enum):
    """User role types in the system."""

    ADMIN = "admin"
    VOLUNTEER = "volunteer"
    HACKER = "hacker"


class TokenScope(str, Enum):
    """JWT token scope types for authorization."""

    ADMIN = "admin"
    VOLUNTEER = "volunteer"
    RESET_PASSWORD = "reset_password"
    ACCOUNT_ACTIVATE = "account_activate"


class SortOrder(str, Enum):
    """Sort order options for queries."""

    OLDEST = "oldest"
    LATEST = "latest"


class QuestionLabel(str, Enum):
    FIRST_NAME = "First Name"
    LAST_NAME = "Last Name"
    EMAIL = "Email"
    PHONE_NUMBER = "Phone Number"
    SCHOOL_NAME = "School Name"
    CURRENT_LEVEL_OF_STUDY = "Current Level of Study"
    GENDER = "Gender"
    RESUME = "Attach Your Resume"
    DIETARY_RESTRICTIONS = "Dietary Restrictions"
    T_SHIRT_SIZE = "T-Shirt Size"

    @classmethod
    def is_prefilled_field(cls, label: str) -> bool:
        """Check if a question label represents a pre-filled field from user profile."""
        label_lower = label.lower().strip()
        return label_lower in [
            cls.FIRST_NAME.value.lower(),
            cls.LAST_NAME.value.lower(),
            cls.EMAIL.value.lower(),
        ]

    @classmethod
    def contains_resume(cls, label: str) -> bool:
        """Check if a question label is related to resume upload."""
        return "resume" in label.lower()


class EmailTemplate:
    """Email template file paths."""

    ACTIVATION = "templates/activation.html"
    CONFIRMATION = "templates/confirmation.html"
    PASSWORD_RESET = "templates/password_reset.html"
    RSVP = "templates/rsvp.html"
    HACKER_PACKAGE = "templates/hacker_package.html"


class EmailSubject:
    """Email subject lines."""

    ACTIVATION = "Account Activation"
    CONFIRMATION = "Application Submitted"
    PASSWORD_RESET = "Account Password Reset"
    RSVP_TEMPLATE = "RSVP for {event_name}"

    @staticmethod
    def rsvp(event_name: str) -> str:
        """Generate RSVP email subject."""
        return f"RSVP for {event_name}"


class EmailMessage:
    """Email text body messages."""

    CONFIRMATION = "You have successfully submitted your application"
    PASSWORD_RESET_TEXT = "Go to this link to reset your password: {url}"
    ACTIVATION_TEXT = "Go to this link to activate your account: {url}"
    RSVP_TEXT = "RSVP at {url}"

    @staticmethod
    def password_reset_text(url: str) -> str:
        """Generate password reset text."""
        return f"Go to this link to reset your password: {url}"

    @staticmethod
    def activation_text(url: str) -> str:
        """Generate activation text."""
        return f"Go to this link to activate your account: {url}"

    @staticmethod
    def rsvp_text(url: str) -> str:
        """Generate RSVP text."""
        return f"RSVP at {url}"
