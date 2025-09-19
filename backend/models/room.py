from typing import List, Dict
import random

class Room:
    def __init__(self, room_id: int, players: List[str]):
        self.room_id = room_id
        self.players = players
        self.status = "waiting"
        self.deck = self.init_deck()
        self.hands: Dict[str, List[int]] = {p: [] for p in players}
        self.current_player = players[0] if players else None

    def init_deck(self):
        deck = []
        for t in list(range(1, 28)) + list(range(28, 40)):
            deck += [t] * 4
        random.shuffle(deck)
        return deck

    def deal_tiles(self):
        for player in self.players:
            self.hands[player] = [self.deck.pop() for _ in range(13)]
        self.status = "playing"

    def next_player(self):
        idx = self.players.index(self.current_player)
        self.current_player = self.players[(idx + 1) % len(self.players)]