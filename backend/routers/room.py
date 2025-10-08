from fastapi import APIRouter, HTTPException
from models.room import Room
from typing import List, Optional
import threading
import logging
import os
import sys
import glob
import importlib.util
import importlib.machinery
import time
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from typing import Set, Dict, Optional

logger = logging.getLogger("uvicorn.error")

router = APIRouter()
rooms = {}  # room_id: Room
rooms_lock = threading.Lock()

# helper to load mahjong_core extension (must export is_win)
def _ensure_mahjong_core():
    if "mahjong_core" in sys.modules:
        m = sys.modules["mahjong_core"]
        if hasattr(m, "is_win"):
            return m
    try:
        import mahjong_core as mc
        if hasattr(mc, "is_win"):
            sys.modules["mahjong_core"] = mc
            return mc
    except Exception:
        pass
    base = os.path.dirname(os.path.dirname(__file__))
    candidates = [
        os.path.join(base, "mahjong_core"),
        os.path.join(base, "mahjong_core", "Release"),
        os.path.join(base, "mahjong_core", "build", "Release"),
        os.path.join(base, "mahjong_core", "build"),
    ]
    for p in candidates:
        if not os.path.isdir(p):
            continue
        for pattern in ("*.pyd", "*.so"):
            for fpath in glob.glob(os.path.join(p, pattern)):
                try:
                    module_name = "mahjong_core"
                    loader = importlib.machinery.ExtensionFileLoader(module_name, fpath)
                    spec = importlib.util.spec_from_file_location(module_name, fpath, loader=loader)
                    if not spec or not spec.loader:
                        continue
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    sys.modules[module_name] = mod
                    if hasattr(mod, "is_win"):
                        logger.info("Loaded mahjong_core from %s", fpath)
                        return mod
                except Exception:
                    logger.exception("failed to load mahjong_core from %s", fpath)
    return None

@router.post("/create_room")
def create_room(player: str, max_players: int = 4):
    with rooms_lock:
        room_id = len(rooms) + 1
        room = Room(room_id, [player], max_players=max_players)
        rooms[room_id] = room
    return {"room_id": room_id, "players": room.players, "max_players": room.max_players}

