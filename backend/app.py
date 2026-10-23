"""Local team calendar service. Run one worker for the in-process scheduler."""

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import date, datetime, timedelta
import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .parsers import KST, midnight
from .store import Store


def make_store() -> Store:
    return Store(Path(os.getenv("DATA_DIR", "/data")), Path(os.getenv("LEAVE_DIR", "/imports/eCount")), "")


async def scheduled_sync(store: Store):
    while True:
        current = datetime.now(KST)
        next_midnight = midnight(current.date() + timedelta(days=1))
        target = next_midnight
        await asyncio.sleep((target - current).total_seconds())
        try:
            await asyncio.to_thread(store.sync)
        except Exception:
            # Keep the scheduler alive; API health exposes state persistence failures.
            with store.lock:
                store.state["sources"]["leave"].update(status="error", error="자동 갱신 중 저장 오류가 발생했습니다. 저장 공간을 확인하세요.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = make_store()
    app.state.store = store
    await asyncio.to_thread(store.sync)
    job = asyncio.create_task(scheduled_sync(store))
    yield
    job.cancel()
    with suppress(asyncio.CancelledError):
        await job


app = FastAPI(title="AI Team Calendar", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def privacy_headers(request: Request, call_next):
    if request.method == "POST":
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).netloc != request.url.netloc:
            raise_error = {"detail": "다른 사이트에서의 갱신 요청은 허용되지 않습니다."}
            from fastapi.responses import JSONResponse
            return JSONResponse(raise_error, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.get("/api/health")
def health():
    return {"ok": True, "timezone": "Asia/Seoul", "schedule": "00:00", "calendarEnabled": False}


@app.get("/api/dashboard")
def dashboard(start: date, end: date, request: Request):
    if not 0 < (end - start).days <= 93:
        raise HTTPException(422, "조회 기간은 1~93일이어야 합니다. 종료일은 포함되지 않습니다.")
    return request.app.state.store.dashboard(start, end)


@app.post("/api/sync")
def sync(request: Request):
    try:
        return request.app.state.store.sync()
    except OSError:
        raise HTTPException(503, "갱신 결과를 저장하지 못했습니다. 저장 공간을 확인하세요.") from None


frontend = Path(os.getenv("FRONTEND_DIR", "/app/frontend/dist"))
if (frontend / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")


@app.get("/{path:path}")
def index(path: str):
    if path.startswith("api/") or path.startswith("assets/"):
        raise HTTPException(404)
    if not (frontend / "index.html").is_file():
        raise HTTPException(503, "화면 빌드가 준비되지 않았습니다.")
    return FileResponse(frontend / "index.html")
