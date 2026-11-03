"""Domain exceptions. They are HTTP-agnostic; ``app.api.errors`` maps them to responses."""

from typing import Any


class DomainError(Exception):
    """Base class for expected, client-facing errors."""

    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(DomainError):
    def __init__(self, resource: str, resource_id: int) -> None:
        super().__init__(f"{resource} {resource_id} not found.")


class InvalidDateRangeError(DomainError):
    """The requested date range is malformed (e.g. start is not before end)."""


class DateOverlapError(DomainError):
    """The requested dates collide with an existing booking or block on the property."""


class InvalidStateTransitionError(DomainError):
    """The requested action is not allowed in the resource's current state."""


class AuthenticationError(DomainError):
    pass
