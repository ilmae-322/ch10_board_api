"""요청 로깅 및 처리 시간 측정 미들웨어."""

import logging
import time

from fastapi import Request

logger = logging.getLogger("board")


async def log_requests(request: Request, call_next):
    """모든 요청의 처리 시간을 측정해 로그와 응답 헤더(X-Process-Time)에 남긴다."""
    started_at = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started_at) * 1000

    response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}ms"
    logger.info(
        "%s %s -> %s (%.2fms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response
