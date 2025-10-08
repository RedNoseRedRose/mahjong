import requests
import time

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

def draw_tile(room_id, player):
    r = requests.post(f"{BASE}{PREFIX}/draw_tile", params={"room_id": room_id, "player": player})
    r.raise_for_status()
    return r.json()

def discard_tile(room_id, player, tile):
    r = requests.post(f"{BASE}{PREFIX}/discard_tile", params={"room_id": room_id, "player": player, "tile": tile})
    r.raise_for_status()
    return r.json()

def game_state(room_id, player=None):
    params = {"room_id": room_id}
    if player:
        params["player"] = player
    r = requests.get(f"{BASE}{PREFIX}/game_state", params=params)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    # simulate 4 players
    room_id = create_room("Alice")
    join_room(room_id, "Bob")
    join_room(room_id, "Carol")
    join_room(room_id, "Dave")
    print("Players joined. Starting game...")
    state = start_game(room_id)
    print("Start Game:", state)
    # play 8 turns (draw + discard) to validate rotation
    for turn in range(8):
        # query state with current player's view to get their hand/counts
        st = game_state(room_id, player=state["current_player"])
        current = st["current_player"]
        print("Current player:", current)
        draw = draw_tile(room_id, current)
        print(f"{current} drew {draw.get('tile')}")
        hand = draw["hand"]
        discard = hand[0]
        res = discard_tile(room_id, current, discard)
        print(f"{current} discarded {discard}, next: {res['next_player']}")
        # update state for next loop
        state = game_state(room_id, player=res['next_player'])
        time.sleep(0.1)
    print("Final state (Alice view):", game_state(room_id, player="Alice"))