from typing import List, Dict, Optional
import random

class Room:
    def __init__(self, room_id: int, players: Optional[List[str]] = None, max_players: int = 4):
        self.room_id = room_id
        self.players: List[str] = players[:] if players else []
        self.max_players = max_players
        self.status = "waiting"  # waiting | playing | finished
        self.deck: List[int] = []
        self.hands: Dict[str, List[int]] = {p: [] for p in self.players}
        self.current_player: Optional[str] = None
        self.discards: List[List[int]] = []  # list of [player, tile]
        self.dealer_index = 0
        self.melds: Dict[str, List[Dict]] = {p: [] for p in self.players}  # player's melds
        # pending discard and claim state
        self.pending_discard: Optional[Dict] = None
        self.passes: set = set()  # players who passed on current pending discard
        self.init_deck()

    def init_deck(self):
        deck = []
        for t in list(range(1, 28)) + list(range(28, 40)):
            deck += [t] * 4
        random.shuffle(deck)
        self.deck = deck
        return self.deck

    def add_player(self, player: str):
        if self.status != "waiting":
            raise ValueError("Game already started")
        if player in self.players:
            raise ValueError("Player already in room")
        if len(self.players) >= self.max_players:
            raise ValueError("Room is full")
        self.players.append(player)
        self.hands[player] = []
        self.melds[player] = []

    def deal_tiles(self):
        if len(self.players) < 2:
            raise ValueError("Need at least 2 players to start")
        if not self.deck:
            self.init_deck()
        self.hands = {p: [] for p in self.players}
        self.discards = []
        self.melds = {p: [] for p in self.players}
        self.pending_discard = None
        self.passes = set()
        for _ in range(13):
            for p in self.players:
                if not self.deck:
                    raise ValueError("Not enough tiles to deal")
                self.hands[p].append(self.deck.pop())
        self.status = "playing"
        self.dealer_index = 0
        self.current_player = self.players[self.dealer_index]

    def next_player(self):
        if not self.players:
            self.current_player = None
            return None
        if self.current_player not in self.players:
            self.current_player = self.players[0]
            return self.current_player
        idx = self.players.index(self.current_player)
        idx = (idx + 1) % len(self.players)
        self.current_player = self.players[idx]
        return self.current_player

    def remove_player(self, player: str):
        if player in self.players:
            self.players.remove(player)
            self.hands.pop(player, None)
            self.melds.pop(player, None)
            if self.dealer_index >= len(self.players):
                self.dealer_index = 0
            if self.current_player == player:
                self.current_player = self.players[self.dealer_index] if self.players else None