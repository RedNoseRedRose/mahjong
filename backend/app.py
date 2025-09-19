from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "mahjong_core"))
import mahjong_core
from routers import room

app = FastAPI()
app.include_router(room.router)

class TilesRequest(BaseModel):
    tiles: List[int]

@app.post("/check_win")
def check_win(req: TilesRequest):
    if len(req.tiles) != 14:
        raise HTTPException(status_code=400, detail="Tiles must be 14 numbers")
    result = mahjong_core.is_win(req.tiles)
    return {"win": result}