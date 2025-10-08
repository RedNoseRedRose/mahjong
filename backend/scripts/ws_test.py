import requests
import time
import json
import sys
import threading
import websocket

BASE = "http://127.0.0.1:8000"
PREFIX = "/rooms"

def create_room(player):
    r = requests.post(f"{BASE}{PREFIX}/create_room", params={"player": player})
    r.raise_for_status()
    return r.json()["room_id"]

def join_room(room_id, player):
    r = requests.post(f"{BASE}{PREFIX}/join_room", params={"room_id": room_id, "player": player})
    r.raise_for_status()
    return r.json()

def start_game(room_id):
    r = requests.post(f"{BASE}{PREFIX}/start_game", params={"room_id": room_id})
    r.raise_for_status()
    return r.json()

def admin_set_hand(room_id, player, tiles):
    r = requests.post(f"{BASE}{PREFIX}/admin/set_hand", params={"room_id": room_id, "player": player}, json=tiles)
    r.raise_for_status()
    return r.json()

def discard_tile(room_id, player, tile):
    return requests.post(f"{BASE}{PREFIX}/discard_tile", params={"room_id": room_id, "player": player, "tile": tile})

def claim(room_id, player, action, tiles=None):
    params = {"room_id": room_id, "player": player, "action": action}
    if tiles is not None:
        params["tiles"] = tiles
    return requests.post(f"{BASE}{PREFIX}/claim", params=params)

def _recv_loop(ws, events, stop_event):
    try:
        while not stop_event.is_set():
            msg = ws.recv()
            if not msg:
                break
            try:
                events.append(json.loads(msg))
            except Exception:
                events.append({"raw": msg})
    except Exception:
        pass

def find_event(events, predicate, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for e in list(events):
            try:
                if predicate(e):
                    return e
            except Exception:
                pass
        time.sleep(0.05)
    return None

def fail(msg):
    print("FAIL:", msg)
    sys.exit(2)

def main():
    # ensure backend (uvicorn) is running before invoking this script
    room = create_room("Alice")
    join_room(room, "Bob")
    join_room(room, "Carol")
    join_room(room, "Dave")
    st = start_game(room)
    current = st["current_player"]

    # open websocket connection for this room
    ws_url = f"ws://127.0.0.1:8000/rooms/ws/{room}"
    ws = websocket.create_connection(ws_url, timeout=5)
    events = []
    stop_event = threading.Event()
    t = threading.Thread(target=_recv_loop, args=(ws, events, stop_event), daemon=True)
    t.start()

    # set hands to force a chi by Bob (next player)
    # determine next player
    # set Alice hand to include 5, Bob to include 4 and 6
    admin_set_hand(room, "Alice", [5] + [10]*12)
    admin_set_hand(room, "Bob", [4,6] + [11]*11)
    admin_set_hand(room, "Carol", [20]*13)
    admin_set_hand(room, "Dave", [21]*13)

    # Alice discard 5
    r = discard_tile(room, "Alice", 5)
    if r.status_code != 200:
        fail("discard failed: " + r.text)
    # expect discard event
    e = find_event(events, lambda x: isinstance(x, dict) and x.get("type") == "discard" and x.get("tile") == 5, timeout=3.0)
    if not e:
        fail("did not receive discard event")
    print("Received discard event:", e)

    # Bob (next) claim chi
    r2 = claim(room, "Bob", "chi", tiles="4,6")
    if r2.status_code != 200:
        fail("claim failed: " + r2.text)

    # expect claim event with action chi or a claim outcome
    e2 = find_event(events, lambda x: isinstance(x, dict) and ((x.get("type") == "claim" and x.get("action") == "chi") or x.get("type") == "chi"), timeout=3.0)
    if not e2:
        # also check for meld broadcast in response body
        try:
            jr = r2.json()
            if not any(isinstance(v, dict) and v.get("type") == "chi" for v in jr.get("melds", [])):
                fail("did not receive claim event and response lacking chi meld")
        except Exception:
            fail("did not receive claim event and response parse failed")
    else:
        print("Received claim event:", e2)

    # cleanup
    stop_event.set()
    try:
        ws.close()
    except Exception:
        pass

    print("WebSocket flow verification passed.")
    return 0

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        fail(str(exc))