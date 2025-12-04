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
