from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import mysql.connector
import json
from typing import Dict, List

app = FastAPI()

# 数据库连接
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="password",
    database="mahjong_db"
)
cursor = db.cursor(dictionary=True)

# 游戏房间管理
class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, room_id: str, websocket: WebSocket):
        await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = []
        self.rooms[room_id].append(websocket)
    
    async def disconnect(self, room_id: str, websocket: WebSocket):
        self.rooms[room_id].remove(websocket)
        if not self.rooms[room_id]:
            del self.rooms[room_id]
    
    async def broadcast(self, room_id: str, message: dict):
        for websocket in self.rooms[room_id]:
            await websocket.send_text(json.dumps(message))

room_manager = RoomManager()

# 用户模型
class User(BaseModel):
    username: str
    password: str

# 注册接口
@app.post("/register")
async def register(user: User):
    cursor.execute(
        "INSERT INTO users (username, password) VALUES (%s, %s)",
        (user.username, user.password)
    )
    db.commit()
    return {"message": "注册成功"}

# 游戏房间WebSocket
@app.websocket("/ws/room/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await room_manager.connect(room_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # 处理游戏消息（出牌、吃碰杠等）
            if message["type"] == "play_tile":
                # 广播出牌信息给房间内所有玩家
                await room_manager.broadcast(room_id, {
                    "type": "tile_played",
                    "user": message["user"],
                    "tile": message["tile"]
                })
            # 处理其他游戏事件...
            
    except WebSocketDisconnect:
        await room_manager.disconnect(room_id, websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
    