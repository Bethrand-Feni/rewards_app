from __future__ import annotations


class AppError(Exception):
    status_code = 500
    default_detail = "Unexpected application error"

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class ResourceNotFound(AppError):
    status_code = 404
    default_detail = "Resource not found"


class Conflict(AppError):
    status_code = 409
    default_detail = "The request conflicts with the current resource state"


class PermissionDenied(AppError):
    status_code = 403
    default_detail = "You do not have permission to perform this action"


class AuthenticationFailed(AppError):
    status_code = 401
    default_detail = "Authentication required"


class InvalidRequest(AppError):
    status_code = 422
    default_detail = "The request is invalid"


class UnsupportedMedia(AppError):
    status_code = 415
    default_detail = "Unsupported media type"


class PayloadTooLarge(AppError):
    status_code = 413
    default_detail = "Payload is too large"


class ServiceUnavailable(AppError):
    status_code = 503
    default_detail = "Service temporarily unavailable"
