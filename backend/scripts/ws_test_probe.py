import websocket, json, threading, time, requests, sys

BASE_HTTP = "http://127.0.0.1:8000"
CANDIDATES = [
    "ws://127.0.0.1:8000/rooms/ws/{room}",
    "ws://127.0.0.1:8000/ws/{room}",
    "ws://127.0.0.1:8000/Rooms/ws/{room}",
]

def create_room(player="Alice"):
    r = requests.post(f"{BASE_HTTP}/rooms/create_room", params={"player": player})
    r.raise_for_status()
    return r.json()["room_id"]

def try_connect(url, timeout=5):
    try:
        ws = websocket.create_connection(url, timeout=timeout)
        return ws
    except Exception as e:
        return e

def probe(room):
    print("Probing websocket endpoints for room:", room)
    for u in CANDIDATES:
        url = u.format(room=room)
        print(" -> trying", url)
        res = try_connect(url, timeout=3)
        if isinstance(res, websocket.WebSocket):
            print("   SUCCESS connected to", url)
            res.close()
            return url
        else:
            print("   FAILED:", repr(res))
    return None

def main():
    room = create_room("ProbeUser")
    print("Created room:", room)
    good = probe(room)
    if not good:
        print("\nNo websocket endpoint matched. Quick checks:")
        print(" - Confirm routers/room.py contains @router.websocket('/ws/{room_id}')")
        print(" - Confirm app.py includes router with prefix '/rooms' (app.include_router(room.router, prefix='/rooms'))")
        print(" - Check uvicorn console for startup errors and route registration")
        print(" - Open http://127.0.0.1:8000/docs to verify REST endpoints (ws routes won't show) and try GET /rooms/game_state?room_id={}".format(room))
        sys.exit(2)
    else:
        print("Use URL:", good)
        print("Now trying to receive a discard event by performing a discard...")
        # open ws and listen
        ws = websocket.create_connection(good, timeout=5)
        events = []
        stop = False
        def recv_loop():
            nonlocal stop
            try:
                while not stop:
                    msg = ws.recv()
                    if not msg:
                        break
                    try:
                        events.append(json.loads(msg))
                    except:
                        events.append({"raw": msg})
            except Exception:
                pass
        t = threading.Thread(target=recv_loop, daemon=True)
        t.start()
        # perform actions to generate events
        requests.post(f"{BASE_HTTP}/rooms/join_room", params={"room_id": room, "player": "B"})
        requests.post(f"{BASE_HTTP}/rooms/join_room", params={"room_id": room, "player": "C"})
        requests.post(f"{BASE_HTTP}/rooms/join_room", params={"room_id": room, "player": "D"})
        requests.post(f"{BASE_HTTP}/rooms/start_game", params={"room_id": room})
        # set Alice hand then discard
        requests.post(f"{BASE_HTTP}/rooms/admin/set_hand", params={"room_id": room, "player": "ProbeUser"}, json=[5]+[10]*12)
        r = requests.post(f"{BASE_HTTP}/rooms/discard_tile", params={"room_id": room, "player": "ProbeUser", "tile": 5})
        if r.status_code != 200:
            print("Discard failed:", r.status_code, r.text)
        # wait for events
        time.sleep(2)
        stop = True
        ws.close()
        print("Events received:", events)
        if not events:
            print("No events received — likely event loop not set in app (room.set_event_loop) or broadcast not wired.")
            print("Check app startup sets room.set_event_loop(asyncio.get_event_loop()) before starting cleanup thread.")
        else:
            print("WebSocket flow appears functional.")
        return 0

if __name__ == "__main__":
    sys.exit(main())