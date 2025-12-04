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
