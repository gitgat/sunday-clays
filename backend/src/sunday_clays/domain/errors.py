"""Domain exceptions; api/errors.py maps each to its ``status_code`` (C2 Errors)."""

from typing import ClassVar


class DomainError(Exception):
    status_code: ClassVar[int] = 400

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class NotFoundError(DomainError):
    status_code: ClassVar[int] = 404


class ConflictError(DomainError):
    status_code: ClassVar[int] = 409
