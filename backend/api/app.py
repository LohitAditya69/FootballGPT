"""FastAPI application factory, routes, and custom error handlers."""

from __future__ import annotations

import logging
import uuid
from typing import Any
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.config import Settings, settings
from backend.api.schemas import (
    AskRequest,
    AskResponse,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
)
from backend.api.service import TacticalService

logger = logging.getLogger(__name__)


def create_app(cfg: Settings = settings, service: TacticalService | None = None) -> FastAPI:
    app = FastAPI(
        title="FootballGPT Product API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url=None,
    )

    tactical_service = service or TacticalService(cfg)

    # CORS configuration for frontend integration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next: Any) -> Response:
        req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = req_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        req_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")
        # Build clean, user-safe message without exposing internal traces or paths
        errors = exc.errors()
        first_msg = "Invalid request payload."
        if errors:
            first_err = errors[0]
            loc = first_err.get("loc", ())
            msg = first_err.get("msg", "")
            if "question" in loc:
                first_msg = "Question must contain 1–2000 characters."
            elif "extra_forbidden" in first_err.get("type", ""):
                first_msg = "Request contains disallowed extra fields."
            elif msg:
                # Use sanitized message
                first_msg = msg.replace("Value error, ", "").strip()

        payload = ErrorResponse(
            schema_version="footballgpt-error-v1",
            request_id=req_id,
            error=ErrorDetail(code="invalid_request", message=first_msg),
        )
        return JSONResponse(status_code=400, content=payload.model_dump())

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        req_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")
        code = "invalid_request" if exc.status_code == 400 else f"http_{exc.status_code}"
        payload = ErrorResponse(
            schema_version="footballgpt-error-v1",
            request_id=req_id,
            error=ErrorDetail(code=code, message=str(exc.detail)),
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        req_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")
        logger.exception("Internal error processing request %s: %s", req_id, exc)
        payload = ErrorResponse(
            schema_version="footballgpt-error-v1",
            request_id=req_id,
            error=ErrorDetail(code="service_error", message="An internal service error occurred."),
        )
        return JSONResponse(status_code=500, content=payload.model_dump())

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "name": "FootballGPT Product API",
            "version": "1.0.0",
            "status": "online",
            "contract": "footballgpt-response-v1",
        }

    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    @app.get("/api/v1/health", response_model=HealthResponse, tags=["Health"])
    async def health_check() -> HealthResponse:
        return HealthResponse(status="ok", version="1.0.0")

    @app.post(
        "/api/v1/ask",
        response_model=AskResponse,
        responses={
            400: {"model": ErrorResponse, "description": "Invalid input"},
            500: {"model": ErrorResponse, "description": "Service error"},
        },
        tags=["Tactical Query"],
    )
    async def ask(request: AskRequest, req: Request) -> AskResponse:
        req_id = getattr(req.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")
        return tactical_service.ask(request, request_id=req_id)

    return app
