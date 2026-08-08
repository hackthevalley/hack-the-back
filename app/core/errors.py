class DomainError(Exception):
    """Base exception for expected domain and application failures."""

    status_code = 400

    def __init__(self, detail: str, *, status_code: int | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code


class ServiceError(DomainError):
    """Backward-compatible expected failure raised by application services."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail, status_code=status_code)
