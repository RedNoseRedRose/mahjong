import requests
import pytest
import time

BASE = "http://127.0.0.1:8000"
PREFIX = "/rooms"

def create_room(player):
    r = requests.post(f"{BASE}{PREFIX}/create_room", params={"player": player})
    r.raise_for_status()
    return r.json()["room_id"]

def join_room(room_id, player):
    r = requests.post(f"{BASE}{PREFIX}/join_room", params={"room_id": room_id, "player": player})
    return r

def start_game(room_id):
    r = requests.post(f"{BASE}{PREFIX}/start_game", params={"room_id": room_id})
    r.raise_for_status()
    return r.json()

def admin_set_hand(room_id, player, tiles):
    r = requests.post(f"{BASE}{PREFIX}/admin/set_hand", params={"room_id": room_id, "player": player}, json=tiles)
    r.raise_for_status()
    return r.json()

def discard_tile(room_id, player, tile):
    r = requests.post(f"{BASE}{PREFIX}/discard_tile", params={"room_id": room_id, "player": player, "tile": tile})
    return r

def claim(room_id, player, action, tiles=None):
    params = {"room_id": room_id, "player": player, "action": action}
    if tiles is not None:
        params["tiles"] = tiles
    r = requests.post(f"{BASE}{PREFIX}/claim", params=params)
    return r

def pass_claim(room_id, player):
    r = requests.post(f"{BASE}{PREFIX}/pass_claim", params={"room_id": room_id, "player": player})
    return r

def game_state(room_id, player=None):
    params = {"room_id": room_id}
    if player:
        params["player"] = player
    r = requests.get(f"{BASE}{PREFIX}/game_state", params=params)
    r.raise_for_status()
    return r.json()

def test_chi_only_next_player_and_success():
    # create room and players A,B,C,D
    room_id = create_room("Alice")
    join_room(room_id, "Bob").raise_for_status()
    join_room(room_id, "Carol").raise_for_status()
    join_room(room_id, "Dave").raise_for_status()
    start_game(room_id)
    # set hands so Alice has tile 5 and Bob (next) has 4 and 6
    admin_set_hand(room_id, "Alice", [5] + [10]*12)
    admin_set_hand(room_id, "Bob", [4,6] + [11]*11)
    admin_set_hand(room_id, "Carol", [4,6] + [12]*11)
    admin_set_hand(room_id, "Dave", [13]*13)
    # Alice discards 5
    r = discard_tile(room_id, "Alice", 5)
    assert r.status_code == 200
    # Carol (not next) attempts chi -> should fail
    r_bad = claim(room_id, "Carol", "chi", tiles="4,6")
    assert r_bad.status_code == 400
    # Bob (next) claims chi -> should succeed
    r_ok = claim(room_id, "Bob", "chi", tiles="4,6")
    assert r_ok.status_code == 200
    j = r_ok.json()
    assert j.get("claimed") == "chi"
    assert any(m.get("type") == "chi" for m in j.get("melds", []))

def test_peng_success_and_pass_clears_pending():
    room_id = create_room("P1")
    join_room(room_id, "P2").raise_for_status()
    join_room(room_id, "P3").raise_for_status()
    join_room(room_id, "P4").raise_for_status()
    start_game(room_id)
    # setup: Alice will discard 7, Bob has two 7s
    admin_set_hand(room_id, "P1", [7] + [20]*12)
    admin_set_hand(room_id, "P2", [7,7] + [21]*11)
    admin_set_hand(room_id, "P3", [22]*13)
    admin_set_hand(room_id, "P4", [23]*13)
    # P1 discards 7
    r = discard_tile(room_id, "P1", 7)
    assert r.status_code == 200
    # P2 claims peng
    r_peng = claim(room_id, "P2", "peng")
    assert r_peng.status_code == 200
    jp = r_peng.json()
    assert jp.get("claimed") == "peng"
    assert any(m.get("type") == "peng" for m in jp.get("melds", []))
    # Now test pass clearing: create new scenario
    room2 = create_room("Q1")
    join_room(room2, "Q2").raise_for_status()
    join_room(room2, "Q3").raise_for_status()
    join_room(room2, "Q4").raise_for_status()
    start_game(room2)
    admin_set_hand(room2, "Q1", [9] + [30]*12)
    admin_set_hand(room2, "Q2", [31]*13)
    admin_set_hand(room2, "Q3", [32]*13)
    admin_set_hand(room2, "Q4", [33]*13)
    r2 = discard_tile(room2, "Q1", 9)
    assert r2.status_code == 200
    # everyone passes
    assert pass_claim(room2, "Q2").status_code == 200
    assert pass_claim(room2, "Q3").status_code == 200
    res = pass_claim(room2, "Q4")
    assert res.status_code == 200
    assert res.json().get("resolved") == "no_claims"
    # current player (next) should be able to draw now
    st = game_state(room2)
    next_player = st["current_player"]
    r_draw = requests.post(f"{BASE}{PREFIX}/draw_tile", params={"room_id": room2, "player": next_player})
    assert r_draw.status_code == 200

if __name__ == "__main__":
    pytest.main(["-q", __file__])