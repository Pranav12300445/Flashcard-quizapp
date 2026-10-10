"""
server.py — Flask backend bridging the web UI to the FlashMind agent.
"""
import os
import sys

# Fix Windows console encoding — prevents 'charmap' codec errors with emoji
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from flask import Flask, jsonify, request, send_from_directory

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from agent import FlashcardAgent

app = Flask(__name__, static_folder=".")

# Singleton agent (keeps memory across web chat turns)
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = FlashcardAgent()
    return _agent


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    message = (request.json or {}).get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400
    try:
        agent = get_agent()
        response = agent.chat(message, verbose=True)
        return jsonify({"response": response, "steps": list(agent.step_log),
                        "provider": agent.provider, "model": agent.model})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reset", methods=["POST"])
def reset():
    if _agent is not None:
        _agent.reset()
    return jsonify({"status": "ok"})


@app.route("/api/deck", methods=["GET"])
def get_deck():
    """Return all cards in the deck (for restoring UI on page refresh)."""
    agent = get_agent()
    cards = agent.memory.all_cards()
    return jsonify({"cards": cards, "deck_size": len(cards)})


@app.route("/api/delete_card", methods=["POST"])
def delete_card():
    """Delete a specific card by its ID."""
    card_id = (request.json or {}).get("card_id")
    if card_id is None:
        return jsonify({"error": "Missing card_id"}), 400
    agent = get_agent()
    removed = agent.memory.remove_card(int(card_id))
    if removed is None:
        return jsonify({"error": "Card not found"}), 404
    return jsonify({"status": "deleted", "card_id": card_id,
                    "deck_size": len(agent.memory.cards)})


@app.route("/api/start_quiz", methods=["POST"])
def start_quiz():
    """Start a quiz — pick the first card (bypasses LLM)."""
    import json as _json
    from tools import quiz_me
    agent = get_agent()
    result = _json.loads(quiz_me(agent.memory))
    return jsonify(result)


@app.route("/api/grade", methods=["POST"])
def grade():
    """Grade an answer and get the next question (bypasses LLM entirely)."""
    import json as _json
    from tools import grade_answer, quiz_me
    user_answer = (request.json or {}).get("answer", "").strip()
    is_last = (request.json or {}).get("is_last", False)
    if not user_answer:
        return jsonify({"error": "Empty answer"}), 400
    agent = get_agent()
    # Grade the answer using the deterministic tool
    grade_result = _json.loads(grade_answer(user_answer, agent.memory))
    # Get next question (unless this was the last card)
    next_question = None
    if not is_last:
        next_result = _json.loads(quiz_me(agent.memory))
        if next_result.get("status") == "ask":
            next_question = next_result
    return jsonify({
        "grade": grade_result,
        "next_question": next_question,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"FlashMind running at http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
