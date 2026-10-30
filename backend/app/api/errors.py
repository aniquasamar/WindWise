"""One error shape for every failure: {"error": {"code", "message", "request_id"}}.

Nothing internal is ever returned: no tracebacks, no file paths, no raw user input.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.validation import ApiError

log = logging.getLogger("app")

_STATUS_TEXT = {
    404: ("not_found", "The requested resource was not found."),
    405: ("method_not_allowed", "This method is not allowed for this resource."),
}


def error_body(request: Request, code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message, "request_id": getattr(request.state, "request_id", None)}}


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=error_body(request, exc.code, exc.message))


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    first = errors[0] if errors else {}
    where = ".".join(str(p) for p in first.get("loc", ()) if p not in ("query", "path", "body"))
    what = first.get("msg", "invalid request")
    message = f"{where}: {what}" if where else str(what)
    return JSONResponse(status_code=422, content=error_body(request, "validation_error", message))


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code, message = _STATUS_TEXT.get(exc.status_code, ("http_error", "The request could not be processed."))
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(request, code, message),
        headers=getattr(exc, "headers", None),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error")  # the traceback goes to the server log only
    return JSONResponse(status_code=500, content=error_body(request, "internal_error", "An unexpected error occurred."))


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)