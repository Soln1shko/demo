"""Ошибки в формате RFC 7807 (application/problem+json)."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM = "application/problem+json"


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        detail: str,
        *,
        title: str | None = None,
        errors: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status, self.code, self.detail = status, code, detail
        self.title = title or detail
        self.errors = errors or []


def not_found(what: str = "Объект") -> ApiError:
    return ApiError(404, "not_found", f"{what} не найден")


def forbidden(detail: str = "Недостаточно прав") -> ApiError:
    return ApiError(403, "forbidden", detail)


def conflict(code: str, detail: str) -> ApiError:
    return ApiError(409, code, detail)


def validation(detail: str, field: str | None = None) -> ApiError:
    errors = [{"field": field or "", "message": detail}]
    return ApiError(422, "validation_failed", detail, errors=errors)


def _problem(status: int, code: str, title: str, detail: str, errors: list[dict[str, str]] | None = None):
    body: dict[str, Any] = {
        "type": f"https://alfa-credit.local/problems/{code}",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type=PROBLEM)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return _problem(exc.status, exc.code, exc.title, exc.detail, exc.errors)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        errors = [
            {
                "field": ".".join(str(p) for p in e["loc"] if p not in ("body", "query", "path")),
                "message": e["msg"],
            }
            for e in exc.errors()
        ]
        return _problem(422, "validation_failed", "Ошибка валидации", "Проверьте переданные данные", errors)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return _problem(exc.status_code, f"http_{exc.status_code}", str(exc.detail), str(exc.detail))