@router.post("/join_room")
def join_room(room_id: int, player: str):
    with rooms_lock:
        room = rooms.get(room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        try:
            room.add_player(player)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {"room_id": room_id, "players": room.players}

@router.post("/start_game")
def start_game(room_id: int):
    with rooms_lock:
        room = rooms.get(room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        try:
            room.deal_tiles()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"hands": room.hands, "deck_count": len(room.deck), "status": room.status, "current_player": room.current_player}

@router.get("/game_state")
def game_state(room_id: int, player: Optional[str] = None):
    with rooms_lock:
        room = rooms.get(room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        public = {
            "deck_count": len(room.deck),
            "current_player": room.current_player,
            "status": room.status,
            "discards": room.discards
        }
        if player and player in room.players:
            masked = {p: (room.hands[p] if p == player else f"{len(room.hands[p])} tiles") for p in room.players}
            public["hands"] = masked
        else:
            public["hands"] = {p: len(room.hands.get(p, [])) for p in room.players}
    return public

@router.post("/draw_tile")
def draw_tile(room_id: int, player: str):
    with rooms_lock:
        room = rooms.get(room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        if room.status != "playing":
            raise HTTPException(status_code=400, detail="Room not playing")
        if player not in room.players:
            raise HTTPException(status_code=400, detail="Player not in room")
        # block drawing while a pending discard is awaiting claims
        if room.pending_discard is not None:
            raise HTTPException(status_code=400, detail="Pending discard awaiting claims")
        if player != room.current_player:
            raise HTTPException(status_code=400, detail="Not player's turn")
        if not room.deck:
            raise HTTPException(status_code=400, detail="No tiles left")
        tile = room.deck.pop()
        room.hands[player].append(tile)
    mc = _ensure_mahjong_core()
    if mc is None:
        raise HTTPException(status_code=500, detail="mahjong_core module not available")
    try:
        win = bool(mc.is_win(room.hands[player]))
    except Exception:
        logger.exception("mahjong_core.is_win raised exception")
        raise HTTPException(status_code=500, detail="mahjong_core.is_win error")
    with rooms_lock:
        if win:
            room.status = "finished"
            event = {"type": "win", "room_id": room_id, "player": player, "hand": room.hands[player]}
            _broadcast_room(room_id, event)
            return {"tile": tile, "hand": room.hands[player], "win": True, "winner": player}
        event = {"type": "draw", "room_id": room_id, "player": player, "tile": tile, "hand_count": len(room.hands[player])}
        _broadcast_room(room_id, event)
        return {"tile": tile, "hand": room.hands[player], "must_discard": True, "current_player": room.current_player}

@router.post("/discard_tile")
def discard_tile(room_id: int, player: str, tile: int):
    with rooms_lock:
        room = rooms.get(room_id)
        if not room or room.status != "playing":
            raise HTTPException(status_code=400, detail="Room not playing")
        if player != room.current_player:
            raise HTTPException(status_code=400, detail="Not player's turn")
        if tile not in room.hands[player]:
            raise HTTPException(status_code=400, detail="Tile not in hand")
        room.hands[player].remove(tile)
        room.discards.append([player, tile])
        room.pending_discard = {"player": player, "tile": tile, "claims": [], "time": time.time()}
        room.passes = set()
        next_p = room.next_player()
        event = {"type": "discard", "room_id": room_id, "player": player, "tile": tile, "pending": True, "next_player": next_p}
        _broadcast_room(room_id, event)
    return {"hand": room.hands[player], "next_player": next_p, "deck_count": len(room.deck)}

# claim endpoint: action in {"chi","peng","gang","hu"}; tiles used param for chi can be passed as csv (optional)
@router.post("/claim")
def claim(room_id: int, player: str, action: str, tiles: Optional[str] = None):
    action = action.lower()
    if action not in ("chi", "peng", "gang", "hu"):
        raise HTTPException(status_code=400, detail="Invalid action")
    with rooms_lock:
        room = rooms.get(room_id)
        if not room or room.pending_discard is None:
            raise HTTPException(status_code=400, detail="No pending discard")
        if player not in room.players:
            raise HTTPException(status_code=400, detail="Player not in room")
        if player == room.pending_discard["player"]:
            raise HTTPException(status_code=400, detail="Discarder cannot claim own tile")
        # record claim with timestamp and distance (for priority)
        discarder = room.pending_discard["player"]
        try:
            idx_disc = room.players.index(discarder)
            idx_claim = room.players.index(player)
            n = len(room.players)
            distance = (idx_claim - idx_disc) % n
        except ValueError:
            distance = 999
        claim_entry = {"player": player, "action": action, "tiles": tiles, "time": time.time(), "distance": distance}
        room.pending_discard["claims"].append(claim_entry)

        # resolve immediately: pick highest priority (hu>gang>peng>chi), then smallest distance, then earliest time
        priority_map = {"hu": 4, "gang": 3, "peng": 2, "chi": 1}
        claims = room.pending_discard["claims"]
        # sort claims accordingly
        claims_sorted = sorted(claims, key=lambda c: (-priority_map.get(c["action"], 0), c["distance"], c["time"]))
        winner = claims_sorted[0]
        claimant = winner["player"]
        act = winner["action"]

        tile = room.pending_discard["tile"]
        # verify claimant has needed tiles and apply action
        if act == "hu":
            mc = _ensure_mahjong_core()
            if mc is None:
                raise HTTPException(status_code=500, detail="mahjong_core not available")
            # test hu with claimant's hand + tile
            temp_hand = list(room.hands[claimant]) + [tile]
            try:
                if mc.is_win(temp_hand):
                    room.status = "finished"
                    # remove pending discard and mark winner
                    room.pending_discard = None
                    room.passes = set()
                    event = {"type":"hu","room_id":room_id,"player":claimant,"winner":claimant}
                    _broadcast_room(room_id, event)
                    return {"win": True, "winner": claimant}
                else:
                    # invalid hu claim
                    return {"detail": "invalid hu claim", "accepted": False}
            except Exception:
                logger.exception("mahjong_core.is_win error")
                raise HTTPException(status_code=500, detail="mahjong_core.is_win error")
        elif act == "peng":
            # need two tiles equal to tile in claimant hand
            cnt = room.hands[claimant].count(tile)
            if cnt < 2:
                raise HTTPException(status_code=400, detail="Not enough tiles for peng")
            # remove two tiles and add meld
            removed = 0
            for _ in range(2):
                room.hands[claimant].remove(tile)
                removed += 1
            room.melds[claimant].append({"type": "peng", "tiles": [tile, tile, tile]})
            # remove discard from discard pile (last occurrence)
            if room.discards and room.discards[-1][1] == tile:
                room.discards.pop()
            # set current player to claimant
            room.pending_discard = None
            room.passes = set()
            room.current_player = claimant
            event = {"type":"claim","action":"peng","room_id":room_id,"player":claimant,"melds":room.melds[claimant]}
            _broadcast_room(room_id, event)
            return {"claimed": "peng", "player": claimant, "melds": room.melds[claimant]}
        elif act == "chi":
            # chi only allowed for next player (distance == 1)
            if winner["distance"] != 1:
                raise HTTPException(status_code=400, detail="Chi only allowed to next player")
            # tiles param expected as comma separated integers indicating the two tiles to use
            if not tiles:
                raise HTTPException(status_code=400, detail="Chi requires tiles param")
            try:
                parts = [int(x.strip()) for x in tiles.split(",")]
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid tiles param")
            if len(parts) != 2:
                raise HTTPException(status_code=400, detail="Chi requires two tiles")
            # check those tiles + tile form a sequence
            seq = sorted(parts + [tile])
            # simple same-suit check: for suited tiles 1..27 only; honors cannot chi
            def same_suit(a, b):
                # suit size 9: 1-9,10-18,19-27
                if a <= 27 and b <= 27:
                    return ( (a-1)//9 ) == ( (b-1)//9 )
                return False
            if not (same_suit(seq[0], seq[1]) and same_suit(seq[1], seq[2])):
                raise HTTPException(status_code=400, detail="Chi tiles must be same suit sequence")
            if not (seq[0]+1 == seq[1] and seq[1]+1 == seq[2]):
                raise HTTPException(status_code=400, detail="Tiles do not form sequence")
            # check claimant has the two tiles
            for t in parts:
                if t not in room.hands[claimant]:
                    raise HTTPException(status_code=400, detail="Missing tile for chi")
            # remove those tiles
            for t in parts:
                room.hands[claimant].remove(t)
            room.melds[claimant].append({"type": "chi", "tiles": seq})
            if room.discards and room.discards[-1][1] == tile:
                room.discards.pop()
            room.pending_discard = None
            room.passes = set()
            room.current_player = claimant
            event = {"type":"claim","action":"chi","room_id":room_id,"player":claimant,"melds":room.melds[claimant]}
            _broadcast_room(room_id, event)
            return {"claimed": "chi", "player": claimant, "melds": room.melds[claimant]}
        elif act == "gang":
            # check claimant has three tiles equal to tile (exposed kong)
            cnt = room.hands[claimant].count(tile)
            if cnt < 3:
                raise HTTPException(status_code=400, detail="Not enough tiles for gang")
            # before performing gang, check if anyone else can hu on this tile (rob gang)
            mc = _ensure_mahjong_core()
            if mc is None:
                raise HTTPException(status_code=500, detail="mahjong_core not available")
            for p in room.players:
                if p == claimant:
                    continue
                temp_hand = list(room.hands[p]) + [tile]
                try:
                    if mc.is_win(temp_hand):
                        # allow other player to hu; we record the potential rob but resolve by higher priority hu claims
                        # add a placeholder claim for that player with action 'hu' and distance computed
                        idx_disc = room.players.index(room.pending_discard["player"])
                        idx_p = room.players.index(p)
                        distance = (idx_p - idx_disc) % len(room.players)
                        room.pending_discard["claims"].append({"player": p, "action": "hu", "tiles": None, "time": time.time(), "distance": distance})
                        # resolve again (recursion safe because we now have added hu claims)
                        return claim(room_id=room_id, player=p, action="hu")
                except Exception:
                    logger.exception("mahjong_core.is_win error during rob gang check")
                    raise HTTPException(status_code=500, detail="mahjong_core.is_win error")
            # perform gang
            for _ in range(3):
                room.hands[claimant].remove(tile)
            room.melds[claimant].append({"type": "gang", "tiles": [tile]*4})
            if room.discards and room.discards[-1][1] == tile:
                room.discards.pop()
            room.pending_discard = None
            room.passes = set()
            # claimant gets turn to draw after kong (current_player set to claimant)
            room.current_player = claimant
            event = {"type":"claim","action":"gang","room_id":room_id,"player":claimant,"melds":room.melds[claimant]}
            _broadcast_room(room_id, event)
            return {"claimed": "gang", "player": claimant, "melds": room.melds[claimant]}

@router.post("/pass_claim")
def pass_claim(room_id: int, player: str):
    with rooms_lock:
        room = rooms.get(room_id)
        if not room or room.pending_discard is None:
            raise HTTPException(status_code=400, detail="No pending discard")
        if player not in room.players:
            raise HTTPException(status_code=400, detail="Player not in room")
        room.passes.add(player)
        # notify others of pass
        _broadcast_room(room_id, {"type": "pass", "room_id": room_id, "player": player, "passes": list(room.passes)})
        discarder = room.pending_discard["player"]
        others = set(room.players) - {discarder}
        if room.passes.issuperset(others):
            room.pending_discard = None
            room.passes = set()
            _broadcast_room(room_id, {"type": "pending_cleared", "room_id": room_id, "reason": "all_passed"})
            return {"passed": True, "resolved": "no_claims"}
    return {"passed": True, "resolved": "waiting_other_passes"}

@router.post("/admin/set_hand")
def admin_set_hand(room_id: int, player: str, tiles: List[int]):
    """Test helper: set a player's hand explicitly (dev only)."""
    with rooms_lock:
        room = rooms.get(room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        if player not in room.players:
            raise HTTPException(status_code=400, detail="Player not in room")
        room.hands[player] = tiles[:]
    return {"room_id": room_id, "player": player, "hand_count": len(room.hands[player])}

# pending discard timeout defaults (kept for fallback if app does not call start_pending_cleanup)
PENDING_DISCARD_TIMEOUT = float(os.getenv("MJ_PENDING_DISCARD_TIMEOUT", 10))
_PENDING_CLEANUP_INTERVAL = float(os.getenv("MJ_PENDING_CLEANUP_INTERVAL", 1.0))
_pending_cleanup_thread: Optional[threading.Thread] = None
_pending_cleanup_stop_event: Optional[threading.Event] = None

def _pending_cleanup_loop(stop_event: threading.Event, interval: float, timeout: float):
    logger.info("Pending-discard cleanup thread started (interval=%s, timeout=%s)", interval, timeout)
    while not stop_event.is_set():
        try:
            # wait with timeout so we can stop quickly when requested
            stopped = stop_event.wait(interval)
            if stopped:
                break
            now = time.time()
            with rooms_lock:
                for room in list(rooms.values()):
                    pd = room.pending_discard
                    if pd is None:
                        continue
                    ts = pd.get("time", 0)
                    if now - ts > timeout:
                        logger.info("Clearing pending_discard for room %s (tile=%s) due to timeout", room.room_id, pd.get("tile"))
                        room.pending_discard = None
                        room.passes = set()
                        # notify connected clients
                        _broadcast_room(room.room_id, {"type": "pending_cleared", "room_id": room.room_id, "reason": "timeout"})
        except Exception:
            logger.exception("Exception in pending-discard cleanup loop")
    logger.info("Pending-discard cleanup thread exiting")

def start_pending_cleanup(interval: Optional[float] = None, timeout: Optional[float] = None):
    """Start background thread to clear stale pending_discard entries.

    If interval/timeout are None the module defaults or env values are used.
    """
    global _pending_cleanup_thread, _pending_cleanup_stop_event
    if _pending_cleanup_thread and _pending_cleanup_thread.is_alive():
        return
    if interval is None:
        interval = _PENDING_CLEANUP_INTERVAL
    if timeout is None:
        timeout = PENDING_DISCARD_TIMEOUT
    _pending_cleanup_stop_event = threading.Event()
    _pending_cleanup_thread = threading.Thread(target=_pending_cleanup_loop, args=(_pending_cleanup_stop_event, interval, timeout), daemon=True)
    _pending_cleanup_thread.start()

def stop_pending_cleanup(timeout: float = 2.0):
    """Stop the background cleanup thread, waiting up to `timeout` seconds."""
    global _pending_cleanup_thread, _pending_cleanup_stop_event
    if _pending_cleanup_stop_event:
        _pending_cleanup_stop_event.set()
    if _pending_cleanup_thread:
        _pending_cleanup_thread.join(timeout)
    _pending_cleanup_thread = None
    _pending_cleanup_stop_event = None

def restart_pending_cleanup(interval: Optional[float] = None, timeout: Optional[float] = None):
    """Restart cleanup thread with new parameters."""
    stop_pending_cleanup()
    start_pending_cleanup(interval=interval, timeout=timeout)

# websocket support / broadcast
_loop: Optional[asyncio.AbstractEventLoop] = None
room_connections: Dict[int, Set[WebSocket]] = {}

def set_event_loop(loop: asyncio.AbstractEventLoop):
    global _loop
    _loop = loop

def _broadcast_room(room_id: int, event: dict):
    """Thread-safe broadcast to all websockets in room (uses saved event loop)."""
    conns = room_connections.get(room_id, set()).copy()
    if not conns or _loop is None:
        return
    for ws in list(conns):
        try:
            # schedule send on the application's event loop
            asyncio.run_coroutine_threadsafe(ws.send_json(event), _loop)
        except Exception:
            logger.exception("Failed to send websocket message, removing connection")
            # best-effort removal
            try:
                room_connections[room_id].discard(ws)
            except Exception:
                pass

@router.websocket("/ws/{room_id}")
async def websocket_room(ws: WebSocket, room_id: int):
    """WebSocket endpoint for room events. Clients receive JSON events."""
    await ws.accept()
    rid = int(room_id)
    room_connections.setdefault(rid, set()).add(ws)
    try:
        while True:
            # keep connection alive; client may send pings or subscribe messages
            try:
                await ws.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                # ignore other receives (no-op)
                await asyncio.sleep(0.1)
    finally:
        room_connections.get(rid, set()).discard(ws)