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
