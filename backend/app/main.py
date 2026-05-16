from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import httpx
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.exceptions import AppException
from app.core.logging import configure_logging

# 모델 모듈은 Base.metadata에 테이블을 등록하기 위해 import만 해 두면 됨.
from app.domains.users import models as _users_models  # noqa: F401

configure_logging()
logger = structlog.get_logger(__name__)


async def _create_schema_for_development() -> None:
    # create_all은 누락된 테이블만 생성한다. 컬럼 변경은 반영되지 않으므로
    # 정식 스키마 변경은 별도 Alembic 마이그레이션에서 처리한다.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0))
    app.state.http_client = http_client

    if settings.environment == "development":
        await _create_schema_for_development()
        logger.info("dev_schema_create_all_done")

    logger.info("lifespan_startup")
    try:
        yield
    finally:
        await http_client.aclose()
        logger.info("lifespan_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ku-helper backend", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppException)
    async def _app_exception_handler(
        request: Request, exc: AppException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "detail": exc.detail},
        )

    app.include_router(api_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
