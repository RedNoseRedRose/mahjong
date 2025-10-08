import requests
import time
import sys

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

def draw_tile(room_id, player):
    return requests.post(f"{BASE}{PREFIX}/draw_tile", params={"room_id": room_id, "player": player})

def game_state(room_id, player=None):
    params = {"room_id": room_id}
    if player:
        params["player"] = player
    r = requests.get(f"{BASE}{PREFIX}/game_state", params=params)
    r.raise_for_status()
    return r.json()

def admin_update_cleanup(timeout=None, interval=None):
    data = {}
    if timeout is not None:
        data["pending_discard_timeout"] = timeout
    if interval is not None:
        data["pending_cleanup_interval"] = interval
    r = requests.post(f"{BASE}/admin/update_cleanup", json=data)
    r.raise_for_status()
    return r.json()

def pass_claim(room_id, player):
    return requests.post(f"{BASE}{PREFIX}/pass_claim", params={"room_id": room_id, "player": player})

def fail(msg):
    print("FAIL:", msg)
    sys.exit(1)

def scenario_timeout_via_update():
    print("Scenario: pending_discard cleared by cleanup thread after dynamic update")
    room = create_room("A")
    join_room(room, "B")
    join_room(room, "C")
    join_room(room, "D")
    st = start_game(room)
    current = st["current_player"]
    # set hands so current can discard tile 5 and next will be blocked
    admin_set_hand(room, current, [5] + [10]*12)
    admin_set_hand(room, "B", [11]*13)  # others arbitrary
    admin_set_hand(room, "C", [12]*13)
    admin_set_hand(room, "D", [13]*13)
    r = discard_tile(room, current, 5)
    if r.status_code != 200:
        fail("discard failed: " + r.text)
    print("Discarded 5, pending_discard set. Try draw immediately (should be blocked).")
    # next player attempt draw -> should be 400
    next_p = game_state(room)["current_player"]
    r_draw = draw_tile(room, next_p)
    if r_draw.status_code == 200:
        fail("Draw succeeded unexpectedly while pending_discard present")
    print("Draw blocked (expected). Now update cleanup to short timeout (2s).")
    admin_update_cleanup(timeout=2, interval=0.5)
    print("Waiting 3s for cleanup to clear pending_discard...")
    time.sleep(3)
    r_draw2 = draw_tile(room, next_p)
    if r_draw2.status_code != 200:
        fail("Draw still blocked after cleanup timeout: " + r_draw2.text)
    print("Draw succeeded after cleanup (expected). Scenario passed.")

def scenario_pass_clears_pending():
    print("Scenario: passing by all other players clears pending_discard immediately")
    room = create_room("P1")
    join_room(room, "P2")
    join_room(room, "P3")
    join_room(room, "P4")
    start_game(room)
    # set hands and force discard
    admin_set_hand(room, "P1", [9] + [20]*12)
    admin_set_hand(room, "P2", [21]*13)
    admin_set_hand(room, "P3", [22]*13)
    admin_set_hand(room, "P4", [23]*13)
    r = discard_tile(room, "P1", 9)
    if r.status_code != 200:
        fail("discard failed: " + r.text)
    # all others pass
    assert pass_claim(room, "P2").status_code == 200
    assert pass_claim(room, "P3").status_code == 200
    res = pass_claim(room, "P4")
    if res.status_code != 200:
        fail("pass_claim failed: " + res.text)
    if res.json().get("resolved") != "no_claims":
        fail("pass_claim did not resolve pending_discard")
    # now next player should be able to draw
    st = game_state(room)
    next_p = st["current_player"]
    r_draw = draw_tile(room, next_p)
    if r_draw.status_code != 200:
        fail("Draw blocked after all-pass: " + r_draw.text)
    print("All-pass cleared pending_discard and draw succeeded. Scenario passed.")

if __name__ == "__main__":
    try:
        scenario_timeout_via_update()
        scenario_pass_clears_pending()
    except Exception as e:
        fail(str(e))
    print("All scenarios passed.")