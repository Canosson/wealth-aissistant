"""FastAPI app factory + middleware (T028)."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from wealth_assistant.api import routes_auth
from wealth_assistant.observability import CorrelationIdMiddleware, configure_logging


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    configure_logging()

    app = FastAPI(
        title="Wealth AIssistant API",
        version="0.1.0",
        description="Portfolio tracking & analytics",
    )

    app.add_middleware(CorrelationIdMiddleware)

    @app.exception_handler(HTTPException)
    async def _http_exc(request: Request, exc: HTTPException) -> JSONResponse:
        # Flatten dict detail to top-level so responses match the OpenAPI Error schema
        detail = exc.detail
        if isinstance(detail, dict):
            content = detail
        else:
            content = {"code": "http_error", "message": str(detail)}
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"code": "internal_error", "message": "An unexpected error occurred."},
        )

    app.include_router(routes_auth.router)

    try:
        from wealth_assistant.api import routes_account
        app.include_router(routes_account.router)
    except ImportError:
        pass

    try:
        from wealth_assistant.api import routes_portfolio
        app.include_router(routes_portfolio.router)
    except ImportError:
        pass

    return app
