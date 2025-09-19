from fastapi import APIRouter, HTTPException
from models.room import Room
import mahjong_core

router = APIRouter()
rooms = {}  # room_id: Room

@router.post("/create_room")
def create_room(player: str):
    room_id = len(rooms) + 1
    rooms[room_id] = Room(room_id, [player])
    return {"room_id": room_id}

@router.post("/draw_tile")
def draw_tile(room_id: int, player: str):
    room = rooms.get(room_id)
    if not room or player != room.current_player:
        raise HTTPException(status_code=400, detail="Not player's turn")
    if not room.deck:
        raise HTTPException(status_code=400, detail="No tiles left")
    tile = room.deck.pop()
    room.hands[player].append(tile)
    # 胡牌判定
    if mahjong_core.is_win(room.hands[player]):
        room.status = "finished"
        return {"tile": tile, "hand": room.hands[player], "win": True, "winner": player}
    # 轮到下一个玩家
    room.next_player()
    return {"tile": tile, "hand": room.hands[player], "next_player": room.current_player}

@router.post("/discard_tile")
def discard_tile(room_id: int, player: str, tile: int):
    room = rooms.get(room_id)
    if not room or player != room.current_player:
        raise HTTPException(status_code=400, detail="Not player's turn")
    if tile not in room.hands[player]:
        raise HTTPException(status_code=400, detail="Tile not in hand")
    room.hands[player].remove(tile)
    # 轮到下一个玩家
    room.next_player()
    return {"hand": room.hands[player], "next_player": room.current_player}

@router.post("/start_game")
def start_game(room_id: int):
    room = rooms.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    room.deal_tiles()
    return {"hands": room.hands, "deck_count": len(room.deck), "status": room.status}

@router.get("/game_state")
def game_state(room_id: int):
    room = rooms.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return {
        "hands": room.hands,
        "deck_count": len(room.deck),
        "current_player": room.current_player,
        "status": room.status
    }