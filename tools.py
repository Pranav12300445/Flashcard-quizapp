"""
tools.py — The real tools the agent calls.

Plain Python functions that read/write FlashcardMemory and return JSON strings,
so the LLM can read the result and decide its next step.
Required by the brief: add_card, quiz_me.  Extra: grade_answer, get_stats.
"""
import difflib
import json
import re

from memory import FlashcardMemory

_STOP = {"a", "an", "the", "is", "are", "of", "to", "in", "and", "it", "its", "that", "this"}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def _tokens(text: str) -> set[str]:
    return {t for t in _norm(text).split() if t not in _STOP}


def _is_match(user: str, reference: str) -> bool:
    u, r = _norm(user), _norm(reference)
    if not u:
        return False
    if u == r or difflib.SequenceMatcher(None, u, r).ratio() >= 0.85:
        return True
    ref_tokens = _tokens(reference)
    if ref_tokens:  # user covered most of the key words of the reference answer
        return len(ref_tokens & _tokens(user)) / len(ref_tokens) >= 0.7
    return False


def add_card(question: str, answer: str, memory: FlashcardMemory) -> str:
    result = memory.add_card(question, answer)
    return json.dumps({
        "status": "duplicate_ignored" if result["duplicate"] else "added",
        "card_id": result["card"]["id"],
        "question": result["card"]["question"],
        "deck_size": len(memory.cards),
    })


def quiz_me(memory: FlashcardMemory) -> str:
    """Pick the next card by weakness-weighted priority (NOT random). Never reveals the answer."""
    picked = memory.pick_next()
    if picked is None:
        return json.dumps({"status": "empty_deck", "message": "No cards yet. Ask the user to add some."})
    card, score = picked
    memory.clock += 1
    card["last_asked"] = memory.clock
    memory.last_asked_id = card["id"]
    memory.pending_id = card["id"]
    if card["wrong"] > card["right"]:
        reason = f"WEAK card (missed {card['wrong']}x, correct {card['right']}x) - re-quizzing it sooner"
    elif card["right"] + card["wrong"] == 0:
        reason = "new card, not asked yet"
    else:
        reason = f"review (correct {card['right']}x, missed {card['wrong']}x)"
    return json.dumps({
        "status": "ask",
        "card_id": card["id"],
        "question": card["question"],
        "priority_score": round(score, 2),
        "reason": reason,
        "deck_size": len(memory.cards),
        "weak_cards": len(memory.weak_cards()),
    })


def grade_answer(user_answer: str, memory: FlashcardMemory) -> str:
    """Grade the user's answer against the card that quiz_me last asked; update the counters."""
    if memory.pending_id is None:
        return json.dumps({"error": "No question is pending. Call quiz_me first."})
    card = memory.get_card(memory.pending_id)
    correct = _is_match(user_answer, card["answer"])
    memory.record_result(card["id"], correct)
    memory.pending_id = None
    return json.dumps({
        "correct": correct,
        "question": card["question"],
        "correct_answer": card["answer"],
        "card_record": {"right": card["right"], "wrong": card["wrong"]},
    })


def get_stats(memory: FlashcardMemory) -> str:
    cards = memory.all_cards()
    right = sum(c["right"] for c in cards)
    wrong = sum(c["wrong"] for c in cards)
    attempts = right + wrong
    return json.dumps({
        "deck_size": len(cards),
        "attempts": attempts,
        "accuracy_pct": round(100 * right / attempts, 1) if attempts else None,
        "weak_cards": [{"question": c["question"], "right": c["right"], "wrong": c["wrong"]}
                       for c in memory.weak_cards()],
        "mastered": sum(1 for c in cards if c["right"] >= 3 and c["wrong"] == 0),
    })


# ── OpenAI function-calling schema ──────────────────────
TOOLS_SCHEMA = [
    {"type": "function", "function": {
        "name": "add_card",
        "description": "Add one flashcard to the deck. Call once per card the user wants to add.",
        "parameters": {"type": "object", "properties": {
            "question": {"type": "string", "description": "The question / front of the card"},
            "answer": {"type": "string", "description": "The correct answer / back of the card"}},
            "required": ["question", "answer"]}}},
    {"type": "function", "function": {
        "name": "quiz_me",
        "description": "Pick the next card to ask. It prioritises weak cards (ones the user got wrong) "
                       "over strong ones. Returns the question only, never the answer.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "grade_answer",
        "description": "Grade the user's reply to the question currently pending from quiz_me. "
                       "Call this whenever the user answers a quiz question.",
        "parameters": {"type": "object", "properties": {
            "user_answer": {"type": "string", "description": "The user's answer, verbatim"}},
            "required": ["user_answer"]}}},
    {"type": "function", "function": {
        "name": "get_stats",
        "description": "Get accuracy, number of attempts and the list of weak cards. "
                       "Call before answering any question about progress or weak spots.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
]
