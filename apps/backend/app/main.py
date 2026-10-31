from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.students import router as students_router
from app.auth.csrf import CSRFMiddleware
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_for_production()

    app = FastAPI(
        title="Basharnia Coach CRM API",
        version="0.1.0",
        # No public interactive docs in production
        docs_url=None if settings.is_production else "/api/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/api/openapi.json",
    )

    # Added first => runs after CORS, so preflight OPTIONS are handled by CORS
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],  # only the panel domain
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-Requested-With"],
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(dashboard_router, prefix="/api")
    app.include_router(students_router, prefix="/api")
    return app


app = create_app()
