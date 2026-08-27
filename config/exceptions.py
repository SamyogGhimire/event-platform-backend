"""
Standardized API error responses:

    {"detail": "Error message here.", "code": "error_code_string"}
"""
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler


class APIError(APIException):
    """Raise with an explicit machine-readable `code`."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Bad request."
    default_code = "bad_request"

    def __init__(self, detail=None, code=None, status_code=None):
        if status_code is not None:
            self.status_code = status_code
        if detail is None:
            detail = self.default_detail
        if code is None:
            code = self.default_code
        self.detail_code = code
        super().__init__(detail=detail, code=code)


def _first_validation_message(detail):
    """Flatten DRF ValidationError detail into a single string + code."""
    if isinstance(detail, list):
        if not detail:
            return "Validation error.", "validation_error"
        first = detail[0]
        if isinstance(first, dict):
            return _first_validation_message(first)
        return str(first), getattr(first, "code", "validation_error") or "validation_error"

    if isinstance(detail, dict):
        for key, value in detail.items():
            msg, code = _first_validation_message(value)
            if key != "non_field_errors":
                return f"{key}: {msg}", code if code != "invalid" else f"invalid_{key}"
            return msg, code
        return "Validation error.", "validation_error"

    return str(detail), getattr(detail, "code", "validation_error") or "validation_error"


def standard_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return None

    if isinstance(exc, APIError):
        response.data = {"detail": str(exc.detail), "code": exc.detail_code}
        return response

    if isinstance(exc, ValidationError):
        detail, code = _first_validation_message(exc.detail)
        response.data = {"detail": detail, "code": code}
        return response

    # Auth / permission / not-found style exceptions.
    # Prefer ErrorDetail.code (e.g. facilitator_required from BasePermission.code)
    # over APIException.default_code (e.g. permission_denied).
    detail = response.data.get("detail", str(exc)) if isinstance(response.data, dict) else str(exc)
    detail_code = getattr(getattr(exc, "detail", None), "code", None)
    code = detail_code or getattr(exc, "default_code", None) or "error"
    response.data = {"detail": str(detail), "code": str(code)}
    return response
