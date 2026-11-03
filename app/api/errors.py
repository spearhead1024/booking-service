"""Translate every failure into the same JSON shape: ``{"error", "message", "details"}``.

Unexpected exceptions are logged server-side and reported as a generic 500, so stack traces
never reach the client.
"""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions import (
    AuthenticationError,
    DateOverlapError,
    DomainError,
    InvalidDateRangeError,
    InvalidStateTransitionError,
    NotFoundError,
)
from app.schemas import ErrorResponse

logger = logging.getLogger(__name__)

# (HTTP status, error code) per domain exception. Lookup walks the MRO, so subclasses inherit.
_DOMAIN_ERRORS: dict[type[DomainError], tuple[int, str]] = {
    NotFoundError: (404, "not_found"),
    InvalidDateRangeError: (400, "validation_error"),
    DateOverlapError: (409, "date_overlap"),
    InvalidStateTransitionError: (409, "invalid_state"),
    AuthenticationError: (401, "unauthorized"),
}

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorResponse, "description": HTTPStatus(status).phrase}
    for status in (400, 401, 404, 409)
}


def error_response(status_code: int, error: str, message: str, details: Any = None) -> JSONResponse:
    body = ErrorResponse(error=error, message=message, details=details)
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))


async def _handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
    status_code, code = next(
        (_DOMAIN_ERRORS[cls] for cls in type(exc).__mro__ if cls in _DOMAIN_ERRORS),
        (400, "bad_request"),
    )
    return error_response(status_code, code, exc.message, exc.details)


async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Only expose location/message/type: raw "input" and "ctx" may echo payloads or hold
    # non-serializable exception objects.
    details = [
        {
            "field": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    return error_response(400, "validation_error", "The request is invalid.", details)


async def _handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    phrase = HTTPStatus(exc.status_code).phrase
    response = error_response(
        exc.status_code, phrase.lower().replace(" ", "_").replace("-", "_"), str(exc.detail)
    )
    if exc.headers:
        response.headers.update(exc.headers)
    return response


async def _handle_integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
    # Should be unreachable because services validate first; this is the safety net for
    # database constraints that fire anyway (e.g. a parent deleted concurrently).
    logger.warning("Integrity error: %s", exc)
    return error_response(409, "integrity_error", "The request conflicts with stored data.")


async def _handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    return error_response(500, "internal_error", "An unexpected error occurred.")


def register_exception_handlers(app: FastAPI) -> None:
    # The decorator form accepts handlers typed with their specific exception class.
    app.exception_handler(DomainError)(_handle_domain_error)
    app.exception_handler(RequestValidationError)(_handle_validation_error)
    app.exception_handler(StarletteHTTPException)(_handle_http_exception)
    app.exception_handler(IntegrityError)(_handle_integrity_error)
    app.exception_handler(Exception)(_handle_unexpected_error)
