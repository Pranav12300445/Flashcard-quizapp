"""
memory.py — Session memory for the Flashcard Quiz Agent (T26).

Two layers (same idea as SubZero):
  Layer 1: structured deck state (cards + right/wrong counters). Tools read/write this.
  Layer 2: conversation buffer (user/assistant turns) injected into every LLM call.

Deck state is persisted to a JSON file so it survives page refreshes and server restarts.
"""
import json
import os

DECK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck_data.json")


class FlashcardMemory:
    MAX_MESSAGES = 40  # keep the prompt small

    def __init__(self):
        self.cards: dict[int, dict] = {}
        self.messages: list[dict] = []
        self.pending_id: int | None = None      # card currently waiting for an answer
        self.last_asked_id: int | None = None
        self.clock = 0                          # increments on every quiz_me call
        self._next_id = 1
        self._load_from_file()

    def clear(self) -> None:
        self.cards = {}
        self.messages = []
        self.pending_id = None
        self.last_asked_id = None
        self.clock = 0
        self._next_id = 1
        self._delete_file()

    # ── persistence ─────────────────────────────────────
    def _save_to_file(self) -> None:
        """Persist deck state to JSON file."""
        data = {
            "cards": {str(k): v for k, v in self.cards.items()},
            "next_id": self._next_id,
            "clock": self.clock,
        }
        try:
            with open(DECK_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[memory] Warning: could not save deck: {e}")

    def _load_from_file(self) -> None:
        """Load deck state from JSON file if it exists."""
        if not os.path.exists(DECK_FILE):
            return
        try:
            with open(DECK_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.cards = {int(k): v for k, v in data.get("cards", {}).items()}
            self._next_id = data.get("next_id", 1)
            self.clock = data.get("clock", 0)
        except Exception as e:
            print(f"[memory] Warning: could not load deck: {e}")

    def _delete_file(self) -> None:
        """Remove the persistence file on reset."""
        try:
            if os.path.exists(DECK_FILE):
                os.remove(DECK_FILE)
        except Exception as e:
            print(f"[memory] Warning: could not delete deck file: {e}")

    # ── conversation buffer ─────────────────────────────
    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        self.messages = self.messages[-self.MAX_MESSAGES:]

    def get_messages(self) -> list[dict]:
        return list(self.messages)

    # ── deck state ──────────────────────────────────────
    def add_card(self, question: str, answer: str) -> dict:
        for c in self.cards.values():
            if c["question"].strip().lower() == question.strip().lower():
                return {"duplicate": True, "card": c}
        card = {
            "id": self._next_id, "question": question.strip(), "answer": answer.strip(),
            "right": 0, "wrong": 0, "last_asked": 0,
        }
        self.cards[card["id"]] = card
        self._next_id += 1
        self._save_to_file()
        return {"duplicate": False, "card": card}

    def remove_card(self, card_id: int) -> dict | None:
        """Remove a card by ID. Returns the removed card or None."""
        card = self.cards.pop(card_id, None)
        if card is not None:
            self._save_to_file()
        return card

    def get_card(self, card_id: int) -> dict | None:
        return self.cards.get(card_id)

    def all_cards(self) -> list[dict]:
        return list(self.cards.values())

    @staticmethod
    def priority(card: dict, clock: int) -> float:
        """Higher = should be asked sooner. This is THE decision rule of the agent's quiz tool."""
        never_asked_bonus = 2.0 if card["right"] + card["wrong"] == 0 else 0.0
        staleness = 0.5 * (clock - card["last_asked"])
        return 3.0 * card["wrong"] - 1.0 * card["right"] + staleness + never_asked_bonus

    def pick_next(self) -> tuple[dict, float] | None:
        cards = self.all_cards()
        if not cards:
            return None
        if len(cards) > 1:  # never repeat the card we just asked
            cards = [c for c in cards if c["id"] != self.last_asked_id]
        best = max(cards, key=lambda c: self.priority(c, self.clock))
        return best, self.priority(best, self.clock)

    def record_result(self, card_id: int, correct: bool) -> None:
        card = self.cards[card_id]
        card["right" if correct else "wrong"] += 1
        self._save_to_file()

    def weak_cards(self) -> list[dict]:
        weak = [c for c in self.all_cards() if c["wrong"] > c["right"]]
        return sorted(weak, key=lambda c: c["wrong"] - c["right"], reverse=True)
