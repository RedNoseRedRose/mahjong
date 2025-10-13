from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from typing import List, Optional
import sys
import os
import logging
import asyncio

from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="Mahjong Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Robust import of mahjong_core extension: try normal import, then fallback candidate paths.
mahjong_core = None
try:
    import mahjong_core  # try normal import
    mahjong_core = mahjong_core
except Exception as e:
    logger.warning("mahjong_core import failed: %s. Trying fallback paths...", e)
    base = os.path.dirname(__file__)
    candidates = [
        os.path.join(base, "mahjong_core"),
        os.path.join(base, "mahjong_core", "Release"),
        os.path.join(base, "mahjong_core", "build", "Release"),
        os.path.join(base, "mahjong_core", "build"),
        os.path.join(base, "mahjong_core", "Release"),
    ]
    for p in candidates:
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)
    try:
        import mahjong_core
        mahjong_core = mahjong_core
    except Exception as e2:
        logger.error("Failed to import mahjong_core after fallbacks: %s", e2)
        mahjong_core = None

class Settings(BaseSettings):
    # pending-discard timeout in seconds
    pending_discard_timeout: int = 10
    # cleanup loop interval in seconds (can be float)
    pending_cleanup_interval: float = 1.0
    # websocket idle config (seconds)
    ws_idle_timeout: float = 30.0
    ws_cleanup_interval: float = 5.0
    # admin token (if set, admin endpoints and ws require this token)
    admin_token: Optional[str] = None

    class Config:
        env_prefix = "MJ_"  # env vars: MJ_PENDING_DISCARD_TIMEOUT, MJ_PENDING_CLEANUP_INTERVAL, MJ_ADMIN_TOKEN

settings = Settings()
app.state.settings = settings

# import room after settings defined
from routers import room

app.include_router(room.router, prefix="/rooms", tags=["rooms"])

@app.on_event("startup")
async def _startup_tasks():
    # supply event loop for websocket send scheduling
    room.set_event_loop(asyncio.get_event_loop())
    try:
        room.start_pending_cleanup(interval=settings.pending_cleanup_interval,
                                   timeout=settings.pending_discard_timeout)
        # start websocket idle cleanup
        room.start_ws_cleanup(interval=settings.ws_cleanup_interval,
                              timeout=settings.ws_idle_timeout)
    except Exception:
        logger.exception("Failed to start background cleanup threads")

class TilesRequest(BaseModel):
    tiles: List[int]

@app.get("/")
def root():
    return {"status": "ok", "mahjong_core_loaded": bool(mahjong_core)}

@app.post("/check_win")
def check_win(req: TilesRequest):
    if len(req.tiles) != 14:
        raise HTTPException(status_code=400, detail="Tiles must be 14 numbers")
    if mahjong_core is None or not hasattr(mahjong_core, "is_win"):
        raise HTTPException(status_code=500, detail="mahjong_core module not available")
    try:
        result = mahjong_core.is_win(req.tiles)
    except Exception as e:
        logger.exception("mahjong_core.is_win error")
        raise HTTPException(status_code=500, detail=str(e))
    return {"win": bool(result)}

from pydantic import BaseModel
from typing import Optional

class UpdateCleanupModel(BaseModel):
    pending_discard_timeout: Optional[float] = None
    pending_cleanup_interval: Optional[float] = None

@app.post("/admin/update_cleanup")
def admin_update_cleanup(cfg: UpdateCleanupModel, x_admin_token: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    # simple header-based admin auth: check X-Admin-Token or Authorization: Bearer <token>
    token_required = app.state.settings.admin_token
    if token_required:
        provided = None
        if x_admin_token:
            provided = x_admin_token
        elif authorization and authorization.lower().startswith("bearer "):
            provided = authorization.split(None, 1)[1]
        if provided != token_required:
            raise HTTPException(status_code=401, detail="admin token required or invalid")
    # update runtime settings
    if cfg.pending_discard_timeout is not None:
        app.state.settings.pending_discard_timeout = cfg.pending_discard_timeout
    if cfg.pending_cleanup_interval is not None:
        app.state.settings.pending_cleanup_interval = cfg.pending_cleanup_interval
    # restart cleanup thread with new values
    try:
        import routers.room as room_module
        room_module.restart_pending_cleanup(interval=app.state.settings.pending_cleanup_interval,
                                            timeout=app.state.settings.pending_discard_timeout)
    except Exception:
        logger.exception("Failed to restart pending cleanup")
        raise HTTPException(status_code=500, detail="failed to restart cleanup")
    # return new settings
    return {"ok": True, "settings": app.state.settings.dict()}