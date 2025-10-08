import requests
import time
import pytest

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

def draw_tile(room_id, player):
    return requests.post(f"{BASE}{PREFIX}/draw_tile", params={"room_id": room_id, "player": player})

def discard_tile(room_id, player, tile):
    return requests.post(f"{BASE}{PREFIX}/discard_tile", params={"room_id": room_id, "player": player, "tile": tile})

def game_state(room_id, player=None):
    params = {"room_id": room_id}
    if player:
        params["player"] = player
    r = requests.get(f"{BASE}{PREFIX}/game_state", params=params)
    r.raise_for_status()
    return r.json()

def test_illegal_player_draw():
    room_id = create_room("A1")
    join_room(room_id, "B1").raise_for_status()
    start_game(room_id)
    # Eve is not in room
    r = draw_tile(room_id, "Eve")
    assert r.status_code == 400

def test_duplicate_join():
    room_id = create_room("A2")
    r1 = join_room(room_id, "B2")
    assert r1.status_code == 200
    r2 = join_room(room_id, "B2")
    assert r2.status_code == 400

def test_empty_deck_draw_and_duplicate_discard():
    # create room and start
    room_id = create_room("A3")
    join_room(room_id, "B3").raise_for_status()
    join_room(room_id, "C3").raise_for_status()
    join_room(room_id, "D3").raise_for_status()
    start_game(room_id)
    # clear deck via admin helper
    r = requests.post(f"{BASE}{PREFIX}/admin/clear_deck", params={"room_id": room_id})
    assert r.status_code == 200 and r.json().get("deck_count") == 0
    # current player cannot draw
    st = game_state(room_id, player=None)
    current = st["current_player"]
    r_draw = draw_tile(room_id, current)
    assert r_draw.status_code == 400
    # duplicate discard: perform draw+discard on fresh room to test duplicate discard behavior
    room_id2 = create_room("A4")
    join_room(room_id2, "B4").raise_for_status()
    join_room(room_id2, "C4").raise_for_status()
    join_room(room_id2, "D4").raise_for_status()
    start_game(room_id2)
    st2 = game_state(room_id2, player=None)
    current2 = st2["current_player"]
    # draw a tile then discard it twice
    r_draw2 = draw_tile(room_id2, current2)
    assert r_draw2.status_code == 200
    hand = r_draw2.json().get("hand", [])
    assert len(hand) >= 1
    tile = hand[0]
    r_disc1 = discard_tile(room_id2, current2, tile)
    assert r_disc1.status_code == 200
    # second discard of same tile should fail
    r_disc2 = discard_tile(room_id2, current2, tile)
    assert r_disc2.status_code == 400

if __name__ == "__main__":
    # run tests manually if pytest not used
    pytest.main(["-q", __file__])